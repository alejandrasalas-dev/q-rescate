# Quantum Probability Lab — Qiskit Fall Fest 2026

**Nueva dirección: categoría EdTech.** Una experiencia educativa para aprender cómo estimar probabilidades con **Monte Carlo clásico** y **Quantum Amplitude Estimation (QAE)** con Qiskit.

## Qué aprenderá quien juegue

- Elegir un escenario de probabilidad, predecir un resultado y comprobarlo.
- Ajustar número de muestras y observar errores de Monte Carlo.
- Experimentar con **Iterative Amplitude Estimation (IQAE)** mediante un circuito pequeño de Qiskit.
- Comparar estimaciones, intervalos, recursos utilizados y límites de cada método.
- Como objetivo de diseño: niveles, feedback, retos repetibles y progresión para motivar su uso frecuente.

## Importante: lo demostrado frente a lo teórico

QAE dispone de una **ventaja cuadrática teórica en complejidad de consultas** bajo determinadas condiciones. No afirmamos que el simulador cuántico corra más rápido ni que preparar datos cuánticos sea gratuito.

El ejemplo educativo usa una probabilidad `p` **conocida y codificada en un circuito RY de un qubit**. Es una simulación didáctica para explicar el algoritmo y su estimación, **no una predicción real ni una demostración end-to-end de ventaja cuántica**.

Las consultas al oráculo Grover reportadas por Qiskit no son directamente equivalentes a las muestras clásicas; se etiquetan por separado y no se grafican como si fueran la misma unidad.

## Probar el experimento

```bash
python -m pip install -r requirements-edtech.txt
python -m pytest edtech/tests -q
python -m edtech.experiment --probability 0.2 --samples 256 --epsilon 0.15 --shots 100 --seed 42
```

La ejecución de GitHub Actions en `feat/edtech-qae` valida la prueba y exporta un JSON. **No afirmar éxito del nuevo experimento hasta revisar el workflow.**

## Entregables del equipo

- **Angelo:** fundamento matemático, oráculos/Grover y condiciones de ventaja teórica.
- **Carlos:** experimento de Monte Carlo e IQAE, pruebas y métricas reproducibles.
- **Alexia:** actividades educativas, niveles, experiencia visual y pitch en español.
- **Ale:** integración, CI, control de alcance y entrega de archivos.

La app interactiva completa está **pendiente**. El código presente es un prototipo experimental.

## Trabajo anterior conservado

Q-Rescate / Q-Route fue la propuesta original de optimización de rutas con QAOA. Permanece en `feat/qaoa-poc`, `feat/real-routing` y otras ramas existentes; no está fusionada ni desplegada. **No confundir aquellos benchmarks con las pruebas EdTech.**

## Referencias técnicas

- [Qiskit: API IterativeAmplitudeEstimation](https://qiskit-community.github.io/qiskit-algorithms/stubs/qiskit_algorithms.IterativeAmplitudeEstimation.html)
- [Qiskit Finance: tutorial Amplitude Estimation](https://qiskit-community.github.io/qiskit-finance/tutorials/00_amplitude_estimation.html)
- [Investigación original de IQAE](https://www.nature.com/articles/s41534-021-00379-1)
