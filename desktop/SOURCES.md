# Referencias técnicas

- [Qt for Python · QWebChannel](https://doc.qt.io/qtforpython-6/PySide6/QtWebChannel/QWebChannel.html): comunicación entre objetos Qt y el mapa JavaScript.
- [Leaflet 1.9.4 · API](https://leafletjs.com/reference.html): mapa, marcadores arrastrables, círculos, eventos y geometrías GeoJSON.
- [OpenStreetMap · atribución y copyright](https://www.openstreetmap.org/copyright).

La referencia visual es la imagen suministrada por el usuario. No está incorporada como fondo ni como panel de la aplicación.

## Contorno provincial Satipo

`assets/satipo.geojson`: consulta al [servicio cartográfico de Osinergmin, capa 26](https://gisem.osinergmin.gob.pe/serverdc/rest/services/DSGN/CARTOG/MapServer/26), filtro IDPROV=1206, outSR=4326, formato GeoJSON. Sus atributos identifican PROVINCIA=SATIPO, DEPARTAMEN=JUNIN y FUENTE=INEI. Descargado el 24 de octubre de 2026. Se conserva el polígono completo, sin reemplazarlo por un círculo o rectángulo. Uso cartográfico referencial.

[La Municipalidad de Satipo](https://www.gob.pe/21701-acceder-al-mapa-de-satipo-a-traves-de-la-plataforma-nacional-de-datos-geo-referenciados-geo-peru) explica el carácter referencial de los límites administrativos INEI en Geo Perú. Esta aplicación no representa un deslinde legal.
