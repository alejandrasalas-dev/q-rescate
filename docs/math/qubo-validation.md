# Validación del QUBO de rutas: restricciones e interpretación cuántica

*Issue #5 · Responsable: Angelo (formulación matemática y validación cuántica) · Rama: `docs/angelo-qubo` → `feat/real-routing`*
*Código de referencia: `routing.py` (`travel_matrix`, `quadratic_program`, `decode_tour`, `tour_cost`).*

---

## 0. Notación y unidades

| Símbolo | En `routing.py` | Significado | Unidad |
|---|---|---|---|
| $n$ | `len(matrix) - 1` | número de puntos de servicio (2 a 4) | — |
| nodo $0$ | `DEPOT = "H"` | hospital (depósito fijo, salida y llegada) | — |
| nodos $1..n$ | `STOPS[:n]` | puntos de servicio A, B, C, D | — |
| $c_{uv}$ | `matrix[u, v]` | tiempo mínimo de $u$ a $v$ (Dijkstra, red dirigida) | minutos (datos sintéticos) |
| $x_{p,i}$ | variable `x_{p}_{i}` | 1 si el punto $i$ (índice `i` → nodo $i+1$) se visita en la posición $p$ | binaria |
| $A$ | `penalty` (= 1000) | peso de penalización de restricciones | minutos |

Índices en el código: posición $p\in\{0,\dots,n-1\}$ y punto $i\in\{0,\dots,n-1\}$. El punto $i$ corresponde a la fila/columna $i+1$ de la matriz, porque la fila/columna 0 es el hospital.

Como los caminos son dirigidos y algunas vías se cierran o se penalizan, **$c_{uv}\neq c_{vu}$ en general**. El problema es un TSP asimétrico con depósito fijo.

---

## 1. Función objetivo de `quadratic_program()`

El costo de una ruta tiene tres partes, que corresponden a los tres bloques del código:

$$
C(x)=\underbrace{\sum_{i=0}^{n-1} c_{0,\,i+1}\;x_{0,i}}_{\text{(a) salida del hospital}}
\;+\;\underbrace{\sum_{p=0}^{n-2}\sum_{i=0}^{n-1}\sum_{j=0}^{n-1} c_{i+1,\,j+1}\;x_{p,i}\,x_{p+1,j}}_{\text{(b) transiciones entre visitas}}
\;+\;\underbrace{\sum_{i=0}^{n-1} c_{i+1,\,0}\;x_{n-1,i}}_{\text{(c) retorno al hospital}}
$$

| Término | Código | Interpretación |
|---|---|---|
| (a) | `linear[f"x_0_{i}"] = matrix[0, i+1]` | Si el punto $i$ es el **primero**, se paga el tiempo H → $i$. Es lineal porque el hospital no es variable. |
| (b) | `quadratic[(x_{p}_{i}, x_{p+1}_{j})] = matrix[i+1, j+1]` | Si $i$ está en la posición $p$ **y** $j$ en la $p+1$, se paga $i\to j$. Es cuadrático porque depende de dos variables. |
| (c) | `linear[f"x_{n-1}_{i}"] += matrix[i+1, 0]` | Si $i$ es el **último**, se paga el retorno $i$ → H. Se usa `+=` porque para $n=1$ la posición 0 sería primera y última a la vez. |

**Observaciones de la revisión:**
1. **Orden dirigido correcto.** El término (b) usa `matrix[i+1, j+1]`, es decir de $i$ hacia $j$ y no al revés. Esto respeta la asimetría de las vías.
2. **Términos con $i=j$.** El triple bucle incluye $x_{p,i}x_{p+1,i}$ con peso $c_{ii}=0$. No aportan costo, y en rutas válidas nunca se activan porque un punto no puede ocupar dos posiciones.
3. **Sin término constante.** El hospital no tiene variable, así que $C(x)$ sale directamente en minutos.
4. **Número de términos:** $2n$ lineales y $(n-1)\,n^2$ cuadráticos. Para $n=3$: 6 lineales y 18 cuadráticos sobre 9 variables.

### Ejemplo con 3 destinos (escenario `normal`)

Matriz de tiempos (minutos), filas origen y columnas destino, en el orden H, A, B, C:

$$
c=\begin{pmatrix}0&4&7&8\\6&0&5&7\\8&5&0&4\\10&7&5&0\end{pmatrix}
$$

Para la ruta H → A → B → C → H, activa $x_{0,A}=x_{1,B}=x_{2,C}=1$ y las demás variables en 0:

| Parte | Variables activas | Tiempo |
|---|---|---|
| (a) salida | $x_{0,A}$ | $c_{H,A}=4$ |
| (b) transiciones | $x_{0,A}x_{1,B}$, $x_{1,B}x_{2,C}$ | $c_{A,B}+c_{B,C}=5+4$ |
| (c) retorno | $x_{2,C}$ | $c_{C,H}=10$ |
| **Total** | | **23 min** |

Verificado en código: `qp.objective.evaluate(bits) = 23.0 = tour_cost(m, [0,1,2])`. Esta es además la ruta óptima del escenario, igual a la que reporta el benchmark del run 40113271525.

---

## 2. Variables binarias y restricciones

### 2.1 Variables

$$x_{p,i}\in\{0,1\},\qquad x_{p,i}=1 \iff \text{el punto } i \text{ se atiende en la posición (turno) } p$$

Se ordenan como **matriz $n\times n$**: la fila es la posición y la columna es el punto. En Qiskit, cada variable es un qubit con índice $k=n\,p+i$, el mismo orden que `quadratic_program()` crea y que `decode_tour()` lee con `reshape(n, n)`.

| $n$ | Variables (qubits) | Orden en el código |
|---|---|---|
| 2 | 4 | `x_0_0, x_0_1, x_1_0, x_1_1` |
| 3 | 9 | `x_0_0 … x_0_2, x_1_0 … x_1_2, x_2_0 … x_2_2` |

El hospital **no** tiene variable porque su posición es fija (inicio y fin). Si se codificara también, harían falta $(n+1)^2$ variables. Fijarlo ahorra $2n+1$ qubits, que son 7 para $n=3$.

### 2.2 Restricciones "exactamente uno"

$$\text{(R1) por posición:}\quad \sum_{i} x_{p,i}=1 \quad \forall p \qquad\qquad \text{(R2) por destino:}\quad \sum_{p} x_{p,i}=1 \quad \forall i$$

| Restricción | Código | Significado | Qué evita |
|---|---|---|---|
| R1 | `position_{p}` | en cada turno se atiende **un** punto | turnos vacíos o dos puntos a la vez |
| R2 | `stop_{i}` | cada punto se atiende **una** vez | puntos olvidados o repetidos |

En total son $2n$ restricciones (6 para $n=3$).

### 2.3 Por qué representan exactamente una ruta

**Proposición 1.** $x$ cumple R1 y R2 si y solo si la matriz $X=[x_{p,i}]$ es una **matriz de permutación**, es decir, si existe una biyección $\pi:\{\text{posiciones}\}\to\{\text{puntos}\}$ con $x_{p,i}=1 \iff \pi(p)=i$.

*Prueba.*
- **(⇒)** R1 dice que cada fila tiene un único 1, así que $\pi(p)$ está bien definida. R2 dice que cada columna tiene un único 1, así que $\pi$ es inyectiva. Una función inyectiva entre dos conjuntos de $n$ elementos también es sobreyectiva, por lo que $\pi$ es biyectiva.
- **(⇐)** Si $\pi$ es biyectiva, cada fila y cada columna tienen exactamente un 1. $\blacksquare$

**Consecuencias:**
- Hay exactamente $n!$ estados válidos: 2 para $n=2$ y 6 para $n=3$.
- Cada estado válido es **una** ruta H → $\pi(0)$ → … → $\pi(n-1)$ → H, y `decode_tour()` la devuelve como `[π(0), …, π(n-1)]`.

### 2.4 Por qué no hay subtours

En el TSP clásico con variables de arista ($y_{uv}=1$ si se usa el tramo $u\to v$), las restricciones de "entra uno y sale uno" aceptan soluciones con **ciclos separados**, por ejemplo H → A → H junto con B → C → B. Eso obliga a añadir restricciones de eliminación de subtours, que crecen exponencialmente.

**Proposición 2.** Con la codificación por posiciones no existe ninguna asignación válida con subtours.

*Prueba.*
- Toda asignación válida define una secuencia $\pi(0),\dots,\pi(n-1)$ (Proposición 1).
- La función objetivo solo conecta posiciones **consecutivas** ($p\to p+1$), además de H → $\pi(0)$ y $\pi(n-1)$ → H. Esos $n+1$ tramos forman un único camino cerrado H → … → H que pasa una vez por cada punto.
- Un subtour exigiría un tramo que regrese a un punto anterior sin pasar por H, pero la codificación no tiene ninguna variable que represente ese tramo. $\blacksquare$

