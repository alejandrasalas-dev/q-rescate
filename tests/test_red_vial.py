"""Tests de engine/red_vial.py sin internet (red sintética + OSMnx simulado)."""
import pickle
import sys
import types

import networkx as nx
import pytest

from engine import red_vial as rv
from engine.contrato import Circulo, Punto, Solicitud

LAT, LON = -11.2537, -74.6378  # Satipo, Junín


def test_haversine_y_desplazar():
    lat2, lon2 = rv.desplazar(LAT, LON, 300, 400)
    assert rv.haversine_m(LAT, LON, lat2, lon2) == pytest.approx(500, rel=1e-3)


def test_red_sintetica_formato():
    G = rv.red_sintetica(LAT, LON, filas=5, columnas=5, paso_m=200)
    assert isinstance(G, nx.MultiDiGraph)
    assert G.number_of_nodes() == 25
    assert G.graph["fuente"] == "sintetica" and G.graph["crs"] == "epsg:4326"
    for _, d in G.nodes(data=True):
        assert {"x", "y"} <= d.keys()
    for _, _, d in G.edges(data=True):
        assert d["length"] == pytest.approx(200, rel=1e-2)
        assert d["travel_time"] == pytest.approx(d["length"] / (30 / 3.6))
    assert nx.is_strongly_connected(G)


def test_red_sintetica_sentidos():
    G = rv.red_sintetica(LAT, LON, filas=5, columnas=5)
    # fila central (i=2) solo hacia el este: 10 -> 11 sí, 11 -> 10 no
    assert G.has_edge(10, 11) and not G.has_edge(11, 10)
    # columna central (j=2) solo hacia el norte: 2 -> 7 sí, 7 -> 2 no
    assert G.has_edge(2, 7) and not G.has_edge(7, 2)
    # calle normal en doble sentido
    assert G.has_edge(0, 1) and G.has_edge(1, 0)
    # el sentido cambia los tiempos: ir 11->10 obliga a rodear
    ida = nx.shortest_path_length(G, 10, 11, weight="travel_time")
    vuelta = nx.shortest_path_length(G, 11, 10, weight="travel_time")
    assert vuelta > ida


def test_normalizar_atributos_texto_y_listas():
    G = nx.MultiDiGraph()
    G.add_node(1, x="-80.63", y="-5.19")
    G.add_node(2, x="-80.629", y="-5.19")
    G.add_edge(1, 2, length="110.5", speed_kph=["40", "60"], oneway="True")
    G.add_edge(2, 1)  # sin atributos
    rv.normalizar(G, "osm")
    d12 = G.get_edge_data(1, 2)[0]
    assert d12["length"] == 110.5 and d12["speed_kph"] == 50.0 and d12["oneway"] is True
    assert d12["travel_time"] == pytest.approx(110.5 / (50 / 3.6))
    d21 = G.get_edge_data(2, 1)[0]
    assert d21["length"] > 0 and d21["speed_kph"] == rv.VELOCIDAD_DEFECTO_KPH
    assert d21["oneway"] is False


def _solicitud(zona=None):
    return Solicitud(
        base=Punto("H", LAT, LON),
        destinos=[Punto("A", -11.2480, -74.6340), Punto("B", -11.2600, -74.6420)],
        zona_operacion=zona,
    )


def test_centro_y_radio():
    lat, lon, r = rv.centro_y_radio(_solicitud(Circulo(LAT, LON, 3000)))
    assert (lat, lon, r) == (LAT, LON, 3000)
    lat, lon, r = rv.centro_y_radio(_solicitud(Circulo(LAT, LON, 50_000)))
    assert r == rv.RADIO_MAX_M
    sol = _solicitud()
    lat, lon, r = rv.centro_y_radio(sol)
    for p in [sol.base] + sol.destinos:
        assert rv.haversine_m(lat, lon, p.lat, p.lon) + rv.MARGEN_M <= r + 1e-6


