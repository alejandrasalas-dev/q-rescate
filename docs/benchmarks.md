# Evaluación experimental de rutas dirigidas con QAOA

## Alcance y procedencia

Trabajo de Carlos para el issue #6, desde `feat/real-routing`, commit base
`a1676df07fbfa5fe3d8bd9002d8d1989eb0114de`. Se evalúa el TSP dirigido con hospital
fijo: visitar cada destino de servicio una vez y regresar al hospital. No se
modela asignación de múltiples ambulancias, capacidad hospitalaria, prioridades
médicas ni círculos sobre un mapa. Los datos son sintéticos y no representan
condiciones actuales de El Niño ni decisiones operativas.

La red tiene tiempos asimétricos. Dijkstra construye una matriz dirigida de
caminos habilitados. Los tres métodos usan exactamente esa matriz, registrada
con SHA-256. El escenario `bridge_closed` retira dos aristas. `flood_risk` agrega
penalizaciones deterministas a ciertos tramos: no estima probabilidades.
El orden de servicio del TSP no implica que el trayecto físico más corto no
pueda atravesar otro destino antes de atenderlo.

## Reproducción

```bash
python -m pip install -r requirements.txt
python -m pytest tests/test_routing.py -q
python routing.py --max-qubits 9
python -m pytest -q
python experiments/benchmark_reliability.py --seeds 3 7 42 --max-qubits 9 --timeout-seconds 120 --total-seconds 900 --output experiments/results/reliability.json
```

Para recrear las versiones observadas, en un entorno virtual nuevo:

```bash
python -m pip install -r experiments/results/requirements-observed.txt
```

Las versiones fijadas son dependencias directas; no constituyen un lock completo
transitivo. JSON incluye Python, plataforma, arquitectura, CPU lógica,
versiones, parámetros, commit base y hashes del script y de `routing.py`.
El árbol de trabajo estaba modificado durante las mediciones; los hashes
identifican el código experimental. Reproducibilidad de configuración no implica
igualdad exacta de duración o de resultados entre plataformas/versiones.

## Diseño del experimento

- Casos: normal con 2 y 3 destinos, puente cerrado con 3, riesgo con 3.
- Control de recursos: 4 destinos equivalen a 16 qubits y se omiten siempre.
- Codificación por posición: n destinos producen n² qubits; 2 → 4, 3 → 9.
- Semillas: 3, 7 y 42; QAOA `reps=1`, COBYLA `maxiter=35`, 512 shots.
- Las semillas afectan inicialización/muestreo; las matrices no se aleatorizan.
- Cada ejecución cuántica ocurre en un subproceso con plazo máximo de 120 s.
- Presupuesto global de fase experimental de 900 s. Los omitidos quedan registrados.
- Cada controlador procesa los casos secuencialmente, con límites de un hilo para BLAS/OpenMP en trabajadores. El piloto y parte de la reanudación coincidieron temporalmente; no se usan sus tiempos para inferir aceleración.
- Se escribe un checkpoint tras cada ejecución, incluso errores y timeouts.
- Al alcanzar `maxiter`, COBYLA puede devolver el mejor intento sin convergencia;
  el resultado de ruta no prueba convergencia del optimizador. La función actual
  `qaoa_tour` no exporta el historial ni el estado completo de COBYLA.

La enumeración exacta evalúa n! recorridos y es una referencia más fuerte que
greedy. No se introdujo un nuevo modelo QUBO ni se modificaron sus penalizaciones;
cualquier revisión del modelo debe coordinarse con Angelo.

## Métricas y lectura correcta

1. **Validez**: permutación de todos los destinos; salida y regreso al hospital
   se incluyen al calcular el costo. Se recalcula el costo, no se confía sólo
   en la bandera del solver.
2. **Calidad**: costo del recorrido original, sin penalizaciones del QUBO.
3. **Gap**: `100 * (costo - óptimo) / abs(óptimo)`. Con referencia cero, gap cero
   si ambos costos son cero; en otro caso es indefinido (`null`).
4. **Fiabilidad**: fracción de ejecuciones válidas y óptimas entre las semillas
   intentadas, separando errores, timeouts y omitidos. Tres semillas ofrecen
   evidencia limitada; no permiten generalizar a instancias grandes.
5. **Duración**: `runtime_seconds` del solver incluye construcción del modelo y
   optimización local. `wall_seconds` del trabajador añade inicio/importaciones.
   No equivale a tiempo de QPU. Los tiempos clásicos excluyen el preprocesamiento
   común de caminos, que también queda fuera de `qaoa_tour`.
6. **Recursos**: qubits de decisión, profundidad lógica y shots configurados;
   `reps` no equivale a profundidad física de un circuito transpilado.

`MinimumEigenOptimizer` devuelve su selección procesada; no se ha modificado
ese comportamiento. La proporción de ejecuciones óptimas no es una probabilidad
por shot. No se inventan conteos ni se reparan rutas inválidas con el óptimo.

El piloto inicial usó 60 s por ejecución y presupuesto global de 360 s. Se conserva
en `pilot_60s.json`; tras observar timeouts se reanudó con 120/900 s.
`--resume-from experiments/results/pilot_60s.json` reutiliza sólo resultados
completos con idéntica matriz, parámetros y hash de `routing.py`; los resultados
anteriores quedan embebidos en `previous_run`. Los intentos activos sin resultado
no se consideran éxitos.

