# Coordinación Q-Route

## Tareas y responsables

| Integrante | Issue | Entregable |
|---|---|---|
| Angelo | #5 | Validación QUBO y ecuaciones |
| Carlos | #6 | Benchmark QAOA con varias semillas y resultados JSON |
| Alexia | #7 | Guion, storyboard y demo visual |
| Ale | #8 | Integración, GitHub Actions y revisión final |

## Actualizaciones de progreso

Cada integrante debe escribir en su Issue: **Estado: En curso, Bloqueado o Listo para revisar; Trabajo actual; Enlace al entregable; Dependencia o ayuda requerida.**

Trabajar en ramas propias creadas desde `feat/real-routing`. Abrir un Pull Request en borrador hacia esa rama y enlazar el Issue. No fusionar ni desplegar sin aprobación.

## Validación antes del pitch

- [ ] Angelo valida QUBO y restricciones.
- [ ] Carlos verifica QAOA en varias semillas, con costos y tiempos.
- [ ] Alexia prepara demostración de escenarios normal, bloqueo y riesgo con resultados verificables.
- [ ] Ale integra componentes, comprueba JSON y CI, y revisa documentación y accesibilidad de entregables.

## Resultado actual

GitHub Actions #40113271525: 17 pruebas aprobadas, QAOA igualó el óptimo clásico en cuatro escenarios pequeños. Son datos sintéticos, una sola ambulancia y un simulador cuántico clásico. No hay evidencia de ventaja cuántica.

## Decisión

Q-Route es el candidato principal en Algoritmos. Q-Rescate es el caso de uso inicial. Quantum Probability Lab queda como alternativa sin desarrollo paralelo.
