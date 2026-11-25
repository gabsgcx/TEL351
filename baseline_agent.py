#!/usr/bin/env python3
"""Agente base (sin aprendizaje) para el escenario `limpieza_angulos` (ViZDoom).

Implementa una adaptacion de la politica heuristica del Taller 4 sobre el
escenario `scenarios/limpieza_angulos.cfg` + `scenarios/basic.wad`.

Politica (4 reglas, en orden de prioridad):

    R1  si no hay amenaza visible          -> TURN_RIGHT   (barrido de busqueda)
    R2  si salud < retreat_health          -> MOVE_BACKWARD (retirada defensiva)
    R3  si |error angular| > theta_aim     -> girar hacia la referencia
    R4  en otro caso                       -> ATTACK

La "referencia" sobre la que se calcula el error angular depende de `policy`:

    policy="nominal"  (BASELINE)  apunta a la posicion nominal a priori
                                  w_k = (nominal_x, nominal_y), que corresponde
                                  al centroide de la region de aparicion de la
                                  amenaza. NO cierra el lazo sobre el rumbo
                                  percibido: usa la percepcion (V_threat) solo
                                  como compuerta para decidir SI dispara.
    policy="bearing"  (REFERENCIA) apunta al rumbo percibido de la amenaza
                                  (servo visual). No es el baseline: se incluye
                                  como cota superior para verificar que la
                                  metrica es sensible y que la brecha es
                                  cerrable.

Uso:
    python baseline_agent.py --episodes 40 --seed 2026 --policy nominal
    python baseline_agent.py --episodes 5 --policy nominal --render

Salida: resumen por consola y, opcionalmente, un CSV con una fila por episodio.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import vizdoom as vzd

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "scenarios" / "limpieza_angulos.cfg"

# Orden de botones declarado en scenarios/limpieza_angulos.cfg
BUTTONS = [
    "MOVE_FORWARD",
    "MOVE_BACKWARD",
    "MOVE_LEFT",
    "MOVE_RIGHT",
    "TURN_LEFT",
    "TURN_RIGHT",
    "ATTACK",
    "USE",
]
BUTTON_INDEX = {name: i for i, name in enumerate(BUTTONS)}

# Nombres de accion usados por la politica
IDLE = "IDLE"
FORWARD = "MOVE_FORWARD"
BACKWARD = "MOVE_BACKWARD"
TURN_LEFT = "TURN_LEFT"
TURN_RIGHT = "TURN_RIGHT"
ATTACK = "ATTACK"

TARGET_NAME = "Cacodemon"


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def action_vector(name: str) -> list[int]:
    """Convierte un nombre de accion en el vector binario que espera ViZDoom."""
    vec = [0] * len(BUTTONS)
    if name != IDLE:
        vec[BUTTON_INDEX[name]] = 1
    return vec


def wrap_deg(angle: float) -> float:
    """Normaliza un angulo a (-180, 180]."""
    wrapped = (angle + 180.0) % 360.0 - 180.0
    return 180.0 if wrapped == -180.0 else wrapped


def find_target(state: Any) -> tuple[bool, float, float]:
    """Devuelve (visible, x, y) de la amenaza a partir del buffer de etiquetas.

    El buffer de etiquetas solo contiene objetos efectivamente visibles en el
    cuadro, por lo que sirve como indicador de V_threat (creencia visual).
    """
    for label in state.labels or []:
        name = label.object_name or ""
        if TARGET_NAME in name:
            return True, float(label.object_position_x), float(label.object_position_y)
    return False, math.nan, math.nan


# --------------------------------------------------------------------------- #
# Configuracion del agente
# --------------------------------------------------------------------------- #
@dataclass
class AgentConfig:
    policy: str = "nominal"       # "nominal" (baseline) | "bearing" (referencia)
    theta_aim: float = 4.0        # umbral de alineacion para disparar [grados]
    ticks: int = 2                # tics de simulacion por decision
    horizon: int = 50             # maximo de decisiones por episodio
    ammo_budget: int = 6          # disparos permitidos por episodio
    retreat_health: float = 40.0  # umbral de salud para la regla de retirada
    sigma_bearing: float = 0.0    # ruido gaussiano en el error angular [grados]
    nominal_x: float = 0.0        # posicion nominal a priori w_k
    nominal_y: float = 32.0

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Politica
# --------------------------------------------------------------------------- #
def policy_action(obs: dict[str, float], cfg: AgentConfig, rng: random.Random) -> str:
    """Devuelve la accion de la politica para una observacion dada."""
    # R1: sin evidencia visual de amenaza -> barrido
    if not obs["visible"]:
        return TURN_RIGHT

    # R2: retirada defensiva
    if obs["health"] < cfg.retreat_health:
        return BACKWARD

    if cfg.policy == "bearing":
        ref_x, ref_y = obs["target_x"], obs["target_y"]
    else:
        ref_x, ref_y = cfg.nominal_x, cfg.nominal_y

    bearing = math.degrees(math.atan2(ref_y - obs["py"], ref_x - obs["px"]))
    err = wrap_deg(bearing - obs["angle"])
    if cfg.sigma_bearing > 0.0:
        err += rng.gauss(0.0, cfg.sigma_bearing)

    # R3: alineacion
    if abs(err) > cfg.theta_aim:
        return TURN_LEFT if err > 0.0 else TURN_RIGHT

    # R4: alineado -> disparar
    return ATTACK


# --------------------------------------------------------------------------- #
# Ejecucion de episodios
# --------------------------------------------------------------------------- #
def make_game(cfg: AgentConfig, seed: int, config_path: Path, render: bool = False):
    """Crea e inicializa el juego. `set_seed` debe llamarse antes de `init`."""
    game = vzd.DoomGame()
    game.load_config(str(config_path))
    game.set_window_visible(render)
    game.set_mode(vzd.Mode.PLAYER)
    game.set_labels_buffer_enabled(True)
    game.set_objects_info_enabled(True)
    # El timeout propio (cfg.horizon) es el que manda; el del motor queda holgado
    # para que "episodio terminado" signifique siempre muerte del objetivo o del
    # jugador, nunca agotamiento de tiempo del motor.
    game.set_episode_timeout(cfg.horizon * cfg.ticks * 4 + 500)
    game.set_seed(seed)
    game.init()
    return game


def run_episode(
    game: Any,
    cfg: AgentConfig,
    seed: int,
    episode_index: int,
    render: bool = False,
) -> dict[str, Any]:
    """Ejecuta un episodio y devuelve un registro con las metricas."""
    # RNG del ruido: determinista por (semilla, indice de episodio), de modo que
    # dos politicas distintas enfrentan exactamente el mismo ruido.
    rng = random.Random(seed * 100_003 + episode_index)

    game.new_episode()

    decisions = 0
    shots = 0
    y0 = math.nan
    last_health = math.nan
    last_ammo = math.nan
    outcome = "timeout"
    t0 = time.perf_counter()

    while decisions < cfg.horizon:
        if game.is_episode_finished():
            break
        state = game.get_state()
        if state is None:
            break

        px, py, _pz, angle, health, ammo, _kills = (
            float(v) for v in state.game_variables
        )
        last_health, last_ammo = health, ammo

        visible, tx, ty = find_target(state)
        if visible and math.isnan(y0):
            y0 = ty

        obs = {
            "visible": visible,
            "px": px,
            "py": py,
            "angle": angle,
            "health": health,
            "ammo": ammo,
            "target_x": tx,
            "target_y": ty,
        }
        action = policy_action(obs, cfg, rng)

        if action == ATTACK:
            if shots >= cfg.ammo_budget:
                outcome = "sin_municion"
                break
            shots += 1

        game.make_action(action_vector(action), cfg.ticks)
        decisions += 1

        if render:
            time.sleep(0.01)

    if outcome != "sin_municion":
        if game.is_episode_finished():
            try:
                dead = bool(game.is_player_dead())
            except Exception:  # pragma: no cover - defensivo
                dead = not (last_health > 0.0)
            outcome = "muerte" if dead else "exito"
        else:
            outcome = "timeout"

    return {
        "seed": seed,
        "episode": episode_index,
        "policy": cfg.policy,
        "sigma": cfg.sigma_bearing,
        "theta": cfg.theta_aim,
        "ticks": cfg.ticks,
        "budget": cfg.ammo_budget,
        "success": int(outcome == "exito"),
        "outcome": outcome,
        "decisions": decisions,
        "shots": shots,
        "y0": None if math.isnan(y0) else round(y0, 3),
        "abs_y0": None if math.isnan(y0) else round(abs(y0), 3),
        "health_end": None if math.isnan(last_health) else round(last_health, 1),
        "ammo_end": None if math.isnan(last_ammo) else round(last_ammo, 1),
        "seconds": round(time.perf_counter() - t0, 3),
    }


def run_batch(
    cfg: AgentConfig,
    episodes: int,
    seed: int,
    config_path: Path = DEFAULT_CONFIG,
    render: bool = False,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """Ejecuta `episodes` episodios consecutivos con una unica instancia del juego."""
    game = make_game(cfg, seed, config_path, render=render)
    rows = []
    try:
        for index in range(episodes):
            row = run_episode(game, cfg, seed, index, render=render)
            rows.append(row)
            if verbose:
                print(
                    f"  ep {index:03d}  y0={row['y0']}  {row['outcome']:<13}"
                    f" dec={row['decisions']:2d} shots={row['shots']:2d}"
                )
    finally:
        game.close()
    return rows


# --------------------------------------------------------------------------- #
# Resumen
# --------------------------------------------------------------------------- #
def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {}
    successes = sum(r["success"] for r in rows)
    return {
        "n": n,
        "success_rate": successes / n,
        "mean_decisions": sum(r["decisions"] for r in rows) / n,
        "mean_shots": sum(r["shots"] for r in rows) / n,
        "n_exito": sum(1 for r in rows if r["outcome"] == "exito"),
        "n_timeout": sum(1 for r in rows if r["outcome"] == "timeout"),
        "n_sin_municion": sum(1 for r in rows if r["outcome"] == "sin_municion"),
        "n_muerte": sum(1 for r in rows if r["outcome"] == "muerte"),
    }


def print_summary(rows: list[dict[str, Any]], cfg: AgentConfig) -> None:
    s = summarize(rows)
    print(
        f"policy={cfg.policy} sigma={cfg.sigma_bearing:g} budget={cfg.ammo_budget} "
        f"theta={cfg.theta_aim:g} ticks={cfg.ticks}"
    )
    print(
        f"  n={s['n']}  exito={s['success_rate']:.2%}  "
        f"decisiones={s['mean_decisions']:.2f}  disparos={s['mean_shots']:.2f}"
    )
    print(
        f"  desenlaces: exito={s['n_exito']} timeout={s['n_timeout']} "
        f"sin_municion={s['n_sin_municion']} muerte={s['n_muerte']}"
    )
    ys = [r["abs_y0"] for r in rows if r["abs_y0"] is not None]
    if ys:
        print(f"  |y0| medio={sum(ys) / len(ys):.1f}  min={min(ys):.1f}  max={max(ys):.1f}")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agente base (sin aprendizaje) para limpieza_angulos."
    )
    parser.add_argument("--episodes", type=int, default=40, help="numero de episodios")
    parser.add_argument("--seed", type=int, default=2026, help="semilla del motor")
    parser.add_argument(
        "--policy", choices=["nominal", "bearing"], default="nominal",
        help="nominal = baseline (apunta a w_k); bearing = referencia (servo visual)",
    )
    parser.add_argument("--theta", type=float, default=4.0, help="umbral de alineacion [grados]")
    parser.add_argument("--ticks", type=int, default=2, help="tics por decision")
    parser.add_argument("--horizon", type=int, default=50, help="maximo de decisiones")
    parser.add_argument("--budget", type=int, default=6, help="disparos permitidos")
    parser.add_argument("--sigma", type=float, default=0.0, help="ruido angular [grados]")
    parser.add_argument("--nominal-x", type=float, default=0.0)
    parser.add_argument("--nominal-y", type=float, default=32.0)
    parser.add_argument("--csv", type=Path, default=None, help="ruta del CSV de salida")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--render", action="store_true", help="mostrar la ventana del juego")
    parser.add_argument("--verbose", action="store_true", help="una linea por episodio")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cfg = AgentConfig(
        policy=args.policy,
        theta_aim=args.theta,
        ticks=args.ticks,
        horizon=args.horizon,
        ammo_budget=args.budget,
        sigma_bearing=args.sigma,
        nominal_x=args.nominal_x,
        nominal_y=args.nominal_y,
    )
    rows = run_batch(
        cfg,
        episodes=args.episodes,
        seed=args.seed,
        config_path=args.config,
        render=args.render,
        verbose=args.verbose,
    )
    print_summary(rows, cfg)
    if args.csv:
        write_csv(rows, args.csv)
        print(f"CSV escrito en {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