def test_red_para_solicitud_sintetica_cubre_puntos():
    sol = _solicitud()
    G = rv.red_para_solicitud(sol, fuente="sintetica")
    assert G.graph["fuente"] == "sintetica"
    ys = [d["y"] for _, d in G.nodes(data=True)]
    xs = [d["x"] for _, d in G.nodes(data=True)]
    for p in [sol.base] + sol.destinos:
        assert min(ys) <= p.lat <= max(ys) and min(xs) <= p.lon <= max(xs)
    with pytest.raises(ValueError):
        rv.red_para_solicitud(sol, fuente="otra")


def test_ruta_cache_estable():
    a = rv.ruta_cache(LAT, LON, 3000)
    assert a == rv.ruta_cache(LAT + 1e-6, LON, 3010)   # mismo redondeo
    assert a != rv.ruta_cache(LAT, LON, 3500)
    assert a.suffix == ".graphml"


@pytest.fixture
def osmnx_falso(monkeypatch, tmp_path):
    """Sustituye osmnx por un módulo mínimo que cuenta descargas."""
    llamadas = {"descargas": 0}
    ox = types.ModuleType("osmnx")

    def graph_from_point(center, dist, network_type, simplify):
        assert network_type == "drive"
        llamadas["descargas"] += 1
        G = rv.red_sintetica(center[0], center[1], filas=3, columnas=3)
        for _, _, d in G.edges(data=True):  # como OSM crudo: sin tiempos
            d.pop("travel_time"); d.pop("speed_kph")
        return G

    def add_edge_speeds(G, fallback):
        for _, _, d in G.edges(data=True):
            d["speed_kph"] = fallback
        return G

    def add_edge_travel_times(G):
        for _, _, d in G.edges(data=True):
            d["travel_time"] = d["length"] / (d["speed_kph"] / 3.6)
        return G

    ox.graph_from_point = graph_from_point
    ox.routing = types.SimpleNamespace(add_edge_speeds=add_edge_speeds,
                                       add_edge_travel_times=add_edge_travel_times)
    ox.save_graphml = lambda G, f: f.write_bytes(pickle.dumps(G))
    ox.load_graphml = lambda f: pickle.loads(f.read_bytes())
    monkeypatch.setitem(sys.modules, "osmnx", ox)
    monkeypatch.setenv("QRESCATE_CACHE", str(tmp_path))
    return llamadas


def test_osm_descarga_y_reutiliza_cache(osmnx_falso, tmp_path):
    G1 = rv.obtener_red_osm(LAT, LON, 1000)
    assert osmnx_falso["descargas"] == 1 and G1.graph["desde_cache"] is False
    assert all("travel_time" in d for _, _, d in G1.edges(data=True))
    assert len(list(tmp_path.glob("red_*.graphml"))) == 1

    G2 = rv.obtener_red_osm(LAT, LON, 1000)
    assert osmnx_falso["descargas"] == 1 and G2.graph["desde_cache"] is True
    assert rv.resumen_red(G2) == {"nodos": 9, "aristas": G1.number_of_edges(),
                                  "aristas_excluidas": 0, "fuente": "osm",
                                  "desde_cache": True}

    rv.obtener_red_osm(LAT, LON, 1000, usar_cache=False)
    assert osmnx_falso["descargas"] == 2


def test_osm_error_descarga_es_legible(osmnx_falso, monkeypatch):
    def falla(*a, **k):
        raise ConnectionError("sin red")
    monkeypatch.setattr(sys.modules["osmnx"], "graph_from_point", falla)
    with pytest.raises(RuntimeError, match="OpenStreetMap"):
        rv.obtener_red_osm(LAT, LON, 1000, usar_cache=False)


def test_sin_osmnx_instalado(monkeypatch):
    monkeypatch.setitem(sys.modules, "osmnx", None)
    with pytest.raises(RuntimeError, match="pip install osmnx"):
        rv.obtener_red_osm(LAT, LON, 1000)
