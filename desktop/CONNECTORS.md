# Contrato de integración · versión 1

## Sustitución del backend

Implementar `BackendPort` (`qrescate_desktop/backend.py`) e inyectarlo:

```python
app = QApplication([])
window = MainWindow(backend=MiAdaptador())
window.show()
app.exec()
```

La interfaz solo depende de objetos en `models.py`. El adaptador puede usar HTTP, un proceso Python o una librería local; no hay transporte ni URL ficticia preconfigurada. No es necesario reconstruir las pantallas. No llamar a widgets desde el adaptador.

El controlador usa un `ThreadPoolExecutor` y señales Qt: capacidades, envío, consultas y cancelación no bloquean la ventana. Los métodos del adaptador deben tener **timeouts finitos**; las consultas de estado se serializan cada 750 ms después del envío. Cancelación puede ejecutarse concurrentemente con una consulta: el adaptador debe soportarlo. Una llamada Python bloqueada no se puede interrumpir desde Qt; esa responsabilidad es del transporte/servicio.

## 1. Capacidades

`capabilities() -> Capabilities`

Por defecto desconectado. Campos: `connected`, `max_bases=1`, `max_vehicles=1`, `max_destinations=3`, `max_qaoa_destinations=3`, `max_qubits=9`, `shots_min=1`, `shots_max=8192`, `reps_max=10`, `maxiter_max=1000`, `methods=(exact,greedy,qaoa)`, `experiments=False`, `cancellation=False`, `qubit_encoding=position_n_squared`.

La primera integración representa una base y una unidad; estas capacidades configuran la validación, contador y texto de límites. Aumentar `max_vehicles` no habilita un algoritmo multi-unidad automáticamente; para otra formulación se debe revisar el contrato del escenario. No se ofrece selector libre de qubits: con `position_n_squared` se deriva n²; con otra codificación la pantalla indica «Según motor». El adaptador debe devolver capacidades coherentes y traducir sus códigos de método a los tres identificadores del frontend.

## 2. Solicitar un cálculo

`submit(scenario: Scenario) -> str` devuelve un `job_id` no vacío. Debe aceptar/enqueuear la solicitud, no esperar hasta completar la optimización. Recibe una copia independiente del escenario; las ediciones posteriores no alteran la solicitud.

Ejemplo de entrada (coordenadas ilustrativas, **no resultado**):

```json
{
  "schema_version": 1,
  "name": "Mi escenario Satipo",
  "base": {"id": "h", "name": "Base", "lat": -11.253, "lng": -74.638},
  "destinations": [{"id": "a", "name": "Destino A", "lat": -11.128, "lng": -74.731}],
  "zones": [{"id": "z", "name": "Exclusión", "kind": "exclusion", "lat": -11.2, "lng": -74.6, "radius_m": 500}],
  "config": {"methods": ["exact", "greedy", "qaoa"], "seed": 42, "shots": 512, "reps": 1, "maxiter": 35, "vehicles": 1}
}
```

Los puntos/centros son WGS84 con campos separados `lat/lng`. Radios en metros. Zonas: `operation` o `exclusion`. La semántica operativa y traducción de círculos a restricciones viales corresponde al backend: el frontend solo transmite geometría y tipo, no elimina aristas. Los cierres dirigidos, la red, los caminos y la matriz común son del motor. Debe devolver un error explícito si una zona no puede aplicarse; no ignorarla silenciosamente.

## 3. Consultar estados y resultados

`status(job_id: str) -> JobSnapshot`

Estados: `ready`, `running`, `completed`, `cancelled`, `error`. Presentación: Listo, Calculando, Completado, Cancelado y Error. `progress_percent` es `None` si no existe un avance real; la UI muestra actividad indeterminada. `job_id` debe coincidir con el solicitado.

`JobSnapshot` contiene `results: list[MethodResult]`, `messages: list[str]`, `error: BackendError | None`, `experiment_rows: list[dict]` y progreso opcional. Los resultados parciales pueden devolverse durante `running`; enviar la lista completa acumulada en cada snapshot con resultados. Los estados terminales se conservan en historial con fecha UTC y escenario enviado.

Cada `MethodResult`:

