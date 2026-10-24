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

<!-- Secciones siguientes: 3 penalización · 4 verificación QUBO = costo · 5 explicación 90 s · 6 Grover (nota) · 7 referencias -->