## Pruebas automatizadas y revisión experimental

Las pruebas originales de rutas aprobaron: **17/17**. La suite ampliada comprobó
**47/47** pruebas, incluidas las del prototipo anterior de asignaciones.
Las 42 pruebas específicas de rutas y evaluación incluyen:

- Energía QUBO igual al costo real para todas las permutaciones válidas de 2 y
  3 destinos, en los tres escenarios.
- Todas las cadenas binarias inválidas de esos modelos tienen energía mayor
  que el óptimo válido con las penalizaciones actuales.
- Recorridos inválidos, costos inconsistentes y matrices distintas se rechazan.
- Decodificación rechaza valores fraccionarios, no finitos y enteros no binarios.
  Se corrigió el caso `[-1, 2, 2, -1]`, que antes podía pasar las sumas de filas
  y columnas. No cambia el QUBO ni los resultados binarios válidos.
- Costos dirigidos no se simetrizan, gap y referencia cero se tratan explícitamente.
- Guardas de qubits y registro de timeout funcionan sin lanzar simulaciones grandes.

Estos tests no prueban que QAOA encuentre siempre el óptimo. Las ejecuciones reales
se guardan por separado y deben revisarse junto con el informe.

## Monte Carlo

Monte Carlo no forma parte del algoritmo cuántico actual. El muestreo de
mediciones de QAOA no es un módulo de simulación climática Monte Carlo.
Una ampliación futura podría generar clásicamente escenarios de bloqueos o
variaciones de tiempos usando distribuciones justificadas, y volver a resolver
cada escenario. Necesitaría registrar las distribuciones, correlaciones, semillas
y fuentes; no asumir que las penalizaciones actuales representan probabilidades.

## Integración

El workflow de rutas se activa para PR hacia `feat/real-routing` y conserva los
resultados como artifacts. Separa pruebas, ejecución y revisión de validez/gap;
no exige gap cero ni afirma superioridad. Falta ejecutar GitHub Actions en el
repositorio remoto tras publicar el PR. El destino del PR es `feat/real-routing`;
no se debe fusionar automáticamente.

## Resultados observados

La ejecución de referencia (`baseline_seed42.json`) terminó con código 0 en
**201,48 s** de tiempo total: QAOA igualó el óptimo en los cuatro casos de
2 y 3 destinos. El caso de 4 destinos se omitió por requerir 16 qubits.

En la repetición con semillas 3, 7 y 42 se observaron estos resultados:

| Escenario | Destinos | Qubits | Óptimo exacto | Greedy (gap) | QAOA: costo por semilla 3 / 7 / 42 | Óptimos | Duración QAOA (s) |
|---|---:|---:|---:|---:|---|---:|---:|
| normal | 2 | 4 | 17 | 17 (0.00 %) | 17 / 17 / 17 | 3/3 | 1.17–1.21 |
| normal | 3 | 9 | 23 | 23 (0.00 %) | 23 / 23 / 23 | 3/3 | 49.71–78.46 |
| bridge_closed | 3 | 9 | 24 | 24 (0.00 %) | 27 / 24 / 24 | 2/3 | 62.08–74.62 |
| flood_risk | 3 | 9 | 28 | 29 (3.57 %) | 28 / 28 / 28 | 3/3 | 61.00–72.24 |
| normal | 4 | 16 | 25 | 25 (0.00 %) | omitido / omitido / omitido | 0/0 | — |

**Fiabilidad observada:** 12/12 ejecuciones con resultado fueron válidas y
11/12 alcanzaron el óptimo (91,7 %). En `bridge_closed`, semilla 3, QAOA devolvió
**27 frente al óptimo 24: gap 12,5 %**. Las otras once tuvieron gap cero.
Son frecuencias entre ejecuciones, no probabilidades de éxito por medición.

Las tres omisiones de 4 destinos no se incluyen en esas fracciones. El piloto
de 60 s conserva además un timeout de `normal`, 3 destinos, semilla 7; los casos
posteriores todavía no se habían ejecutado en ese checkpoint. La reanudación
de 120 s reutilizó cuatro ejecuciones completadas del piloto y terminó ocho
ejecuciones adicionales. No se eliminó el timeout de la evidencia histórica.

La enumeración exacta tardó entre 0.000023 y 0.000080 s en estos cinco casos;
QAOA tardó aproximadamente 1,17–78,46 s por ejecución, excluyendo el arranque
del trabajador. La concurrencia parcial entre piloto y reanudación y las
diferencias de entorno impiden interpretar esos números como una comparación
controlada de velocidad. En estas instancias pequeñas, el costo computacional
observado de QAOA fue mucho mayor que el de enumeración exacta.

**Conclusión:** QAOA obtuvo rutas válidas en las doce ejecuciones completadas,
pero no garantizó optimalidad. El límite de nueve qubits sólo permite evaluar
hasta tres destinos con esta codificación. Los resultados no demuestran ventaja
ni aceleración cuántica y no permiten extrapolar a redes operativas mayores.
No se usó hardware cuántico físico.