**Costo de esta ventaja:** $n^2$ qubits en lugar de $n(n-1)$ variables de arista, y el término cuadrático (b) en lugar de uno lineal.

### 2.5 Verificación exhaustiva

Se recorrieron **todos** los estados binarios y se decodificaron con `decode_tour()`:

| $n$ | Estados $2^{n^2}$ | Válidos | $n!$ | ¿Son todas las permutaciones, sin repetir? |
|---|---|---|---|---|
| 2 | 16 | 2 | 2 | Sí |
| 3 | 512 | 6 | 6 | Sí |

El orden de las variables coincide con $k=n\,p+i$ (test `test_orden_de_qubits_x_p_i_es_n_por_p_mas_i`).

---

## 3. Penalización: signo, magnitud y escalabilidad

`QuadraticProgramToQubo(penalty=A)` convierte las restricciones en

$$Q(x)=C(x)+A\,V(x),\qquad V(x)=\sum_p\Big(1-\sum_i x_{p,i}\Big)^2+\sum_i\Big(1-\sum_p x_{p,i}\Big)^2 .$$

$V(x)$ es un entero $\ge 0$ y vale 0 **solo** en rutas válidas. Ejemplo: el estado con todo en 0 tiene $V=2n=6$, y por eso `evaluate(0) = 6000`.

### 3.1 Signo

- Hace falta $A>0$. Con $A\le 0$, violar restricciones **reduce** la energía.
- Con el código original, `quadratic_program(m, penalty=-5)` se aceptaba y el mínimo global era un estado inválido: el estado con todo en 0 da $Q=-30$.
- **Corrección:** ahora se lanza `ValueError` si `penalty <= 0` (test `test_penalidad_no_positiva_se_rechaza`).

### 3.2 Magnitud mínima correcta

**Lema.** Todo estado inválido viola **al menos dos** restricciones, es decir $V(x)\ge 2$.

*Prueba.*
- Sean $r_p$ las sumas por fila y $c_i$ las sumas por columna. Se cumple $\sum_p r_p=\sum_i c_i$, porque ambas son el número total de unos.
- Si solo fallara una fila, esa suma sería distinta de $n$. Entonces el total de las columnas tampoco sería $n$ y alguna columna también fallaría.
- El mismo argumento vale empezando por una columna. $\blacksquare$

**Proposición 3.** Si $A > C^\*/2$, ningún estado inválido es mínimo global.

*Prueba.* Como $C(x)\ge 0$ y $V(x)\ge 2$, se tiene $Q(x)\ge 2A>C^\*$. $\blacksquare$

**Umbral exacto.** Es $A_{\text{crít}}=\max_{x\ \text{inválido}} \frac{C^\*-C(x)}{V(x)}$, calculado por enumeración:

| Escenario | $C^\*$ | $A_{\text{crít}}$ | Estado inválido que lo fija |
|---|---|---|---|
| normal | 23 | **7.0** | H→A→B y se omite C: costo 9, $V=2$ |
| bridge_closed | 24 | **6.5** | costo 11, $V=2$ |
| flood_risk | 28 | **8.0** | costo 12, $V=2$ |

- Con los datos actuales, $A=1000$ es **correcto**, pero unas 125–150 veces mayor que el umbral.
- El estado que fija el umbral es justamente "saltarse una emergencia". Si la penalidad no alcanza, el QUBO prefiere **no atender** un punto.

### 3.3 Cuándo falla una penalización fija (escalabilidad)

- $A_{\text{crít}}$ crece con la **escala de los costos**, pero $A=1000$ no cambia.
- Cambiar de unidades no debería cambiar la solución. Sin embargo, si los tiempos se expresan en **segundos** (como devuelven OSRM o Google Maps) y los trayectos son unas 3 veces más largos (escala real de Lima Este, más de 1 h), el mínimo del QUBO pasa a ser una **ruta inválida** que omite una emergencia.
- Con los datos actuales, $A=1000$ falla cuando los costos se multiplican por más de 125–154, según el escenario.
- También falla al **añadir paradas**, porque $C^\*$ crece con $n$.
- Test que lo demuestra: `test_penalidad_por_defecto_valida_con_tiempos_en_segundos` falla con el código original en los 3 escenarios.

### 3.4 Corrección propuesta (en `routing.py`)

$$A_{\text{auto}}=\max\big(1000,\ \mathrm{UB}\big),\qquad \mathrm{UB}=\sum_{u}\max_{v} c_{uv}\ \ (\ge C^\*)$$

