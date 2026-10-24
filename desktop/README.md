# Q-Rescate · Frontend de escritorio Windows

Interfaz PySide6 inspirada fielmente en la referencia suministrada: navegación izquierda, tarjetas superiores, mapa central, panel de configuración a la derecha y comparación inferior. Los controles, textos, iconos vectoriales y tarjetas son componentes editables; no se emplea la captura como fondo. El único componente web es el mapa Leaflet/OpenStreetMap conectado con QWebChannel.

## Inicio rápido

Extrae **todo** el ZIP a una carpeta y abre `INICIAR_Q_RESCATE.cmd`. La primera ejecución crea un entorno y descarga PySide6. Requiere Windows de 64 bits, Python 3.11 o posterior disponible como `python`, e Internet para instalar paquetes y ver las teselas del mapa. Leaflet 1.9.4 está incluido localmente con su licencia.

La ventana reproduce la referencia a 1586 × 990 píxeles lógicos. Su mínimo es 1360 × 850 para mantener las tres columnas legibles; se recomienda una pantalla de 1600 × 1000 o superior con la escala de Windows adecuada. El panel de configuración permite desplazamiento vertical cuando hace falta.

Desde la copia del repositorio con el entorno existente en la carpeta padre:

```powershell
..\.venv\Scripts\python.exe -m pip install -r desktop\requirements-desktop.txt
..\.venv\Scripts\python.exe desktop\run_desktop.py
```

Alternativamente, desde esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe run_desktop.py
```

La interfaz no necesita Qiskit para abrirse. Las dependencias del motor siguen en el `requirements.txt` original del repositorio, que no se ha modificado.

## Uso

- Base / Agregar destino: activa la herramienta y pulsa el mapa. Arrastra un marcador para moverlo; clic derecho abre su editor. El panel permite cambiar nombre/coordenadas o eliminarlo con ×. Escape cancela la herramienta.
- Modo claro/oscuro: el selector Apariencia del menú lateral cambia también el mapa y conserva la preferencia al reiniciar.
- Marcar zona de NO PASAR: crea un círculo rojo de exclusión; el nombre permite indicar el motivo del cierre. Se puede mover, cambiar radio y eliminar. El backend aplicará las restricciones viales.
- Zona de operación / Excluir zona: pulsa el mapa y confirma centro, tipo y radio en el formulario. Selecciona la zona para mostrar los controles de centro y radio arrastrables; también se puede editar/eliminar desde el panel.
- Las letras A, B, C siguen el orden de los destinos; el motor usa identificadores estables, nunca las letras como identidad.
- El mapa remarca la provincia de Satipo, Junín y sombrea el exterior. El desplazamiento está restringido y no permite alejarse más allá de la vista provincial. Bases, destinos y centros de zonas deben estar dentro del polígono, también al editar coordenadas o importar JSON. El contorno es referencial: fuente INEI, servicio cartográfico de Osinergmin; no representa un deslinde legal.
- Escenarios: crear, abrir y guardar JSON validado; Ctrl+S guarda y Ctrl+O abre. Se avisa de cambios pendientes antes de reemplazar o cerrar.
- El ejemplo está marcado **Demostración** y solo carga puntos y círculos ilustrativos; no agrega resultados ni recorridos.
- Los controles de la leyenda muestran/ocultan únicamente las geometrías recibidas del motor. No se conectan puntos con líneas ficticias.
- Resultados: costo, gap, validez, duración, unidad, orden y mensajes. El historial conserva el escenario enviado y se exporta a JSON/CSV. Editar el escenario vacía su comparación y mapa de rutas, preservando el historial de la sesión.
- Experimentos: formulario de semillas distintas (por defecto 3, 7, 42), tabla de estados y resultados suministrados por el servicio. Su acción permanece deshabilitada mientras la capacidad no exista.

## Alcance y estado

Se entrega **solo frontend y contratos de integración**, sin descargar redes viales, implementar cierres, Dijkstra, algoritmos ni cambiar el QUBO. No se modificaron código ni pruebas preexistentes. No se declara OSMnx validado: un mapa visible no es un motor de ruteo conectado.

Al iniciar: **Backend no conectado**, **Listo**, **Sin resultados**. Calcular/experimentar quedan deshabilitados con explicación. `DisconnectedBackend` nunca calcula ni inventa valores. El servicio se inyecta al crear `MainWindow(backend=mi_adaptador)`; véase `CONNECTORS.md`.

El modelo de presentación corresponde al TSP dirigido de una unidad con depósito fijo y regreso. La codificación por posición muestra n² qubits como información. QAOA se identifica como simulación. Grover y multi-recurso no se incorporan al problema principal.

## Organización

```
qrescate_desktop/
  models.py       Objetos de escenario, capacidades, errores y resultados
  backend.py      BackendPort y adaptador desconectado
  controller.py   Trabajo asíncrono, consulta de estado, cancelación, historial
  window.py       Pantallas y edición nativa Qt
  widgets.py      Tarjetas, iconos vectoriales y estilos
  map_widget.py   QWebEngineView / QWebChannel
  assets/map.html Mapa, marcadores, círculos y geometrías GeoJSON
tests/            Contratos y pruebas Qt/WebEngine con servicio de prueba
```

## Verificación

Desde la raíz del repositorio:

```powershell
..\.venv\Scripts\python.exe -m pip install pytest
..\.venv\Scripts\python.exe -m pytest desktop\tests -q
..\.venv\Scripts\python.exe -m pytest tests -q
```

Las pruebas de escritorio crean ventanas reales de Qt/WebEngine y requieren una sesión gráfica. El backend de prueba solo vive en `tests/`; no está conectado al lanzador de producción. Ver `VERIFICATION.md` para resultados de la entrega.

## Licencias y conexión

PySide6/Qt se instalan por pip con sus propias licencias (LGPL/GPL/comercial, según componente). Leaflet conserva su BSD-2-Clause en `assets/vendor/LEAFLET-LICENSE.txt`. La atribución OpenStreetMap está visible dentro del mapa. No se precargan ni descargan masivamente teselas; su disponibilidad depende de la red y del servicio.
