# Q-Route: demostración cuántica de impacto, sin exagerar la ventaja

**Fecha:** 24 de octubre de 2026. **Categoría:** Algoritmos y aplicaciones. **Estado:** simulación Qiskit ejecutada y validada en GitHub Actions.

## Cambio de enfoque para el pitch

En vez de intentar demostrar que QAOA ejecutado en CPU es más rápido que un solucionador clásico exacto, mostraremos **dos resultados reales y diferentes** sobre el mismo problema:

1. **Mejora de calidad frente a una estrategia clásica sencilla:** el algoritmo QAOA encontró una asignación de costo **12.708,71**, frente a **13.448,82** de la heurística clásica `greedy`. La mejora relativa frente al costo de `greedy` es **5,50 %**.
2. **Amplificación de probabilidades con Grover:** mediante un oráculo de cuatro qubits que reconoce asignaciones factibles y de costo inferior a `greedy`, Qiskit midió un **95,90 %** de éxito tras tres iteraciones, frente al **5,71 %** observado al medir la superposición inicial sin Grover.

**Ninguno de estos hallazgos demuestra una ventaja cuántica práctica general**: el método exacto clásico y la búsqueda local también obtuvieron el costo **12.708,71** y lo hicieron mucho más rápido en el problema pequeño.

## Experimento exacto

- Caso: red vial sintética de 100 nodos, extensión ilustrativa de **1.800 km**, cierre de vías, dos vehículos con depósitos distintos, cuatro destinos, capacidad de dos por vehículo, prioridades y penalización por llegar tarde.
- Qiskit usa **cuatro qubits**. Cada bit indica a qué vehículo se asigna un destino; el orden de visita dentro de cada vehículo se optimiza **clásicamente**.
- Posibles cadenas de cuatro bits: **16**.
- Asignaciones que respetan la capacidad: **6**.
- Asignaciones de costo estrictamente menor que `greedy`: **1** (máscara decimal 5, bits en orden little-endian `[1,0,1,0]`).
- El umbral se deriva **del costo greedy**, no del óptimo exacto.
- Qiskit construye un **oráculo de fase** que marca esa solución y el operador de Grover amplifica su amplitud.
- Simulador: `StatevectorSampler`, 2048 mediciones para cada configuración, semilla 42, sin QPU IBM físico.

## Resultados observados

| Iteraciones de Grover | Consultas al oráculo por medición | Probabilidad teórica ideal | Éxitos medidos / 2048 | Porcentaje medido |
|---:|---:|---:|---:|---:|
| 0 | 0 | 6,25 % | 117 | **5,71 %** |
| 1 | 1 | 47,27 % | 957 | **46,73 %** |
| 2 | 2 | 90,84 % | 1867 | **91,16 %** |
| 3 | 3 | 96,13 % | 1964 | **95,90 %** |

La probabilidad ideal se calcula con `sin²[(2r+1)·arcsin(√(1/16))]` para `r` iteraciones. Se verificó tanto mediante `Statevector` como con conteos de `StatevectorSampler`.

**Comparación alternativa contra azar condicionado a rutas factibles:** una elección uniforme entre seis asignaciones válidas tiene probabilidad de acierto 1/6 = **16,67 %**; en tres intentos independientes con reemplazo, **42,13 %** de acertar al menos una vez. Esto es una **línea base de búsqueda aleatoria**, no un solver clásico competitivo ni una comparación directa de coste de implementación de oráculos.

## Advertencia científica CRÍTICA

**El oráculo de Grover se compiló desde una tabla de verdad calculada clásicamente:** el código revisa **las 16 combinaciones** y evalúa el costo de las **seis factibles** para construir las fases del circuito. Por tanto, el preprocesamiento clásico **ya ha comprobado las asignaciones candidatas**. No se puede decir que Grover resolvió nuestro problema más eficazmente que el clásico de extremo a extremo.

El objetivo de este circuito es demostrar **amplificación cuántica de probabilidades en el modelo de consultas al oráculo**. Construir un oráculo reversible eficiente que compruebe restricciones y costos **sin enumerar previamente soluciones** es una línea de trabajo futuro no implementada. La búsqueda aleatoria no es representativa de los algoritmos clásicos de optimización eficientes.

Tampoco hay evidencia de que un circuito de más qubits dé mejor calidad o menor tiempo. El hardware cuántico real introduce ruido y gastos de transpilación/medición ausentes en el simulador ideal. No usar 1.800 km de escala geográfica como si 1.800 km estuviesen representados por qubits.

## Qué podemos decir al jurado

> «Nuestro proyecto estudia cómo aprovechar optimización híbrida para asignar recursos cuando existen destinos, bloqueos y restricciones. Con Qiskit QAOA redujimos **5,5 %** el costo frente a una regla clásica sencilla, aunque el mejor clásico también alcanzó ese óptimo. Para explicar qué añade la computación cuántica, programamos además Grover: una asignación mejor pasó de aproximadamente **6 %** a **96 %** de probabilidad de ser medida en un circuito ideal. Es un efecto real de amplificación cuántica en simulación; **todavía no es una ventaja práctica de extremo a extremo**, porque preparar el oráculo fue clásico. Nuestra contribución es comparar soluciones, validar restricciones y explicar con honestidad la oportunidad y los límites».

## Validación y trazabilidad

- **[Ejecución GitHub Actions #40125292411](https://github.com/alejandrasalas-dev/q-rescate/actions/runs/40125292411): correcta.** **29 tests aprobados**, artefacto `grover-impact-evidence` con JSON completo.
- Código: `experiments/grover_impact.py`.
- Tests: `tests/test_grover_impact.py` y los del modelo de múltiples recursos.
- Referencia oficial: [Tutorial Grover de IBM Quantum](https://quantum.cloud.ibm.com/docs/en/tutorials/grovers-algorithm).

### Revisiones del equipo

- **Angelo:** validar la lógica del oráculo, las seis asignaciones factibles, la fórmula de amplificación y el alcance del modelo de consultas.
- **Carlos:** revisar que QAOA, exacto, greedy y búsqueda local compartan función de costo; verificar que el JSON de Grover se interpreta como distribución de mediciones, no como velocidad/ventaja final.
- **Alexia:** visualización «antes/después de amplificación» **con etiqueta visible** `simulación ideal / no ventaja práctica demostrada`, más comparación de costo QAOA vs greedy vs exacto.
- **Ale:** integración y acceso a demo; ningún merge/deploy/publicación sin aprobación.