| Campo | Tipo / significado |
|---|---|
| `method` | `exact`, `greedy` o `qaoa` |
| `cost` | número finito o `None`; objetivo original, sin penalización QUBO |
| `unit` | texto (por ejemplo `min`), proporcionado por el motor |
| `gap_percent` | número finito o `None`; referencia exacta sobre la misma matriz |
| `valid` | booleano o `None`; factibilidad comprobada por el motor |
| `duration_seconds` | número finito no negativo o `None` |
| `visit_order` | lista ordenada de IDs; incluir base inicial y final si corresponde |
| `geometry` | `Geometry` GeoJSON `LineString` o `None` |
| `messages` | lista de textos, incluidos avisos y limitaciones |

**Geometría**: `{"type":"LineString","coordinates":[[longitud,latitud], ...]}` en EPSG:4326. El orden GeoJSON es **lng,lat**, distinto de Leaflet y de los campos del escenario. Debe ser la geometría real retornada por el motor, con sentido y regreso. Si falta geometría, se muestran métricas sin inventar líneas. No se geocodifican ni asignan coordenadas reales a resultados sintéticos.

El gap se calcula en el backend: `100*(costo-optimo)/abs(optimo)`; con óptimo cero devolver 0 si ambos son cero y `None` si no se puede definir. No declarar superioridad/rapidez cuántica ni interpretar tiempos de simulación como tiempo de QPU.

## 4. Cancelar

`cancel(job_id: str) -> None`. Solo se habilita con `cancellation=True`. Solicita cancelación y debe regresar pronto. La UI sigue consultando hasta recibir `cancelled`, `completed` o `error`; no inventa confirmación. No mata procesos arbitrariamente. Un error al solicitar cancelación se informa y no detiene las consultas del trabajo.

## 5. Experimentos

`submit_experiments(scenario: Scenario, seeds: list[int]) -> str`. Solo con `experiments=True`. La UI valida semillas distintas de 0 a 2³¹−1, máximo 100. El servicio decide límites de recursos, orden, timeout y omisiones; no se ejecutan bucles QAOA dentro del frontend.

Se consulta con el mismo `status(job_id)`. `experiment_rows` es una lista acumulada con `seed`, `method`, `state`, `cost`, `gap_percent`, `valid`, `duration_seconds`, `message`. `state` puede incluir estados del experimento como timeout/omitido si el motor los proporciona como texto. Los snapshots completos, incluidos estos registros, se exportan a JSON. CSV incluye una fila por registro experimental cuando existe; en otros trabajos incluye una fila por método, con semilla, métricas, visitas, geometría, mensajes y error. JSON conserva además el escenario completo enviado y todos los metadatos.

## Errores

`BackendError(code: str, message: str, details: dict={}, retryable: bool=False)`. Ejemplos de códigos: `NETWORK_UNAVAILABLE`, `NO_PATH`, `UNSUPPORTED_ZONE`, `RESOURCE_LIMIT`, `TIMEOUT`. Un snapshot de error debe conservar el `job_id`. Las excepciones del adaptador son convertidas por el controlador a un snapshot de error; no se fabrican resultados. Para un transporte de red, validar y convertir JSON a estos objetos antes de devolverlo. No incluir credenciales ni secretos en mensajes o `details` exportables.

## Pendiente del equipo de backend

- Implementar el adaptador concreto y sus timeouts / gestión del ciclo de vida de trabajos.
- Declarar capacidades reales y política de zonas.
- Entregar costo, validez, gap, orden y geometrías sobre la misma matriz dirigida.
- Añadir el servicio de experimentos y cancelación cuando estén disponibles.
- Verificar integración OSMnx/red real de Satipo con datos actuales. Esta entrega no la declara validada.

## Cobertura de la interfaz

La UI valida bases, destinos y centros de zonas contra el polígono referencial de Satipo (UBIGEO 1206) incluido en assets/satipo.geojson. No es una validación de transitabilidad: el motor sigue siendo responsable de red vial, cierres y caminos. Los círculos de exclusión se mantienen independientes del límite provincial. Los recorridos recibidos se dibujan con color y flechas de sentido sin inventar geometrías.
