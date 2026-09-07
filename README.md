# Agente Autónomo para Limpieza de Ángulos (ViZDoom)

Este repositorio contiene el código fuente, configuraciones y documentación del proyecto semestral para la asignatura **Agentes Inteligentes**. 

El objetivo general del proyecto es desarrollar un agente autónomo capaz de navegar en un entorno tipo shooter táctico para realizar la tarea de "limpieza de ángulos". El agente debe verificar puntos de interés estratégicos (esquinas, coberturas, entradas) de forma eficiente, minimizando el tiempo de exposición al riesgo y, en etapas posteriores, adaptándose a la presencia de enemigos.

---

## 🛠️ Requisitos e Instalación

El entorno principal del proyecto está basado en **ViZDoom**. Para ejecutar los scripts en un entorno local, se requiere **Python 3.8+** y las dependencias detalladas en el archivo `requirements.txt`.

Instalación básica:
```bash
pip install -r requirements.txt
```
## Progreso del Proyecto

### Taller 1: Definición del Problema
Se definió teóricamente el problema de navegación espacial 3D, el espacio de soluciones y las dimensiones del entorno.

### Taller 2: Selección de Plataforma y Setup
Evaluación de frameworks (Counter-Strike 1.6, DeepMind Lab, ViZDoom). Se seleccionó ViZDoom por su API nativa en Python, determinismo y soporte para escenarios personalizados.
* **Scripts de validación desarrollados:**
  1. test_vizdoom.py: Prueba de inicialización del motor y movimiento lineal.
  2. test_movement.py: Ejecución de secuencias predefinidas de movimiento y lectura del vector espacial (X, Y, Z) y ángulo.
  3. test_all_controls.py: Test exhaustivo de las 8 acciones discretas (movimientos, rotación, ataque, uso) y validación del impacto en las variables de estado (ej. consumo de munición).

#### Evidencia Técnica (Taller 2)
Como respaldo de la viabilidad técnica de ViZDoom, se adjuntan las capturas de la correcta ejecución de los scripts de prueba:

* **Renderizado del Entorno:** https://github.com/user-attachments/assets/caa2da9e-f1b1-47a8-b457-7a83b9e75f6e
* **Logs de Consola y Estado:** [Ver capturas de la consola]() *(Demuestra la extracción exitosa de POSITION_X/Y/Z, ANGLE, HEALTH y AMMO2 utilizando el método game.get_state())*.

---
**Autora:** Gabriela González
**Universidad Técnica Federico Santa María**