- **Por qué UB es una cota del costo:** toda ruta sale exactamente una vez de cada nodo, así que su costo es $\le$ UB. Como $A\ge \mathrm{UB}\ge C^\*>C^\*/2$, se cumple la Proposición 3 **para cualquier unidad, escala o $n$**.
- **Por qué se conserva el piso de 1000:** compatibilidad. Con los datos actuales, UB vale 29–33, así que se sigue usando exactamente 1000. Ni el benchmark del equipo ni el CI cambian (test `test_penalidad_por_defecto_no_cambia_resultados_actuales`).
- **Cambios en el código:** nueva función `penalty_bound(matrix)`, `penalty=None` como valor por defecto y validación de signo. Una penalidad explícita sigue funcionando igual.

| Tests | Código original | Con la corrección |
|---|---|---|
| `tests/test_penalizacion.py` (7) | **7 fallan** | 7 pasan |
| Suite completa | — | **38 pasan** |

### 3.5 Nota para Carlos (issue #6)

La corrección busca que **la formulación sea correcta en cualquier escala**. No pretende mejorar el rendimiento de QAOA, porque eso depende de la configuración del algoritmo y su validación experimental le corresponde a Carlos.

Se le entregan dos observaciones:

- Con la configuración actual (p=1, 35 iteraciones), $A=1000$ deja la distribución de QAOA casi uniforme. Con 512 muestras sobre 512 estados, la mejor muestra suele ser la ruta óptima incluso sin que QAOA concentre probabilidad en ella.
- Es preferible medir también la probabilidad de la ruta óptima en cada medición, comparada con el azar. La herramienta para hacerlo está en `analisis/validacion_qubo.py` y los datos en `analisis/resultados_validacion.json`.

Por esta razón la corrección mantiene 1000 como valor mínimo: con los datos actuales no cambia ningún resultado del benchmark.

---

## 4. Verificación: QUBO, ruta decodificada y costo original

### 4.1 Qué se verificó

Para **cada ruta válida** $\pi$ se construyó su vector binario ($x_{p,\pi(p)}=1$) y se comprobaron tres igualdades:

$$
\underbrace{Q(x_\pi)}_{\texttt{qp.objective.evaluate}}
=\underbrace{C(\pi)}_{\texttt{tour\_cost}}
=\underbrace{\langle x_\pi|H_C|x_\pi\rangle+\text{offset}}_{\text{energía de Ising}},
\qquad \texttt{decode\_tour}(x_\pi)=\pi
$$

| Escenarios | $n$ | Rutas válidas por escenario | QUBO = costo | Ising = costo | Decodificación |
|---|---|---|---|---|---|
| normal, bridge_closed, flood_risk | 2 | 2 | ✔ | ✔ | ✔ |
| normal, bridge_closed, flood_risk | 3 | 6 | ✔ | ✔ | ✔ |
| normal, bridge_closed, flood_risk | 4 | 24 | ✔ | (16 qubits, no evaluado) | ✔ |
| **Total** | | **96 rutas** | **96/96** | **24/24** | **96/96** |

Esto amplía el test del equipo `test_qubo_energy_equals_original_cost_for_every_valid_tour`, que solo cubre el escenario `normal`, a los 3 escenarios y a $n=4$. El nuevo test es `test_qubo_ising_y_costo_coinciden_en_todos_los_escenarios`.

Junto con la Proposición 1 (los estados válidos son exactamente las $n!$ rutas) y la Proposición 3 (ningún estado inválido es mínimo), esto implica que **el mínimo del QUBO, y por tanto el estado fundamental del Hamiltoniano, es la ruta óptima**. Lo confirma el test `test_ising_tiene_minimo_en_la_ruta_optima`.

### 4.2 Supuestos del modelo

| Supuesto | Implicación |
|---|---|
| Una sola unidad (ambulancia, brigada o camión) | No resuelve varios vehículos (VRP) |
| Costos $c_{uv}\ge 0$ y conocidos de antemano | Necesario para la Proposición 3. Los cierres y riesgos entran **antes**, vía Dijkstra |
| Todos los puntos deben atenderse | No hay priorización ni puntos opcionales |
| Costo = suma de tiempos de tramo | No modela ventanas horarias, capacidad ni tiempo de servicio en cada punto |
| Red estática durante la ruta | Un cierre nuevo exige recalcular la matriz y volver a optimizar |
| Datos sintéticos | No hay calibración con datos reales |

### 4.3 Límites

