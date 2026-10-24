# Informe de integración Windows · 24/10/2026

Fuentes: frontend `b03fe62d538bcddd6679e365b1905d803d917bc8`; PR #16 backend `a431e17ddbb231c8879e747c24df8f32d8ef20d5`, comprobado nuevamente en GitHub antes de publicar.

## Verificaciones ejecutadas

- Suite conjunta final: **152 pruebas aprobadas**, 25 advertencias no fatales, 75,39 s. Incluye la prueba Qt con el adaptador real, proceso separado, geometrías y guardado/reapertura. El XML `pytest.xml` recoge esta ejecución conjunta.
- OSM real, tres destinos: exacto 13,544 min; greedy 16,239 min. Red descargada: 1.325 nodos y 3.552 aristas; ajustes 19,2–224,7 m.
- OSM real, dos destinos, semilla 42, 512 shots: QAOA (4 qubits) y exacto 5,576 min, plazo 180 s. Se conservaron geometrías reales y etapa parcial del clásico.
- Exclusión: 62 aristas eliminadas y destino A inaccesible; resultado restante marcado parcial.
- Selección amplia Satipo–Pangoa: 345,48 km², 2.918 nodos y 7.772 aristas; exacto 86,807 min. Sin recorte a 8 km ni sustitución sintética.
- Cancelación del proceso: estado Cancelado.
- Aplicación Qt real con mapa y adaptador OSM: backend conectado, mapa cargado y cálculo Completado (`desktop-osm.json` y captura PNG).
- Guardado/reapertura de escenario, exportación JSON/CSV y preservación de metadatos comprobados en pruebas de interfaz y contrato.

## Distribución y límites pendientes

Se preparó `packaging/build_windows.py` y se inició PyInstaller en Windows con todas las dependencias. **El ejecutable no se declara validado**: el empaquetado seguía procesando dependencias al preparar el envío urgente. No se entrega como si fuera un binario autónomo probado. El inicio desde código está verificado y el lanzador instala el manifiesto completo.

No se probó en otra máquina Windows limpia sin Python. No se validó una descarga exhaustiva de toda la provincia; sí la selección amplia indicada. La aplicación soporta selección provincial bajo demanda, con límites explícitos de área, tamaño de grafo, plazo y ajuste a la vía. La zona de operación limita los puntos elegibles y permite desvíos viales fuera del círculo.

No se cambiaron el QUBO ni las penalizaciones de Angelo para resolver la interfaz. Las extensiones de su motor cubren adquisición provincial, rechazo de ajustes mayores de 1 km, geometría orientada, resultados parciales y liberación de procesos. Los costos de OSM usan velocidades estimadas; no son tiempos de respuesta operativos validados.

No se fusionó el PR #16 ni el PR de integración.

## Corrección de timeout OSM

La descarga dependía exclusivamente de overpass-api.de. Ahora verifica disponibilidad con conexión de 5 s/lectura de 7 s, alterna con overpass.private.coffee y evita los reintentos recursivos de OSMnx ante 429/502/503/504. Conserva el plazo externo del proceso y el control de slots del servicio. Los dos son servidores OSM reales; no se añade ningún fallback sintético.

Se reutiliza una caché de otra selección solo si su manifiesto conserva el polígono completo original y este contiene toda la nueva petición; no se infiere cobertura por bounding box. Se conserva el detalle técnico exportable y se presenta un mensaje único, legible y reintentable.

En esta comprobación de red ambos endpoints públicos fallaron (ConnectTimeout/ReadTimeout); por ello no se afirma haber completado una descarga nueva durante la interrupción externa. Sí se completó una ejecución real OSM desde la caché existente (`osm-retry-cache.json`), y se probaron fallos/reintentos controlados sin usar datos sintéticos.
