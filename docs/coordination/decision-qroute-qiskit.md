# Q-Route — decisión del equipo y guía técnica Qiskit

**Actualizado: 24 de octubre de 2026. Categoría: Algoritmos y aplicaciones.**

## Decisión vigente
El equipo **mantiene Q-Route**, una investigación/prototipo de optimización híbrida clásica-cuántica de decisiones logísticas con múltiples destinos, recursos y restricciones como objetivo de desarrollo. **El componente implementado hoy es mucho más pequeño:** un vehículo que sale de un depósito, visita 2–4 paradas una vez y regresa (TSP dirigido). QAOA se ejecutó para 2 y 3 destinos; cuatro destinos (16 qubits) se omitieron. No existen todavía múltiples vehículos, capacidades ni planificación operativa a escala real.

**Q-Rescate** es el caso narrativo inicial. Fenómeno de El Niño, vías bloqueadas e incendios sirven para explicar la importancia de coordinar rutas y recursos a gran escala, **no para atribuir datos reales o capacidad operativa a nuestra simulación**. Podemos explicar otros sectores como aplicaciones futuras. La demo debe dejar clara la diferencia entre *motivación general* y *modelo ejecutado*.

**Quantum Probability Lab/EdTech:** idea explorada pero no seleccionada. Quedó un experimento aislado en la rama `feat/edtech-qae`; no es el proyecto activo, no tiene PR a `main`, y no debe mezclarse con Q-Route. No borrar ramas ajenas ni fusionarlas sin aprobación.

## Lo que pide el reto
«Optimización de rutas y conexiones mediante algoritmos cuánticos»: representar variables/costos, comparar alternativas clásicas y cuánticas/híbridas, **visualizar resultados**. Se evalúan: formulación y restricciones (20 % de la categoría), Qiskit y claridad (25 %), innovación/validación (25 %), rigor/reproducibilidad (15 %) y arquitectura/prototipo (15 %). La ventaja cuántica práctica no está exigida.

## Arquitectura que se puede defender
```text
Grafo de vías y condiciones (dato sintético o fuente atribuida)
  -> NetworkX / Dijkstra: caminos y matriz de costos (clásico)
  -> formulación QUBO/Ising del problema reducido
  -> QAOA con primitivas locales Qiskit (circuito cuántico SIMULADO)
  -> decodificación, validación de restricciones y recálculo de costos (clásico)
  -> comparación visual: exacto, heurística y QAOA + qubits + tiempo + fiabilidad
```

La red completa puede tener muchas vías **sin que todas entren en qubits**. La codificación TSP actual usa **n² qubits** para n destinos, por lo que simular instancias grandes con vector de estado puede resultar impracticable. Preprocesar una red grande y optimizar con QAOA un subproblema de 2–3 destinos **no significa** resolver cuánticamente toda la red.

