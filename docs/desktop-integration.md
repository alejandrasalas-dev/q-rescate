# Aplicación Windows integrada · Q-Rescate

## Fuentes y rama

- Frontend obligatorio: `b03fe62d538bcddd6679e365b1905d803d917bc8`.
- Backend PR #16 integrado: `a431e17ddbb231c8879e747c24df8f32d8ef20d5`.
- Rama: `feat/desktop-full-integration`; destino de revisión: `feat/real-routing` (coordinación del proyecto). No fusionar automáticamente.
- Se combinaron ambos historiales; se mantienen los tests anteriores y el QUBO/penalizaciones del backend. La validación binaria estricta del frontend/benchmarks también permanece. No se implementó un solucionador sustituto.

## Un único inicio desde código

Recomendado: Windows x64, Python 3.13 (entorno verificado). Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe run_qrescate.py
```

También se puede abrir `INICIAR_Q_RESCATE.cmd`; instala las dependencias completas antes de iniciar. La aplicación necesita tanto `desktop/` como `engine/`, `routing.py` y los archivos de raíz: no distribuir únicamente la carpeta desktop como si fuera la app integrada.

Normal: red vial **OSM**, sin fallback sintético. `--disconnected` abre edición/mapa sin cálculos. `--synthetic-test` solicita explícitamente una red sintética y solo se usa para pruebas. Los resultados conservan siempre su fuente. Si faltan dependencias del motor se abre desconectado con el error de instalación. Todos los puntos de entrada llaman `freeze_support()` antes de importar el frontend.

## Adaptador y motor de Angelo

`local_backend.py` implementa `BackendPort`. Traduce explícitamente nombre/name, lng/lon, destinos/destinations, exact/exacto, greedy/voraz, semilla/seed, círculos y metros. Envía `engine.contrato.Solicitud` a `engine.ejecutor.Calculo`. Ese ejecutor es quien crea el proceso `spawn`; el hilo de Qt solo envía/consulta/cancela.

El registro de trabajos usa IDs estables y un bloqueo por trabajo. Los resultados terminales se conservan; consultar/cancelar concurrentemente no muta procesos cerrados. Al cerrar se cancelan los procesos propios, se liberan colas y se espera el cierre de los hilos. El controlador no lanza Qiskit dentro de sus hilos.

Las etapas del motor se presentan sin porcentajes inventados. Se conservan los resultados parciales del clásico si QAOA termina por timeout/cancelación, los métodos omitidos/error, los puntos ajustados, destinos inaccesibles, matriz y metadatos de red. Estos últimos viajan en `JobSnapshot.metadata` y en JSON/CSV. Un recorrido que omite destinos inaccesibles se muestra como **Parcial**, aunque la permutación de los destinos restantes sea válida.

Geometría: el motor entrega `[[lat,lon],...]`. El adaptador invierte **una sola vez** a GeoJSON `[[lng,lat],...]`; Leaflet recibe GeoJSON directamente. Se dibujan las geometrías reales del motor, con colores y flechas, y se acerca el mapa al primer resultado nuevo.

## Parámetros efectivos

- Mínimo: **2 destinos**. Máximo clásico: 4; con QAOA: **3 destinos / 9 qubits**.
- Un vehículo, una base y **una zona de operación**; varias exclusiones.
- `reps=1` y `maxiter=35` son los valores fijos reales del motor de este PR. Se muestran y se deshabilita su edición; no se ignoran valores diferentes cargados de un escenario.
- Semilla y shots sí se transmiten. Plazo configurable en Más opciones: 1–900 s, valor inicial **300 s**, aplicado al proceso completo (descarga incluida).
- Experimentos múltiples permanecen deshabilitados con explicación. No se simula un servicio inexistente.
- Los ejemplos se convierten desde `engine/ejemplos.py`; contienen ubicaciones ilustrativas y no resultados precalculados.

## Cobertura provincial y recursos

`engine/cobertura.py` amplía la adquisición de red de `red_vial.py`; **no modifica el QUBO**. La vía normal ya no usa el recorte legado de radio a 8 km.

1. Comprueba los puntos y centros de zonas en el polígono provincial referencial de Satipo.
2. Construye la envolvente convexa de los puntos y, si existe, del círculo de operación; añade **5 km de margen** de caminos/desvíos.
3. Limita la descarga a la provincia más un margen fronterizo de 10 km. OSM puede incluir conexiones de desvío fuera del borde provincial; la selección de destinos sigue restringida a Satipo.
4. Descarga `drive` con OSMnx, manteniendo las componentes para detectar falta de conexión. El motor existente conserva su política de componente principal y sentidos.
5. Caché GraphML por hash del polígono exacto + versión de política; caché HTTP de OSMnx separada. Escritura GraphML mediante archivo temporal.

**No se descarga toda la provincia en cada clic.** Se soportan puntos elegibles en toda la provincia mediante selección bajo demanda. No se afirma que todas las vías rurales tengan cobertura OSM ni que una descarga completa provincial haya sido validada.

Protecciones: consulta HTTP 45 s, plazo externo de proceso, área máxima **60.000 km²**, grafo máximo **250.000 nodos / 750.000 aristas**, radio de operación máximo 250 km. Una petición demasiado grande se rechaza; no se recorta silenciosamente a 8 km. La comprobación de tamaño del grafo ocurre tras la adquisición; no equivale a una cuota dura de RAM del sistema operativo.

La zona de operación define **qué puntos pueden solicitarse**, no una pared que prohíba todos los desvíos viales fuera del círculo. Si la base o un destino quedan fuera, se rechaza con explicación. Las exclusiones sí eliminan tramos mediante el motor existente. Un centro/radio de operación no reemplaza la cobertura de la provincia.

Los ajustes mayores de 300 m se advierten. Un ajuste mayor de **1.000 m** aborta el cálculo en lugar de presentar un destino lejano como atendido. Ausencia de caminos, base bloqueada y destinos inaccesibles se muestran explícitamente.

## Verificación y evidencias

`integration-evidence/` conserva resultados reales de Windows de esta ejecución, el escenario exacto, parámetros, duración y fuente de red. No son los valores sintéticos históricos del repositorio.

| Prueba real OSM | Resultado observado |
|---|---|
| Satipo, 3 destinos, clásico/greedy | Completado; exacto 13,544 min, greedy 16,239 min; 1.325 nodos, 3.552 aristas |
| Satipo, 2 destinos, QAOA | Completado; exacto y QAOA 5,576 min; 4 qubits; semilla 42 y 512 shots; plazo 180 s |
| Exclusión sobre destino A | 62 aristas excluidas; A inaccesible; rutas restantes marcadas parciales |
| Satipo–Pangoa, selección amplia | Completado; área 345,48 km², 2.918 nodos y 7.772 aristas; exacto 86,807 min |
| Cancelación de proceso | Estado Cancelado, sin mantener el proceso de cálculo activo |
| Qt + mapa + adaptador OSM | Ventana real, mapa cargado, backend conectado y resultado Completado (`desktop-osm.json`) |

La prueba amplia supera el radio antiguo requerido para cubrir todos sus puntos; no demuestra disponibilidad exhaustiva de carreteras en toda la provincia. Tiempos y costos dependen del estado de OSM y de las velocidades estimadas por OSMnx; no son tiempos operativos de emergencias validados.

Repetición:

```powershell
.\.venv\Scripts\python.exe -m pytest tests desktop/tests -q
.\.venv\Scripts\python.exe desktop/tools/verify_real.py --case classic --output integration-evidence/classic.json
.\.venv\Scripts\python.exe desktop/tools/verify_real.py --case qaoa --output integration-evidence/qaoa.json
.\.venv\Scripts\python.exe desktop/tools/verify_real.py --case exclusion --output integration-evidence/exclusion.json
.\.venv\Scripts\python.exe desktop/tools/verify_real.py --case wide --output integration-evidence/wide.json
.\.venv\Scripts\python.exe run_qrescate.py --smoke-test integration-evidence/desktop-osm.json
```

## Empaquetado PyInstaller

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
.\.venv\Scripts\python.exe packaging/build_windows.py
.\dist\Q-Rescate\Q-Rescate.exe --synthetic-test --smoke-test integration-evidence/frozen-synthetic.json
```

Se genera una distribución **onedir**: hay que conservar todo `dist/Q-Rescate`, incluidos `_internal`, QtWebEngine, DLL y datos. El `.exe` por sí solo no es distribuible. El resultado exacto del empaquetado y su comprobación se registra en `integration-evidence/REPORT.md`; construirlo no basta para afirmar que funciona en otra Windows limpia.

## Disponibilidad de servidores OSM

La descarga verifica el estado de dos servidores públicos (overpass-api.de y overpass.private.coffee) y cambia de instancia si hay fallo o saturación. No hay disponibilidad garantizada de estos servicios externos. Se puede calcular sin Internet cuando existe una caché que cubra íntegramente la selección; una red parcial nunca sustituye silenciosamente la solicitada. La copia instalada debe cerrarse y abrirse después de actualizar el código.
