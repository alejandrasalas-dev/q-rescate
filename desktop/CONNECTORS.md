# BackendPort · Adaptador local integrado

La implementación concreta es `qrescate_desktop/local_backend.py`, que se inyecta al iniciar la aplicación. `DisconnectedBackend` permanece disponible mediante `--disconnected` y ante fallos de instalación.

- `capabilities()`: conectado, una base/unidad, mínimo dos destinos, máximo cuatro clásicos o tres QAOA, nueve qubits, una zona de operación, cancelación disponible, experimentos múltiples no disponibles.
- `submit(Scenario)`: valida y convierte a `engine.contrato.Solicitud`; crea `engine.ejecutor.Calculo` y devuelve un identificador sin esperar la optimización.
- `status(job_id)`: consulta con bloqueo por trabajo; devuelve `JobSnapshot` y conserva el resultado final.
- `cancel(job_id)`: solicita y registra cancelación del proceso propio; conserva resultados parciales recibidos.
- `shutdown()`: cancela y libera procesos/colas propios al cerrar.
- `submit_experiments(...)`: no implementado; la pantalla mantiene esta acción deshabilitada con explicación.

## Traducciones

`name → nombre`, `lng → lon`, `destinations → destinos`, `exact → exacto`, `greedy → voraz`, `seed → semilla`, `operation → zona_operacion`, `exclusion → exclusiones`, `radius_m → radio_m`.

Salida: `costo_min → cost` con unidad `min`, `gap_pct → gap_percent`, `valida → valid`, `duracion_s → duration_seconds`, `orden → visit_order`. La geometría `[[lat,lon],...]` se invierte una sola vez a GeoJSON `[[lng,lat],...]`.

`JobSnapshot.metadata` conserva la solicitud exacta del motor, su resultado completo, ajustes a la red y IDs inaccesibles. Cada método conserva su estado `ok`/`omitido`/`error` y sus detalles. Los resultados parciales no se presentan como atención completa de destinos inaccesibles.

Estados: `ok → completed`, `error → error`, `cancelado → cancelled`, `tiempo_agotado → error` con código `TIMEOUT`, `en_curso → running`. Se muestran etapas reales sin porcentajes inventados.

El motor fija `reps=1`, `maxiter=35`; la interfaz los muestra sin edición. Semilla, shots y plazo sí se transmiten. Configuraciones incompatibles se rechazan, no se ignoran.

Para cobertura provincial, semántica de zonas, límites de descarga y ejecución, véase [docs/desktop-integration.md](../docs/desktop-integration.md). Las fuentes exactas integradas y las pruebas actuales están en ese documento y en `integration-evidence/REPORT.md`.