- **Qubits:** se necesitan $n^2$. Con $n=4$ son 16, que es el límite práctico del simulador local; con $n=10$ serían 100.
- **Estados válidos:** son una fracción mínima del total, $n!/2^{n^2}$: 1.2 % para $n=3$ y 0.04 % para $n=4$. QAOA con el mezclador estándar $X$ explora sobre todo estados inválidos.
- **Extensiones posibles:**
  - Mezcladores que preservan las restricciones (XY-mixer / QAOA+), que solo exploran permutaciones.
  - Descomposición híbrida: agrupar puntos con un método clásico y aplicar QAOA a cada subruta.
  - Multivehículo: añadir un índice de vehículo, lo que da $K\,n^2$ qubits.

---

## 5. Por qué esta formulación tiene sentido para Q-Route

### 5.1 Un solo modelo para distintos escenarios

El modelo cuántico **no sabe** si la unidad es una ambulancia, un camión de bomberos o un camión de víveres. Todo el escenario entra a través de una única pieza: la matriz $c_{uv}$, calculada con la capa clásica (red vial + Dijkstra).

```
 Escenario (red vial, cierres, riesgos)  →  Dijkstra  →  matriz c_uv  →  QUBO  →  Ising  →  QAOA / exacto / heurística
           ↑ cambia según el caso                          ↑ desde aquí todo es idéntico
```

| Escenario | Qué cambia en la red | Qué **no** cambia |
|---|---|---|
| **El Niño** (caso de storytelling) | Vías inundadas o con huaico se eliminan; vías en riesgo cuestan más tiempo | Variables, restricciones, QUBO, Hamiltoniano y QAOA |
| **Incendio urbano** | Calles obstruidas se eliminan; congestión cerca del foco aumenta el tiempo | Igual |
| **Logística o suministros** | Tiempos o costos de reparto entre almacenes y comunidades | Igual |

En el código esto ya se cumple: `bridge_closed` (cierre) y `flood_risk` (+8 min) solo modifican el grafo, y `quadratic_program()` no cambia.

### 5.2 Por qué QUBO

- Las decisiones del problema son **sí o no** ("¿el punto $i$ va en el turno $p$?"), lo que encaja con variables binarias.
- Las reglas son de tipo "exactamente uno", que se expresan bien como penalidades cuadráticas.
- QUBO es el formato de entrada estándar de los optimizadores cuánticos: QAOA, *quantum annealing* y `GroverOptimizer` en Qiskit. Además es intercambiable con solucionadores clásicos, lo que permite **comparar con la misma formulación**.

### 5.3 Por qué QAOA

- **Se deriva directamente del problema:** $H_C$ sale del QUBO sin pasos intermedios, y el estado fundamental es la ruta óptima (sección 4.1).
- **Es apto para el hardware actual (NISQ):** usa circuitos poco profundos (pocas capas $p$) y un optimizador clásico, es decir, es un enfoque **híbrido**.
- **Tiene una base teórica sólida:** cuando $p\to\infty$ recupera la evolución adiabática y alcanza el óptimo. Con $p$ pequeño es una heurística y debe validarse empíricamente contra métodos clásicos, que es lo que hace el benchmark del equipo.

### 5.4 Lo que **no** afirmamos

- No afirmamos que QAOA sea más rápido ni mejor que los métodos clásicos: en estos tamaños el método exacto es instantáneo.
- No usamos hardware cuántico real, solo un simulador clásico.
- **Lo que sí afirmamos:** la formulación es **correcta** (secciones 1 a 4), **general** (5.1) y **compatible** con algoritmos cuánticos actuales y futuros. Q-Route queda preparada para evaluarlos cuando el hardware madure.

---

## 6. Explicación para el jurado (90 segundos)

