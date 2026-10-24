# Q-Rescate · Aplicación Windows integrada

La interfaz PySide6 conserva el diseño, el mapa Leaflet/OpenStreetMap, los temas claro/oscuro y la edición de escenarios. El cerebro de los cálculos es el motor existente de Angelo, ejecutado en un proceso separado.

## Inicio

Desde la raíz del repositorio abre `INICIAR_Q_RESCATE.cmd`, o ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe run_qrescate.py
```

Requiere Windows x64 y Python (verificado con 3.13). El inicio normal usa OSM real y nunca cambia silenciosamente a una red sintética. Para edición sin motor: `run_qrescate.py --disconnected`.

No distribuyas solo esta carpeta: la aplicación integrada necesita también `engine`, `routing.py` y los archivos de raíz. El lanzador de esta carpeta delega al de raíz.

Consulta [la guía de integración](../docs/desktop-integration.md) para contratos, parámetros efectivos, límites de cobertura, cache, procesos, cancelación, ejemplos, pruebas y empaquetado.

Los informes de pruebas anteriores del frontend en `VERIFICATION.md` son históricos. La evidencia actual de la integración está en `../integration-evidence/REPORT.md`.
