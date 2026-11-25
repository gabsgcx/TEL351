#!/usr/bin/env python3
"""Runner de experimentos del agente base (Taller 5).

Diseno experimental
-------------------
Factor 1 (condicion del problema): desplazamiento lateral de la amenaza
    respecto de la posicion nominal w_k del agente base.
        D0  "en el cono"      |y0 - w_k,y| <= 30
        D1  "fuera del cono"  |y0 - w_k,y| >= 60
    (se excluye la banda 30 < offset < 60 para no mezclar el borde del cono)

Factor 2 (robustez): ruido en la estimacion del error angular
        sigma = 0 grados  (percepcion ideal)
        sigma = 10 grados (incertidumbre de orientacion, Taller 3)

Referencia superior: politica "bearing" (servo visual). No es un baseline; se
incluye solo para verificar que la metrica es sensible y que la brecha entre el
agente base y el optimo practico es cerrable.

Apareamiento: la posicion inicial de la amenaza es una funcion determinista de
(semilla, indice de episodio), independiente de la politica y del ruido
(verificado). Por lo tanto todas las condiciones se evaluan sobre exactamente
los mismos episodios: la comparacion es pareada.

Uso:
    python run_experiments.py                  # experimento completo
    python run_experiments.py --quick          # smoke test rapido
    python run_experiments.py --pool 800       # pool mas grande
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from baseline_agent import AgentConfig, run_batch, summarize

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "resultados"

SEED = 2026
NOMINAL_Y = 32.0
BUDGET = 6          # disparos permitidos por episodio (restriccion de recursos)

# Banda del cono efectivo del arma a la distancia inicial (medida empiricamente)
CONE_HALF_WIDTH = 30.0
STRATUM_GAP = 60.0

POLICIES = ("nominal", "bearing")
SIGMAS = (0.0, 10.0)


@dataclass(frozen=True)
class Condition:
    name: str
    policy: str
    sigma: float
    stratum: str          # "D0" | "D1"
    description: str


CONDITIONS: tuple[Condition, ...] = (
    Condition("B0_en_cono", "nominal", 0.0, "D0",
              "Agente base, amenaza dentro del cono"),
    Condition("B1_fuera_cono", "nominal", 0.0, "D1",
              "Agente base, amenaza fuera del cono"),
    Condition("B2_fuera_ruido", "nominal", 10.0, "D1",
              "Agente base, fuera del cono + ruido"),
    Condition("REF_fuera", "bearing", 0.0, "D1",
              "Referencia servo visual, fuera del cono"),
    Condition("REF_fuera_ruido", "bearing", 10.0, "D1",
              "Referencia servo visual, fuera + ruido"),
)


# --------------------------------------------------------------------------- #
def offset_of(row: dict[str, Any]) -> float | None:
    """Desplazamiento lateral de la amenaza respecto de la posicion nominal."""
    if row["y0"] is None:
        return None
    return abs(row["y0"] - NOMINAL_Y)


def in_stratum(offset: float | None, stratum: str) -> bool:
    if offset is None:
        return False
    if stratum == "D0":
        return offset <= CONE_HALF_WIDTH
    if stratum == "D1":
        return offset >= STRATUM_GAP
    raise ValueError(f"estrato desconocido: {stratum}")


def mean_sd(values: list[float]) -> tuple[float, float]:
    """Media y desviacion estandar muestral (denominador n-1)."""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    mean = sum(values) / n
    if n < 2:
        return (mean, 0.0)
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return (mean, math.sqrt(variance))


def collect_pool(policy: str, sigma: float, pool: int) -> list[dict[str, Any]]:
    """Ejecuta el pool completo de episodios para una politica y un ruido."""
    cfg = AgentConfig(policy=policy, sigma_bearing=sigma, ammo_budget=BUDGET)
    print(f"[pool] policy={policy} sigma={sigma:g} episodios={pool} ...", flush=True)
    rows = run_batch(cfg, episodes=pool, seed=SEED)
    for row in rows:
        row["condition"] = f"pool_{policy}_s{int(sigma)}"
        row["offset"] = offset_of(row)
    return rows


def select(rows: list[dict[str, Any]], stratum: str, n: int) -> list[dict[str, Any]]:
    selected = [r for r in rows if in_stratum(r["offset"], stratum)]
    return selected[:n]


# --------------------------------------------------------------------------- #
def build_table(
    pools: dict[tuple[str, float], list[dict[str, Any]]],
    n_stratum: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Devuelve (filas por episodio, filas resumen)."""
    episode_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for cond in CONDITIONS:
        pool = pools[(cond.policy, cond.sigma)]
        chosen = select(pool, cond.stratum, n_stratum)
        if not chosen:
            print(f"[warn] condicion {cond.name}: sin episodios en el estrato")
            continue

        for row in chosen:
            record = dict(row)
            record["condition"] = cond.name
            record["description"] = cond.description
            record["stratum"] = cond.stratum
            episode_rows.append(record)

        n = len(chosen)
        k = sum(r["success"] for r in chosen)
        shots_fail = [r["shots"] for r in chosen if not r["success"]]
        dec_mean, dec_sd = mean_sd([r["decisions"] for r in chosen])
        sho_mean, sho_sd = mean_sd([r["shots"] for r in chosen])
        summary_rows.append(
            {
                "condition": cond.name,
                "policy": cond.policy,
                "sigma": cond.sigma,
                "stratum": cond.stratum,
                "description": cond.description,
                "n": n,
                "successes": k,
                "success_rate": k / n,
                "dec_mean": dec_mean,
                "dec_sd": dec_sd,
                "dec_min": min(r["decisions"] for r in chosen),
                "dec_max": max(r["decisions"] for r in chosen),
                "sho_mean": sho_mean,
                "sho_sd": sho_sd,
                "sho_min": min(r["shots"] for r in chosen),
                "sho_max": max(r["shots"] for r in chosen),
                "mean_shots_on_failures": (
                    sum(shots_fail) / len(shots_fail) if shots_fail else 0.0
                ),
                "n_ammo_out": sum(1 for r in chosen if r["outcome"] == "sin_municion"),
                "n_timeout": sum(1 for r in chosen if r["outcome"] == "timeout"),
                "n_death": sum(1 for r in chosen if r["outcome"] == "muerte"),
                "mean_offset": sum(r["offset"] for r in chosen) / n,
                "mean_damage": sum(
                    100.0 - (r["health_end"] if r["health_end"] is not None else 100.0)
                    for r in chosen
                ) / n,
            }
        )
    return episode_rows, summary_rows