## Evidencia experimental vigente
- [Prueba base de rutas #40113271525](https://github.com/alejandrasalas-dev/q-rescate/actions/runs/40113271525): 17 tests, QAOA obtuvo el costo óptimo en cuatro experimentos pequeños con semilla 42.
- [Carlos PR #10](https://github.com/alejandrasalas-dev/q-rescate/pull/10): documenta 12/12 soluciones factibles y 11/12 óptimas con tres semillas, con **una ejecución subóptima** de costo 27 frente al óptimo 24; depende de la revisión del PR y sus ejecuciones CI.
- **No demostramos velocidad, calidad o escalabilidad superiores frente al mejor método clásico.** El baseline exacto es más rápido en estas instancias de simulador. No convertir igualdad del óptimo en una promesa de ventaja.

## Checklist técnico tomado como orientación de los materiales entregados por la organización

### A. Modelo matemático — Angelo / Issue #5
- [ ] Entradas, unidades, variables, objetivo, restricciones y solución factible definidos.
- [ ] QUBO/Ising equivalente al problema original en todas las soluciones válidas probadas.
- [ ] Penalizaciones justificadas; no hay subtours ni rutas inviables presentadas como válidas.
- [ ] Comparación contra un método clásico adecuado; limitaciones de escala explícitas.
- [ ] Propuesta de descomposición / multi-recurso señalada como **trabajo futuro**, no simulación ya realizada.

### B. Qiskit y reproducibilidad — Carlos / Issue #6
- [ ] Comprobar versiones y API vigente: Qiskit `QuantumCircuit`, primitivas locales (`StatevectorSampler`), `QuadraticProgram`, QAOA.
- [ ] Verificar convenios de bits, qubits, semillas, shots, profundidad y backends.
- [ ] Validar las restricciones y recalcular el costo real tras decodificar la solución.
- [ ] Medir factibilidad, brecha respecto a clásico exacto, variación entre semillas y tiempos (con cuidado de comparabilidad).
- [ ] Mantener la simulación limitada a 9 qubits salvo revisión técnica explícita.
- [ ] No confundir simulación ideal con hardware IBM real; éste es opcional y requiere acceso/credenciales seguras.

### C. Interfaz y presentación — Alexia / Issue #7
- [ ] Abrir con desafío de escala: coordinar decisiones logísticas bajo restricciones cambiantes.
- [ ] Usar El Niño/incendios solo como contexto documental, con fuentes y límites.
- [ ] Mostrar qué se probó: **un vehículo**, rutas con 2–3 destinos, escenarios normal/cierre/riesgo, costo clásico y QAOA.
- [ ] Separar claramente «visión para múltiples recursos» de «funcionalidad implementada».
- [ ] Explicar el papel de Qiskit en una pantalla/circuito y reconocer que no se probó aceleración.
- [ ] Entregar storyboard, una demo visible (o video) y el contenido PPT/pitch en español.

### D. Integración — Ale / Issue #8
- [ ] Contratos de datos entre backend Qiskit y la demo (ejemplo: escenario, grafo, secuencia, costo, qubits, algoritmo, semilla, validez).
- [ ] Ejecutar y registrar CI; verificar que no haya artefactos vacíos, timeouts silenciados o resultados irreproducibles.
- [ ] README en español con instrucciones y avisos de datos sintéticos.
- [ ] Verificar acceso del jurado a GitHub y demo; entregar enlaces, descripción y PPT al portal oficial antes del cierre.
- [ ] No fusionar/publicar/desplegar ni usar recursos facturables sin aprobación de Ale.

## Recursos de Qiskit compartidos en Drive (lectura, no código del proyecto)
Carpeta: https://drive.google.com/drive/folders/1I6rBGxq-4zXPeIZK2FU_wR00I4XzwXzv

- **quantum-optimization / SKILL.md:** formulación QUBO, penalizaciones, solución factible y benchmark justo — **aplicación directa**.
- **qiskit-engineering / SKILL.md:** primitivas actuales, simulador, circuito/mediciones, transpilar si se usa hardware — **aplicación directa**.
- **ibm-quantum-compute / SKILL.md:** autenticación/ISA/QPU — **solo si decidimos ejecutar en hardware IBM**, no necesario ahora.
- **hackathon-coach / SKILL.md:** rúbrica, demo, claridad, acceso de jurado, pitch y entregables — **aplicación directa**.
- **qml-edtech / SKILL.md:** pertenece a EdTech, **no es prioridad del proyecto seleccionado**.

Estas guías son material de referencia externo. No se copian ni ejecutan automáticamente; el trabajo se valida con las bases oficiales, el código del repositorio y la documentación Qiskit actual.

## Criterio para no dispersarnos
Prioridad 1: demo verificable que visualice y compare lo ya ejecutado.
Prioridad 2: validación QUBO y análisis de fiabilidad/limitaciones de Carlos.
Prioridad 3: explicación de cómo crecería el problema, qué se descompondría clásicamente y qué escala puede simularse.
No comenzar una reimplementación completa de varios vehículos ni perseguir ventaja cuántica no medida durante las horas de entrega.
