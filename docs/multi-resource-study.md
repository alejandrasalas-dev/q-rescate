# Q-Route: varias unidades, restricciones y alcance geográfico

**Objetivo de la prueba:** encontrar evidencia concreta para decidir cuándo tiene sentido resolver un problema de rutas mediante métodos clásicos y cuándo Qiskit QAOA produce resultados comparables o mejores. No se asume que el algoritmo cuántico ganará.

## Qué se evalúa, por separado

**Eje geográfico:** tres cuadrados hipotéticos de 20, 200 y 1.800 km por lado. Se usa la **misma red sintética de 100 nodos** en los tres. El caso de 1.800 km **NO representa carreteras reales de Perú**. Permite demostrar si aumentar distancia, sin agregar decisiones, cambia el costo computacional.

**Eje combinatorio:** 2 recursos/4 destinos, 3 recursos/6 destinos, 4 recursos/8 destinos. Los recursos salen de **depósitos distintos**, tienen capacidad para atender **exactamente dos destinos** y cada destino debe asignarse **una sola vez**.

**Restricciones adicionales:** costes de carretera asimétricos, calles bidireccionales bloqueadas, penalización de riesgo, prioridades de servicio y penalización por llegadas después de un umbral ficticio. Los plazos, pesos y ubicaciones son datos sintéticos, **no SLA, accidentes ni tiempos de bomberos reales**.

## Métodos comparados
- **Clásico exacto:** programación dinámica por subconjuntos que asigna dos destinos por recurso y evalúa ambos órdenes de atención.
- **Clásicos heurísticos:** asignación codiciosa y búsqueda local de intercambios entre vehículos.
- **Cuántico simulado (Qiskit QAOA):** únicamente el caso de **2 vehículos/4 destinos**, representado por un QUBO de **4 variables binarias y 4 qubits**.
  - \`z_i=1\`: destino \`i\` para el vehículo 0; \`z_i=0\`: destino \`i\` para vehículo 1.
  - Restricción \`sum(z_i)=2\` incorporada mediante una penalización cuadrática.
  - Objetivo de las asignaciones válidas: costo mínimo por vehículo de visitar sus dos destinos, incluyendo viaje, retorno, prioridades y tardanza.
  - Las penalizaciones por rutas inválidas se verifican enumerando las 16 cadenas binarias de cuatro qubits.
  - El orden de las dos visitas **se determina de forma clásica** al construir el QUBO. Esto es una **descomposición híbrida**, no una optimización cuántica completa del VRP.
  - Para 3 y 4 vehículos **NO está implementado un QUBO cuántico equivalente**; solo se prueba la referencia clásica. No se debe extrapolar el QUBO de cuatro bits como si resolviera toda la asignación grande.

## Ejecución y pruebas

\`\`\`bash
python -m pip install -r requirements.txt
python -m pytest tests/test_multi_resource_scale.py tests/test_routing.py -q
python -m experiments.multi_resource_scale --output experiments/results/multi-resource-classical.json
python -m experiments.multi_resource_scale --quantum --output experiments/results/multi-resource-quantum.json
\`\`\`

GitHub Actions ejecuta todos los escenarios clásicos y **una única corrida** de QAOA en 1.800 km (sintéticos), carretera bloqueada, dos recursos y cuatro destinos. Publica resultados JSON y tiempos. Una prueba cuántica sobre cuatro qubits puede ser viable aunque la región sintética sea enorme, porque la red se procesa primero **clásicamente**.

## Resultados

**La tabla final solo puede completarse tras validar GitHub Actions.** El código y los resultados se mantienen en el PR en borrador, sin fusionar. Se reportará por escenario:

| Distancia sintética | Recursos | Destinos | Clásico exacto | Heurística | QAOA | Significado |
|---|---:|---:|---|---|---|---|
| 20 km | 2 | 4 | Por ejecutar CI | Por ejecutar CI | No ejecutado | Regional |
| 200 km | 3 | 6 | Por ejecutar CI | Por ejecutar CI | No ejecutado | Intermedio |
| 1.800 km | 2 | 4 | Por ejecutar CI | Por ejecutar CI | Una prueba | Magnitud geográfica, no mayor número de decisiones |
| 1.800 km | 4 | 8 | Por ejecutar CI | Por ejecutar CI | No implementado | Mayor complejidad de asignación |

## Qué NO demostraría esta prueba

- No demostraría una ventaja cuántica por representar un área tan grande como Perú; **la región se procesa clásicamente**.
- No demostraría aceleración de QPU real, puesto que usamos un simulador ideal local \`StatevectorSampler\`.
- No demostraría que QAOA funciona mejor para 3–4 vehículos: todavía no existe QUBO cuántico validado para esos casos.
- No demostraría desempeño operativo de logística o emergencias en Perú. No hay datos reales de MTC/INDECI en este experimento.

## Revisión solicitada a Angelo y Carlos

**Angelo:** revisar equivalencia de objetivo QUBO (energía de cada asignación válida), penalización y límites de la descomposición híbrida.

**Carlos:** comprobar que los resultados comparados usan la misma función objetivo, que las corridas cuánticas son reproducibles y que ninguna duración se presenta como evidencia de speedup por simulación.

**Ale y Alexia:** visualizar en demo el escenario y el alcance real del prototipo, con eje geográfico y eje combinatorio etiquetados separadamente.

No fusionar ni desplegar sin autorización expresa de Ale.