def format_markdown(summary_rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Condicion | Politica | Estrato | sigma | n | Exito (k/n) | Decisiones (media +/- DE) | Disparos (media +/- DE) | Disparos en fallos | Sin municion |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summary_rows:
        lines.append(
            f"| `{row['condition']}` | {row['policy']} | {row['stratum']} "
            f"| {row['sigma']:g} | {row['n']} "
            f"| {row['success_rate']:.1%} ({row['successes']}/{row['n']}) "
            f"| {row['dec_mean']:.2f} +/- {row['dec_sd']:.2f} "
            f"| {row['sho_mean']:.2f} +/- {row['sho_sd']:.2f} "
            f"| {row['mean_shots_on_failures']:.2f} | {row['n_ammo_out']} |"
        )
    return "\n".join(lines)


def format_console(summary_rows: list[dict[str, Any]]) -> str:
    header = (
        f"{'condicion':<20}{'politica':<9}{'est':<4}{'sigma':>6}{'n':>5}"
        f"{'exito':>15}{'decisiones':>16}{'disparos':>16}"
    )
    lines = [header, "-" * len(header)]
    for row in summary_rows:
        lines.append(
            f"{row['condition']:<20}{row['policy']:<9}{row['stratum']:<4}"
            f"{row['sigma']:>6g}{row['n']:>5}"
            f"{row['success_rate']:>8.1%} {row['successes']:>2d}/{row['n']:<2d}"
            f"{row['dec_mean']:>9.2f}+-{row['dec_sd']:<5.2f}"
            f"{row['sho_mean']:>9.2f}+-{row['sho_sd']:<5.2f}"
        )
    return "\n".join(lines)


def offset_curve(pools: dict[tuple[str, float], list[dict[str, Any]]], bucket: int = 20) -> str:
    """Exito por tramo de desplazamiento, para inspeccion del efecto."""
    lines = []
    for policy in POLICIES:
        for sigma in SIGMAS:
            rows = pools[(policy, sigma)]
            buckets: dict[int, list[int]] = {}
            for row in rows:
                if row["offset"] is None:
                    continue
                key = int(row["offset"] // bucket) * bucket
                buckets.setdefault(key, []).append(row["success"])
            cells = " ".join(
                f"[{k:3d},{k + bucket:3d}):{sum(v) / len(v):.2f}"
                for k, v in sorted(buckets.items())
            )
            lines.append(f"{policy:<8} sigma={sigma:<4g} {cells}")
    return "\n".join(lines)


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "condition", "stratum", "description", "seed", "episode", "policy",
        "sigma", "theta", "ticks", "budget", "success", "outcome", "decisions",
        "shots", "y0", "abs_y0", "offset", "health_end", "ammo_end", "seconds",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_figure(summary_rows: list[dict[str, Any]], path: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[warn] matplotlib no disponible: {exc}")
        return False

    labels = [r["condition"] for r in summary_rows]
    values = [r["success_rate"] for r in summary_rows]
    colors = ["#2b6cb0" if r["policy"] == "nominal" else "#2f855a" for r in summary_rows]

    fig, ax = plt.subplots(figsize=(6.6, 3.2), dpi=200)
    ax.bar(labels, values, color=colors, width=0.6)
    for i, row in enumerate(summary_rows):
        ax.text(
            i,
            min(1.05, values[i] + 0.04),
            f"{values[i]:.1%} ({row['successes']}/{row['n']})",
            ha="center",
            fontsize=7,
        )
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Tasa de exito")
    ax.set_title("Agente base vs referencia", fontsize=9)
    ax.tick_params(axis="x", labelsize=7, rotation=15)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=int, default=400, help="episodios por pool")
    parser.add_argument("--n-stratum", type=int, default=40, help="episodios por condicion")
    parser.add_argument("--quick", action="store_true", help="smoke test")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    if args.quick:
        args.pool = 60
        args.n_stratum = 8

    pools: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for policy in POLICIES:
        for sigma in SIGMAS:
            pools[(policy, sigma)] = collect_pool(policy, sigma, args.pool)

    episode_rows, summary_rows = build_table(pools, args.n_stratum)

    print("\n=== curva exito vs desplazamiento (pool completo) ===")
    print(offset_curve(pools))

    print("\n=== resultados por condicion ===")
    print(format_console(summary_rows))

    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(episode_rows, args.out / "episodios.csv")
    (args.out / "resumen.md").write_text(
        "# Resultados del agente base\n\n"
        f"Semilla={SEED}, pool={args.pool} episodios por politica/ruido, "
        f"n={args.n_stratum} por condicion, theta=4 grados, ticks=2, "
        "presupuesto=6 disparos, horizonte=50 decisiones.\n\n"
        + format_markdown(summary_rows)
        + "\n\n## Curva exito vs desplazamiento\n\n```\n"
        + offset_curve(pools)
        + "\n```\n",
        encoding="utf-8",
    )
    made = make_figure(summary_rows, args.out / "resultados.png")

    print(f"\nArtefactos en {args.out}")
    print("  episodios.csv, resumen.md" + (", resultados.png" if made else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