> **Problema (15 s).** Durante El Niño, lluvias e inundaciones bloquean carreteras y dejan comunidades aisladas. Lo mismo pasa en un incendio urbano cuando las calles se obstruyen. Decidir **en qué orden** visitar los puntos afectados es un problema combinatorio: con $n$ puntos hay $n!$ órdenes posibles.
>
> **Capa clásica (15 s).** Q-Route primero calcula con Dijkstra el tiempo real entre cada par de puntos, esquivando las vías cerradas y penalizando las riesgosas. El resultado es una matriz de tiempos. Lo único que cambia de un escenario a otro es esa matriz.
>
> **QUBO (20 s).** Cada qubit responde una pregunta de sí o no: *¿el punto $i$ se atiende en el turno $p$?* El tiempo total de la ruta es una función cuadrática de esas variables. Las reglas "un punto por turno" y "cada punto una vez" se agregan como penalidades. Demostramos que solo las rutas válidas pueden ser óptimas y que no aparecen subtours.
>
> **Hamiltoniano (15 s).** Al cambiar cada variable binaria por un espín, el QUBO se convierte en la energía de un sistema de espines (un Hamiltoniano de Ising). **La mejor ruta es el estado de mínima energía.** Lo verificamos en las 96 rutas de prueba.
>
> **QAOA en Qiskit (15 s).** QAOA prepara ese estado alternando dos operaciones: una que aplica el costo y otra que mezcla los estados. Un optimizador clásico ajusta los ángulos del circuito. Es un algoritmo híbrido, pensado para el hardware cuántico actual.
>
> **Honestidad (10 s).** Validamos todo contra la solución exacta. A esta escala lo clásico es más rápido y no prometemos una ventaja cuántica. Lo que entregamos es una formulación correcta, probada y general, lista para evaluarse a medida que el hardware crezca.

**Versión de una línea:** *"Convertimos una ruta en una energía: la mejor ruta es el estado de mínima energía de un sistema de qubits, y QAOA lo busca."*

---

## 7. Nota: Grover Adaptive Search (trabajo futuro, no implementado)

- **Idea.** *Grover Adaptive Search* (GAS, disponible en Qiskit como `GroverOptimizer`) busca una ruta con costo menor que un umbral $T$. Un oráculo cuántico marca esos estados y la amplificación de Grover aumenta su probabilidad. Cada vez que encuentra una ruta mejor, baja $T$ y repite.
- **Por qué encaja.** Usa **el mismo QUBO** de este documento, sin reformular el problema. Para Q-Route sería un solucionador cuántico más, comparable con QAOA y con los métodos clásicos.
- **Ganancia teórica.** Encontrar una de $M$ soluciones marcadas entre $N$ estados requiere unas $\sqrt{N/M}$ consultas al oráculo, frente a unas $N/M$ con búsqueda clásica no estructurada. Es una aceleración **cuadrática**, no exponencial.
- **Limitaciones:**
  - El oráculo debe calcular el costo de cada ruta dentro del circuito, lo que exige muchos qubits auxiliares y circuitos profundos.
  - Requiere hardware con corrección de errores, que todavía no existe a la escala necesaria.
  - Los mejores métodos clásicos de TSP (*branch-and-cut*, heurísticas como LKH) no hacen búsqueda no estructurada, así que la ventaja cuadrática no se traslada directamente.
- **Conclusión.** GAS es una línea de investigación futura, interesante si se busca un método con mejor garantía teórica. Para el hardware actual, QAOA es la opción adecuada. **No se implementa en esta entrega.**

---

## 8. Referencias

1. Lucas, A. (2014). *Ising formulations of many NP problems.* Frontiers in Physics 2:5. Formulación QUBO/Ising del TSP con codificación por posiciones.
2. Farhi, E., Goldstone, J., Gutmann, S. (2014). *A Quantum Approximate Optimization Algorithm.* arXiv:1411.4028.
3. Barkoutsos, P. et al. (2020). *Improving Variational Quantum Optimization using CVaR.* Quantum 4, 256.
4. Hadfield, S. et al. (2019). *From the Quantum Approximate Optimization Algorithm to a Quantum Alternating Operator Ansatz.* Algorithms 12(2), 34. Mezcladores que preservan restricciones.
5. Gilliam, A., Woerner, S., Gonciulea, C. (2021). *Grover Adaptive Search for Constrained Polynomial Binary Optimization.* Quantum 5, 428.
6. Documentación de Qiskit Optimization: `QuadraticProgram`, `QuadraticProgramToQubo`, `MinimumEigenOptimizer`, `GroverOptimizer`.

---

## Resumen de criterios de aceptación (issue #5)

| Criterio | Dónde |
|---|---|
| Notación y unidades compatibles con `routing.py` | Sección 0 |
| Costo de las rutas válidas idéntico al objetivo QUBO con 2 y 3 paradas | Sección 4.1: 96/96, incluido $n=4$; tests `test_qubo_*` |
| Restricciones y limitaciones explicadas, sin atribuir ventajas no medidas | Secciones 2, 3, 4.2, 4.3 y 5.4 |
| Error de código encontrado y PR con tests que fallan antes de la corrección | Sección 3: `tests/test_penalizacion.py` (7 fallan con el código original) |
| Archivo versionado mediante PR a `feat/real-routing` | PR desde `docs/angelo-qubo` |
