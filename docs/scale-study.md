# Q-Route — estudio controlado de escalabilidad (24/10/2026)

## Pregunta de investigación

**¿Cuándo tiene sentido la solución clásica y qué podemos afirmar legítimamente sobre QAOA?** Para contestar, distinguimos DOS dimensiones independientes:

1. **Tamaño de la red vial:** 25, 100 y 400 intersecciones (nodos). NetworkX procesa todo el grafo **clásicamente** y calcula caminos permitidos. Tener cientos de calles no implica cientos de qubits.
2. **Cantidad de destinos que se optimizan conjuntamente:** 3, 6 y 10 paradas. Nuestro QUBO de TSP utiliza **n² variables/qubits**, independientemente de las calles de entrada. Aumentar paradas sí aumenta drásticamente el costo del circuito.

No confundir «muchos datos de carreteras» con «muchas decisiones entrelazadas».

## Diseño experimental

- Redes **sintéticas** de cuadrículas dirigidas con costos asimétricos, semilla 2026.
- Escenarios: normal, cierre de algunas vías, aumento de costo por riesgo simulado.
- El generador conserva una estructura conectada y los **costos de las vías compartidas son iguales** en escenarios normal/cierre; en riesgo solo se agregan penalizaciones.
- Caso operativo implementado: **un solo vehículo**, sale del depósito, visita todas las paradas una vez y regresa. No es VRP multivehículo, no hay capacidad, despacho de bomberos ni datos reales de Perú.
- Algoritmos clásicos: **Held-Karp exacto** para obtener el óptimo, **vecino más cercano** y **2-opt dirigido** como heurísticas. Las tres soluciones se validan contra la misma matriz de costos.
- Quantum: **solo una ejecución de Qiskit QAOA** con **3 paradas/9 qubits** sobre una red de 100 nodos y una vía cerrada. Este caso no está cubierto por el experimento de semillas de Carlos. No simular 36 ni 100 qubits, por límites de recursos.
- Validación: 17 tests específicos del estudio, incluyendo comparación de Held-Karp con enumeración exhaustiva en instancias pequeñas.

## Resultados clásicos preliminares verificados localmente

Los costos son unidades **arbitrarias, NO minutos reales**. Se muestran únicamente los escenarios de **carretera cerrada**; el JSON de GitHub Actions incluirá los 27 casos.

| Nodos de carretera | Paradas | Qubits requeridos por QUBO | Óptimo Held-Karp | Vecino cercano | 2-opt dirigido |
|---:|---:|---:|---:|---:|---:|
| 25 | 3 | 9 | 50 | 64 | 50 |
| 100 | 3 | 9 | 138 | 161 | 138 |
| 400 | 3 | 9 | 252 | 276 | 252 |
| 25 | 6 | 36 | 65 | 72 | 65 |
| 100 | 6 | 36 | 194 | 223 | 201 |
| 400 | 6 | 36 | 323 | 383 | 328 |
| 25 | 10 | 100 | 100 | 141 | 100 |
| 100 | 10 | 100 | 218 | 249 | 226 |
| 400 | 10 | 100 | 424 | 465 | 424 |

**Interpretación:** incluso en estas redes más grandes, el método clásico exacto funciona muy bien porque solo hay hasta diez destinos de servicio. La diferencia entre heurísticas demuestra por qué debemos comparar contra métodos sólidos; que QAOA supere al vecino cercano **no** implica ventaja frente a los métodos clásicos competitivos.

El valor en los casos de 400 nodos NO significa que los 400 nodos pasaron por QAOA; los caminos son calculados clásicamente antes de formular el pequeño TSP.

## Reproducción

\`\`\`bash
python -m pip install -r requirements.txt
python -m pytest tests/test_scale_study.py -q
python -m experiments.scale_study --output experiments/results/scale-classical.json
python -m experiments.scale_study --quantum --output experiments/results/scale-quantum.json
\`\`\`

La segunda ejecución con QAOA utiliza un simulador ideal local; tarda más y se limita a 9 qubits. GitHub Actions publica el JSON como artefacto **solo si la ejecución finaliza** y verifica estructura y estado.

## Qué aportaría evidencia de «usar cuántica aquí y clásico allá»

La comparación debe medir **la misma función objetivo, restricciones, instancias, semillas y criterios de recursos**. Se requeriría:
- Factibilidad de cada solución y brecha frente a referencia clásica exacta o al mejor valor conocido.
- Escalamiento de tiempos y recursos, **sin confundir simulación clásica de circuitos con QPU real**.
- Referencias clásicas serias: Held-Karp para tamaños manejables, 2-opt/OR-Tools para problemas grandes; mantener misma unidad de costo y validar restricciones.
- QAOA al menos en varios tamaños razonables y repetido con semillas para analizar frecuencia de soluciones válidas y óptimas.
- Si se plantea múltiples vehículos y capacidades, crear una **nueva formulación VRP** y validarla; el prototipo TSP no cubre esos casos.
- Si se incorporan mapas/datasets de MINAM o MTC, registrar fuentes, licencias, supuestos y cierres simulados, no etiquetar caminos fabricados como reales.

**Situación actual:** los experimentos pequeños de Carlos reportan 12/12 rutas válidas y 11/12 óptimas con QAOA, pero no prueban aceleración cuántica. Este estudio de escala está orientado a mostrar el límite de la formulación, no a fabricar un caso favorable.

## Evidencia y colaboración

- [PR de fiabilidad de Carlos #10](https://github.com/alejandrasalas-dev/q-rescate/pull/10): comparación de semillas, modelo pequeño.
- [Issue de Angelo #5](https://github.com/alejandrasalas-dev/q-rescate/issues/5): formulación matemática y restricciones.
- **Este estudio**: crecimiento independiente de red vial y de destinos, en rama propia \`feat/scaling-study\`.

No fusionar cambios ni implementar recursos de pago sin aprobación.
