"""
Tarea 2 (Tabla 2): red vial para el motor de Q-Rescate.

- `obtener_red_osm`: descarga calles reales con OSMnx (network_type="drive"),
  añade velocidades y tiempos, y guarda una caché .graphml.
- `red_sintetica`: cuadrícula sin internet, con el mismo formato, para tests.
- `red_para_solicitud`: elige centro y radio a partir de una `Solicitud`.

Formato común del grafo (nx.MultiDiGraph, respeta sentidos de circulación):
  nodos:   x = lon, y = lat
  aristas: length (m), speed_kph, travel_time (s), oneway (bool)
  grafo:   crs = "epsg:4326", fuente = "osm" | "sintetica"
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Optional

import networkx as nx

R_TIERRA_M = 6_371_008.8
RADIO_MIN_M = 500.0
RADIO_MAX_M = 8_000.0       # evita descargas enormes desde la interfaz
MARGEN_M = 400.0            # margen alrededor de los puntos si no hay zona
VELOCIDAD_DEFECTO_KPH = 30.0


# ----------------------------------------------------------------- utilidades
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_TIERRA_M * math.asin(math.sqrt(a))


def desplazar(lat: float, lon: float, norte_m: float, este_m: float) -> tuple[float, float]:
    """Punto desplazado norte/este en metros (aprox. local, suficiente < 10 km)."""
    dlat = math.degrees(norte_m / R_TIERRA_M)
    dlon = math.degrees(este_m / (R_TIERRA_M * math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def directorio_cache() -> Path:
    """Caché en la carpeta del usuario (funciona también con PyInstaller)."""
    base = os.environ.get("QRESCATE_CACHE")
    ruta = Path(base) if base else Path.home() / ".q-rescate" / "osm"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def ruta_cache(lat: float, lon: float, radio_m: float, cache_dir: Optional[Path] = None) -> Path:
    # Redondeo ~11 m en coordenadas y 50 m en radio: pequeños movimientos reutilizan la caché.
    clave = f"{lat:.4f}_{lon:.4f}_{int(round(radio_m / 50.0) * 50)}_drive"
    h = hashlib.sha1(clave.encode()).hexdigest()[:10]
    return (cache_dir or directorio_cache()) / f"red_{h}.graphml"


# --------------------------------------------------------------- normalizar
def _a_bool(v) -> bool:
    if isinstance(v, list):
        v = v[0] if v else False
    return str(v).strip().lower() in ("true", "1", "yes", "-1")


def _a_float(v, defecto: Optional[float] = None) -> Optional[float]:
    if isinstance(v, list):  # OSMnx puede dejar listas al simplificar
        vals = [_a_float(x) for x in v]
        vals = [x for x in vals if x is not None]
        return sum(vals) / len(vals) if vals else defecto
    try:
        return float(v)
    except (TypeError, ValueError):
        return defecto


def normalizar(G: nx.MultiDiGraph, fuente: str) -> nx.MultiDiGraph:
    """Garantiza length/speed_kph/travel_time numéricos en todas las aristas."""
    for _, d in G.nodes(data=True):
        d["x"], d["y"] = float(d["x"]), float(d["y"])
    for u, v, d in G.edges(data=True):
        length = _a_float(d.get("length"))
        if length is None:
            nu, nv = G.nodes[u], G.nodes[v]
            length = haversine_m(nu["y"], nu["x"], nv["y"], nv["x"])
        speed = _a_float(d.get("speed_kph"), VELOCIDAD_DEFECTO_KPH) or VELOCIDAD_DEFECTO_KPH
        tt = _a_float(d.get("travel_time"))
        if tt is None or tt <= 0:
            tt = length / (speed / 3.6)
        d["length"], d["speed_kph"], d["travel_time"] = length, speed, tt
        d["oneway"] = _a_bool(d.get("oneway", False))
    G.graph.setdefault("crs", "epsg:4326")
    G.graph["fuente"] = fuente
    return G


# ---------------------------------------------------------------- OSMnx real
def _osmnx():
    try:
        import osmnx as ox
    except ImportError as e:
        raise RuntimeError("Falta OSMnx. Instala con: python -m pip install osmnx") from e
    return ox


def obtener_red_osm(lat: float, lon: float, radio_m: float,
                    cache_dir: Optional[Path] = None, usar_cache: bool = True) -> nx.MultiDiGraph:
    """Helper radial legado acotado (no usado por la app integrada).

    La vía normal `red_para_solicitud(..., fuente='osm')` usa cobertura.obtener
    con polígono, margen y límites explícitos sin el recorte radial a 8 km.
    """
    radio_m = min(max(float(radio_m), RADIO_MIN_M), RADIO_MAX_M)
    archivo = ruta_cache(lat, lon, radio_m, cache_dir)
    ox = _osmnx()
    if usar_cache and archivo.exists():
        G = ox.load_graphml(archivo)
        G.graph["desde_cache"] = True
        return normalizar(G, "osm")

    try:
        G = ox.graph_from_point((lat, lon), dist=radio_m, network_type="drive", simplify=True)
    except Exception as e:  # sin internet, zona vacía, etc.
        raise RuntimeError(f"No se pudo descargar la red de OpenStreetMap: {e}") from e

    # OSMnx 2.x: ox.routing.*; OSMnx 1.x: ox.add_edge_*
    rt = getattr(ox, "routing", ox)
    G = rt.add_edge_speeds(G, fallback=VELOCIDAD_DEFECTO_KPH)
    G = rt.add_edge_travel_times(G)
    G = normalizar(G, "osm")
    G.graph["desde_cache"] = False
    ox.save_graphml(G, archivo)
    return G


# ----------------------------------------------------------- red sintética
def red_sintetica(lat: float, lon: float, filas: int = 7, columnas: int = 7,
                  paso_m: float = 200.0, velocidad_kph: float = VELOCIDAD_DEFECTO_KPH,
                  calles_un_sentido: bool = True) -> nx.MultiDiGraph:
    """Cuadrícula centrada en (lat, lon). Sin internet; mismo formato que OSM.

    Con `calles_un_sentido`, la fila central va solo hacia el este y la columna
    central solo hacia el norte (prueba de sentidos de circulación).
    """
    G = nx.MultiDiGraph(crs="epsg:4326")
    f0, c0 = (filas - 1) / 2, (columnas - 1) / 2
    nid = lambda i, j: i * columnas + j  # noqa: E731
    for i in range(filas):
        for j in range(columnas):
            y, x = desplazar(lat, lon, (i - f0) * paso_m, (j - c0) * paso_m)
            G.add_node(nid(i, j), x=x, y=y)

    fila_ow, col_ow = filas // 2, columnas // 2

    def calle(a, b, un_sentido):
        na, nb = G.nodes[a], G.nodes[b]
        length = haversine_m(na["y"], na["x"], nb["y"], nb["x"])
        attrs = dict(length=length, speed_kph=velocidad_kph,
                     travel_time=length / (velocidad_kph / 3.6), oneway=un_sentido)
        G.add_edge(a, b, **attrs)
        if not un_sentido:
            G.add_edge(b, a, **attrs)

    for i in range(filas):
        for j in range(columnas):
            if j + 1 < columnas:  # este-oeste
                calle(nid(i, j), nid(i, j + 1), calles_un_sentido and i == fila_ow)
            if i + 1 < filas:     # sur-norte
                calle(nid(i, j), nid(i + 1, j), calles_un_sentido and j == col_ow)
    return normalizar(G, "sintetica")


# ------------------------------------------------------ desde la solicitud
def centro_y_radio(solicitud) -> tuple[float, float, float]:
    """Usa la zona de operación; si no hay, un círculo que cubre todos los puntos."""
    if solicitud.zona_operacion is not None:
        z = solicitud.zona_operacion
        return z.lat, z.lon, min(max(z.radio_m, RADIO_MIN_M), RADIO_MAX_M)
    pts = [solicitud.base] + list(solicitud.destinos)
    lat = sum(p.lat for p in pts) / len(pts)
    lon = sum(p.lon for p in pts) / len(pts)
    r = max(haversine_m(lat, lon, p.lat, p.lon) for p in pts) + MARGEN_M
    return lat, lon, min(max(r, RADIO_MIN_M), RADIO_MAX_M)


def red_para_solicitud(solicitud, fuente: str = "osm", **kw) -> nx.MultiDiGraph:
    if fuente == "osm":
        from engine.cobertura import obtener
        return obtener(solicitud, **kw)
    lat, lon, r = centro_y_radio(solicitud)
    if fuente == "sintetica":
        lado = max(3, int(2 * r // kw.get("paso_m", 200.0)) + 1)
        return red_sintetica(lat, lon, filas=lado, columnas=lado, **kw)
    raise ValueError(f"Fuente de red desconocida: {fuente}")


def resumen_red(G: nx.MultiDiGraph) -> dict:
    """Bloque `Resultado.red` (aristas_excluidas se rellena en la tarea 4)."""
    return {
        "nodos": G.number_of_nodes(),
        "aristas": G.number_of_edges(),
        "aristas_excluidas": 0,
        "fuente": G.graph.get("fuente", "desconocida"),
        "desde_cache": bool(G.graph.get("desde_cache", False)),
    }
