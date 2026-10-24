# Arquitectura de Q-Route / Q-Rescate

**Hackathon Qiskit Fall Fest 2026 · Categoría Algoritmos y aplicaciones**

## Respuesta técnica al mentor

**Modelo de grafos:** utilizamos un **grafo dirigido y ponderado** (`networkx.DiGraph`). Los nodos representan puntos de la red; las aristas, conexiones transitables; y los pesos, costos de desplazamiento. Una arista puede tener distinto costo según el sentido. Un cierre se representa eliminando la arista correspondiente. Con **Dijkstra** (`nx.single_source_dijkstra_path_length`) obtenemos los caminos permitidos y una **matriz de costos dirigida**, común para todos los solucionadores.

**Problema de optimización principal:** TSP dirigido con depósito fijo. En el modelo validado, **una unidad** visita los destinos exactamente una vez y regresa al origen. La formulación **QUBO** utiliza variables binarias `x[p,i]`: el destino `i` ocupa la posición `p`. Impone un destino por posición y una posición por destino, minimizando costo de salida, desplazamientos entre destinos y retorno. Para `n` destinos, esta codificación utiliza **n² variables/qubits**.

**Algoritmo cuántico principal:** **QAOA (Quantum Approximate Optimization Algorithm)** mediante IBM **Qiskit SDK**, **Qiskit Algorithms** y **Qiskit Optimization** (`QuadraticProgram` / `QuadraticProgramToQubo`, `MinimumEigenOptimizer`, `QAOA`, `StatevectorSampler`). QAOA intenta encontrar una buena solución del QUBO; después se decodifica, comprueba factibilidad y recalcula el costo real.

**Comparación clásica:** enumeración exacta de recorridos pequeños y heurística de vecino más cercano, sobre la **misma matriz de costos**. Para experimentos adicionales se investigaron programación dinámica, búsqueda local y asignación entre recursos.

**Grover es complementario, no el algoritmo principal del TSP:** en un experimento aparte se muestra **amplificación de probabilidad** en una asignación de dos recursos/cuatro destinos con cuatro qubits. El oráculo de esa demostración fue construido **enumerando clásicamente todas las combinaciones**; demuestra el efecto del circuito, **no** una ventaja computacional práctica sobre el mejor método clásico.

## Flujo de datos

```text
Escenario y puntos en el mapa
          |
          v
Grafo dirigido y ponderado (NetworkX / OSMnx si está integrado)
          |
          v
Restricciones de vías + Dijkstra -> matriz de costos
          |
          +--> Clásico exacto / heurístico
          |
          +--> TSP -> QUBO/Ising -> QAOA (Qiskit, SIMULADOR)
                              |
                              v
       Decodificación + comprobación de restricciones + costo
          |
          v
  Interfaz: rutas, costos, gap, validez y tiempo
```

## Estado real frente a integración en desarrollo

| Componente | Estado comprobable |
| --- | --- |
| Grafo sintético dirigido y ponderado con NetworkX | Implementado en `routing.py` en `feat/real-routing` |
| Dijkstra, matriz común, exacto, greedy, QUBO y QAOA | Implementados y probados mediante GitHub Actions |
| Simulador ideal de Qiskit `StatevectorSampler` | Utilizado; **no se utilizó hardware IBM Quantum físico** |
| OSMnx y red real de OpenStreetMap en la interfaz | Integración de Carlos/Angelo **en desarrollo; no declarar validada hasta verla funcionando** |
| Grover con oráculo precomputado clásicamente | Experimento separado en [PR #13](https://github.com/alejandrasalas-dev/q-rescate/pull/13) |
| Multi-recurso y capacidad de dos destinos por unidad | Experimento adicional en [PR #12](https://github.com/alejandrasalas-dev/q-rescate/pull/12), sin reemplazar el TSP principal |

## Resultados y límites

- Escenario sintético `bridge_closed`, tres destinos, semilla 3: clásico exacto **24**, QAOA **27**; ambas rutas válidas.
- Escenario sintético `flood_risk`, tres destinos, semilla 42: exacto **28**, greedy **29**, QAOA **28**.
- Se observaron **12/12 rutas QAOA válidas y 11/12 óptimas** en las corridas completadas del [PR #10](https://github.com/alejandrasalas-dev/q-rescate/pull/10).
- No hay evidencia de que QAOA sea **más rápido o superior** al método clásico exacto en estos casos.
- Los costos y rutas históricos son de **grafos sintéticos**, no recorridos calculados sobre las calles reales de Piura. Si se conecta OSMnx hay que ejecutar el cálculo nuevamente.

## Tecnologías

- **IBM Qiskit SDK + Qiskit Algorithms + Qiskit Optimization** para la formulación y simulación cuántica.
- **Python y NetworkX** para redes, caminos, matrices y baselines clásicos.
- **OSMnx + OpenStreetMap** como integración vial planificada/en desarrollo para la demo.
- **PySide6** como interfaz de escritorio planificada/en desarrollo.
- **GitHub Actions + pytest** para validación reproducible.

**Resumen de una frase:** «Modelamos la logística con un grafo dirigido y ponderado, calculamos costos mediante Dijkstra y resolvemos un TSP dirigido formulado como QUBO con QAOA en el simulador Qiskit, comparándolo con un algoritmo clásico exacto y heurísticas; Grover es una demostración cuántica complementaria».
