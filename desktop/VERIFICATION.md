# Comprobación de entrega

Fecha: 24 de octubre de 2026. Windows 64 bits, Python 3.13.1, PySide6 6.12.0.

## Comprobaciones automatizadas

- **47 pruebas originales del repositorio aprobadas**, sin cambios en sus archivos ni en el QUBO.
- **30 pruebas nuevas del frontend aprobadas**. Usan Qt y QWebEngine reales, no una captura como interfaz.
- Total: **77 pruebas aprobadas** en la ejecución conjunta final.

Cobertura del frontend:

- Serialización/deserialización completa y copia independiente de escenario.
- Rechazo de versiones, coordenadas, IDs duplicados y parámetros inválidos.
- Estado desconectado: cálculo/experimentos deshabilitados, resultados vacíos.
- Mapa Leaflet cargado, contorno provincial destacado, exterior sombreado y atribución OpenStreetMap visible.
- Mínimo de zoom, restricción de desplazamiento y rechazo de ubicaciones fuera de Satipo en el mapa y en Python.
- Modos claro/oscuro en widgets y mapa sin perder el escenario; preferencia persistente.
- Botón NO PASAR crea una exclusión roja editable y eliminable.
- Comunicación real JavaScript → QWebChannel → Python para colocar la base.
- Creación, movimiento y eliminación de destinos; máximo configurable; n² qubits informativos.
- Movimiento/edición/eliminación de zonas y radio; controles de mapa renderizados.
- Formularios nativos de nombre/coordenadas y de nombre/tipo/radio de zonas.
- Guardar/cargar JSON por las acciones de la interfaz; archivo inválido conserva el escenario actual.
- Navegación por Dashboard, Escenarios, Experimentos, Resultados y Ayuda.
- Cálculo de servicio de prueba fuera del hilo GUI; estado Calculando → Completado.
- Renderizado de la geometría suministrada y visibilidad por método.
- Instantánea de escenario inmutable; las ediciones retiran resultados obsoletos del mapa.
- Historial y exportación JSON/CSV.
- Solicitud/confirmación de cancelación y envío de varias semillas al servicio de prueba.
- Errores de backend visibles, sin fabricar métricas.

El backend usado en estas pruebas está definido únicamente en `tests/test_desktop.py`. **La aplicación normal inicia desconectada**, sin datos de ese servicio.

## Revisión visual

Se generaron capturas desde la propia ventana Qt y se revisaron mapa, panel derecho, estados vacíos y ejemplo marcado como demostración. Se corrigieron contraste del panel bajo el tema oscuro de Windows, ancho de las tres columnas, campos que podían recortarse y color/indicadores de métodos.

El acceso de la herramienta de control de escritorio a la ventana Python no estaba autorizado; la revisión visual se hizo con capturas producidas por Qt. Las interacciones verificadas están automatizadas con llamadas a controles Qt y el canal del mapa, no mediante clics externos de esa herramienta.

## Límites comprobables

- No hay backend real conectado ni se valida OSMnx, red vial, cierres o geometrías reales de Satipo en esta entrega.
- Se probó el contrato con un servicio de prueba que devuelve datos explícitos; no demuestra integración con un servicio todavía no disponible.
- Las teselas requieren Internet; Leaflet y los controles de edición son locales. Se informa si las teselas no cargan.
- La cobertura se restringe al contorno provincial referencial de Satipo (fuente INEI, servicio Osinergmin); no se usa como deslinde legal.
- El ZIP contiene código y lanzador, **no un ejecutable autónomo**. Requiere Python; la primera ejecución del lanzador descarga PySide6.
- Las pruebas de arrastre verifican eventos/coordenadas y controles renderizados; no se afirma una prueba manual de cada gesto con ratón físico.
