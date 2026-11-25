# Agente base — Taller 5 (limpieza de ángulos, ViZDoom)

Agente **sin aprendizaje** (baseline) para el escenario `limpieza_angulos`, más el
runner que produce la evidencia experimental del informe.

## 1. Requisitos

- Python 3.9 o superior
- ViZDoom 1.3.0 (`pip install vizdoom`)
- Opcional, sólo para la figura: `matplotlib`

Verificación rápida del entorno:

```bash
python -c "import vizdoom; print(vizdoom.__version__)"
```

## 2. Reproducción mínima

Todo se ejecuta desde esta carpeta (`sem/proyecto/`).

```bash
# a) un episodio del agente base, con ventana, para inspección visual
python baseline_agent.py --episodes 1 --policy nominal --render --verbose

# b) tabla de resultados del informe (≈3 min en CPU, sin GPU)
python run_experiments.py
```

Salidas de (b) en `resultados/`:

| Archivo | Contenido |
|---|---|
| `episodios.csv` | una fila por episodio (condición, semilla, `y0`, desenlace, decisiones, disparos) |
| `resumen.md` | tabla agregada (éxito como conteo $k/n$, métricas continuas como media ± desviación estándar) y curva éxito vs desplazamiento |
| `resultados.png` | figura de barras con la tasa de éxito por condición |

Semilla fija (`SEED = 2026`), por lo que los números de la tabla son reproducibles
bit a bit en la misma versión de ViZDoom.

## 3. Estructura

```
proyecto/
├── baseline_agent.py      # agente base + bucle de episodios + CLI
├── run_experiments.py     # diseño experimental, estratificación y agregación
├── resultados/            # artefactos generados
└── scenarios/
    ├── limpieza_angulos.cfg
    └── basic.wad
```

## 4. Política del agente base

Cuatro reglas, evaluadas en orden (adaptación de la política heurística del Taller 4):

| # | Condición | Acción |
|---|---|---|
| R1 | no hay amenaza visible en el buffer de etiquetas | `TURN_RIGHT` (barrido) |
| R2 | `salud < 40` | `MOVE_BACKWARD` (retirada) |
| R3 | `|error angular| > θ_aim` | girar hacia la referencia |
| R4 | en otro caso | `ATTACK` |

La **referencia** del error angular es la clave del baseline:

- `--policy nominal` (**baseline**): apunta a la posición nominal a priori
  `w_k = (0, 32)`, centroide de la región de aparición de la amenaza. La
  percepción (`V_threat`) se usa sólo como compuerta para decidir *si* dispara,
  nunca para corregir el rumbo.
- `--policy bearing` (**referencia superior**, no es el baseline): apunta al
  rumbo percibido de la amenaza (servo visual). Sirve para comprobar que la
  métrica es sensible y que la brecha es cerrable.

## 5. Parámetros

| Parámetro | CLI | Valor | Rol |
|---|---|---|---|
| umbral de alineación | `--theta` | 4° | regla R3 |
| tics por decisión | `--ticks` | 2 | granularidad de control |
| horizonte | `--horizon` | 50 decisiones | corte por timeout |
| presupuesto de munición | `--budget` | 6 disparos | restricción de recursos |
| ruido angular | `--sigma` | 0° / 10° | incertidumbre de orientación (Taller 3) |
| semilla | `--seed` | 2026 | reproducibilidad |

## 6. Diseño experimental (resumen)

- **Factor 1 — desplazamiento lateral** de la amenaza respecto de `w_k`:
  `D0` = dentro del cono efectivo del arma (`offset ≤ 30`),
  `D1` = fuera del cono (`offset ≥ 60`). La banda `30 < offset < 60` se excluye
  para no mezclar el borde.
- **Factor 2 — ruido** en la estimación del error angular: `σ ∈ {0°, 10°}`.
- **n = 40** episodios por condición, balanceados por estrato.
- **Comparación pareada**: la posición inicial de la amenaza es función
  determinista de `(semilla, índice de episodio)`, independiente de la política
  y del ruido (verificado empíricamente), de modo que todas las condiciones
  enfrentan exactamente los mismos episodios.

## 7. Métricas

- **Principal**: tasa de éxito (episodio termina con el objetivo eliminado).
- **Secundarias**: decisiones hasta el desenlace, disparos consumidos,
  disparos desperdiciados en episodios fallidos, desenlace
  (`exito` / `sin_municion` / `timeout` / `muerte`).

## 8. Notas de implementación

- `game.set_seed()` se invoca **antes** de `init()`; de lo contrario no tiene efecto.
- El buffer de etiquetas (`set_labels_buffer_enabled(True)`) contiene sólo objetos
  visibles, por lo que se usa como indicador de `V_threat`.
- El timeout se controla con un contador propio de decisiones (horizonte); el
  timeout del motor se deja holgado para que «episodio terminado» signifique
  siempre muerte del objetivo o del jugador.
- `KILLCOUNT` no es fiable en este WAD (el guion ACS no lo actualiza); el éxito se
  detecta por finalización del episodio sin muerte del jugador.
