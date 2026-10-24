"""Tests del motor (tareas 3-8) sobre la red sintética, sin internet."""
import csv
import json

import numpy as np
import pytest

from engine import motor
from engine.contrato import Circulo, Punto, Solicitud
from engine.ejecutor import Calculo, ejecutar
from engine.ejemplos import EJEMPLOS, ejemplo
from engine.red_vial import desplazar, haversine_m, red_sintetica

LAT, LON = -11.2537, -74.6378  # Satipo
PASO = 200.0


def nodo(i, j):
    """(lat, lon) del nodo (fila i, columna j) de la cuadrícula 7x7."""
    return desplazar(LAT, LON, (i - 3) * PASO, (j - 3) * PASO)


def punto(pid, i, j, d_norte=0.0):
    la, lo = nodo(i, j)
    la, lo = desplazar(la, lo, d_norte, 0)
    return Punto(pid, la, lo, f"P{pid}")


@pytest.fixture
def G():
    return red_sintetica(LAT, LON, filas=7, columnas=7, paso_m=PASO)


def sol(destinos, exclusiones=(), metodos=("exacto", "voraz"), base=(3, 3)):
    return Solicitud(base=punto("H", *base), destinos=list(destinos),
                     exclusiones=list(exclusiones), metodos=list(metodos))


DEST3 = [punto("A", 5, 1), punto("B", 1, 5), punto("C", 5, 5)]


# ------------------------------------------------------------ tarea 3
def test_ajuste_a_nodo_mas_cercano(G):
    r = motor.calcular_recorridos(sol([punto("A", 5, 1, d_norte=30), punto("B", 1, 5)]), G=G)
    a = next(p for p in r.puntos if p["id"] == "A")
    assert a["nodo"] == 5 * 7 + 1
    assert a["distancia_m"] == pytest.approx(30, abs=1)
    assert a["lejos_de_calle"] is False


# ------------------------------------------------------------ tareas 5-6
def test_recorrido_completo_exacto_y_voraz(G):
    r = motor.calcular_recorridos(sol(DEST3), G=G)
    assert r.estado == "ok", r.mensaje
    assert r.red["fuente"] == "sintetica" and r.red["aristas_excluidas"] == 0
    assert len(r.matriz_min) == 4
    ex = next(m for m in r.metodos if m.metodo == "exacto")
    vo = next(m for m in r.metodos if m.metodo == "voraz")
    for m in (ex, vo):
        assert m.estado == "ok" and m.valida
        assert m.orden[0] == m.orden[-1] == "H" and sorted(m.orden[1:-1]) == ["A", "B", "C"]
        # costo = suma de la matriz a lo largo del orden
        idx = [["H", "A", "B", "C"].index(x) for x in m.orden]
        assert m.costo_min == pytest.approx(sum(r.matriz_min[a][b] for a, b in zip(idx, idx[1:])), abs=1e-2)
    assert ex.gap_pct == 0.0 and vo.gap_pct >= 0.0
    assert vo.costo_min >= ex.costo_min - 1e-9


def test_matriz_respeta_sentidos(G):
    # Fila central (i=3) es de un solo sentido hacia el este.
    r = motor.calcular_recorridos(sol([punto("A", 3, 4), punto("B", 0, 0)], base=(3, 3)), G=G)
    M = np.array(r.matriz_min)
    un_tramo = PASO / (30 / 3.6) / 60
    assert M[0, 1] == pytest.approx(un_tramo, rel=1e-2)   # H -> A directo
    assert M[1, 0] > M[0, 1] * 2                           # A -> H obliga a rodear


# ------------------------------------------------------------ tarea 8
def test_geometria_sigue_calles_y_cierra(G):
    r = motor.calcular_recorridos(sol(DEST3), G=G)
    ex = r.metodos[0]
    g = ex.geometria
    assert len(g) > 5
    assert haversine_m(*g[0], *nodo(3, 3)) < 1 and haversine_m(*g[-1], *nodo(3, 3)) < 1
    # cada segmento es una arista de la cuadrícula (~200 m)
    for a, b in zip(g, g[1:]):
        assert haversine_m(*a, *b) == pytest.approx(PASO, rel=0.02)
    json.dumps(r.a_dict())  # serializable


# ------------------------------------------------------------ tarea 4
def test_exclusion_desvia_la_ruta(G):
    # Bloquea el tramo entre (3,3) y (4,3) — subida directa desde la base.
    la, lo = desplazar(*nodo(3, 3), PASO / 2, 0)
    excl = Circulo(la, lo, 40)
    r0 = motor.calcular_recorridos(sol([punto("A", 4, 3), punto("B", 0, 0)]), G=G)
    r1 = motor.calcular_recorridos(sol([punto("A", 4, 3), punto("B", 0, 0)], [excl]), G=G)
    assert r1.estado == "ok" and r1.red["aristas_excluidas"] == 1  # columna central: un sentido
    assert r1.matriz_min[0][1] > r0.matriz_min[0][1]
    for p in r1.metodos[0].geometria:
        assert haversine_m(*p, la, lo) > excl.radio_m


def test_destino_aislado_es_inaccesible(G):
    # Esquina (0,0): cortar sus dos únicas calles.
    c1 = Circulo(*desplazar(*nodo(0, 0), 0, PASO / 2), 30)
    c2 = Circulo(*desplazar(*nodo(0, 0), PASO / 2, 0), 30)
    r = motor.calcular_recorridos(sol([punto("A", 0, 0), *DEST3[1:]], [c1, c2]), G=G)
    assert r.estado == "ok", r.mensaje
    assert r.inaccesibles == ["A"]
    assert "A" not in r.metodos[0].orden and "inaccesibles" in r.mensaje


def test_destino_dentro_de_exclusion(G):
    a = punto("A", 5, 1)
    r = motor.calcular_recorridos(sol([a, *DEST3[1:]], [Circulo(a.lat, a.lon, 50)]), G=G)
    assert r.inaccesibles == ["A"]


def test_todos_inaccesibles_es_error(G):
    a, b = punto("A", 5, 1), punto("B", 1, 5)
    r = motor.calcular_recorridos(sol([a, b], [Circulo(a.lat, a.lon, 50), Circulo(b.lat, b.lon, 50)]), G=G)
    assert r.estado == "error" and r.inaccesibles == ["A", "B"]


def test_base_en_exclusion_es_error(G):
    h = punto("H", 3, 3)
    r = motor.calcular_recorridos(sol(DEST3, [Circulo(h.lat, h.lon, 50)]), G=G)
    assert r.estado == "error" and "base" in r.mensaje


def test_solicitud_invalida():
    r = motor.calcular_recorridos({"base": {"id": "H", "lat": 0, "lon": 0}, "destinos": []})
    assert r.estado == "error" and "Solicitud inválida" in r.mensaje


# ------------------------------------------------------------ QAOA (tarea 6)
def test_qaoa_dos_destinos(G):
    pytest.importorskip("qiskit_optimization")
    s = sol([punto("A", 5, 1), punto("B", 1, 5)], metodos=("exacto", "qaoa"))
    r = motor.calcular_recorridos(s, G=G)
    q = next(m for m in r.metodos if m.metodo == "qaoa")
    assert q.estado == "ok" and "4 qubits" in q.detalle
    if q.valida:
        assert q.gap_pct is not None and q.orden[0] == "H"


def test_qaoa_omitido_por_qubits(G):
    s = sol([punto("A", 5, 1), punto("B", 1, 5), punto("C", 5, 5), punto("D", 1, 1)],
            metodos=("exacto", "qaoa"))
    s.max_qubits = 99  # el motor recorta a 9 igualmente
    r = motor.calcular_recorridos(s, G=G)
    q = next(m for m in r.metodos if m.metodo == "qaoa")
    assert q.estado == "omitido" and "16 qubits" in q.detalle


# ------------------------------------------------------------ exportar
def test_exportar_json_csv(G, tmp_path):
    r = motor.calcular_recorridos(sol(DEST3), G=G)
    pj = motor.exportar_json(r, tmp_path / "r.json")
    assert json.loads(pj.read_text(encoding="utf-8"))["estado"] == "ok"
    pc = motor.exportar_csv(r, tmp_path / "r.csv")
    filas = list(csv.DictReader(pc.open(encoding="utf-8-sig")))
    assert [f["metodo"] for f in filas] == ["exacto", "voraz"]
    assert filas[0]["orden"].startswith("H → ")


# ------------------------------------------------------------ ejemplos
def test_ejemplos_validos():
    for nombre in EJEMPLOS:
        Solicitud.desde_dict(ejemplo(nombre)).validar()
    e = ejemplo("satipo_3_destinos"); e["destinos"].clear()
    assert EJEMPLOS["satipo_3_destinos"]["destinos"]  # copia independiente


# ------------------------------------------------------------ tarea 7: proceso aparte
def _ejemplo_rapido():
    e = ejemplo("satipo_con_exclusion")
    e["metodos"] = ["exacto", "voraz"]
    return e


def test_ejecutor_proceso_separado():
    res = ejecutar(_ejemplo_rapido(), fuente="sintetica", timeout_s=60)
    assert res["estado"] == "ok", res["mensaje"]
    assert res["red"]["fuente"] == "sintetica"
    assert [m["metodo"] for m in res["metodos"]] == ["exacto", "voraz"]


def test_ejecutor_cancelar():
    c = Calculo(_ejemplo_rapido(), fuente="sintetica")
    res = c.cancelar()
    assert res["estado"] == "cancelado"
    assert c.consultar() is res


def test_ejecutor_tiempo_agotado():
    res = Calculo(_ejemplo_rapido(), timeout_s=0.001, fuente="sintetica").esperar()
    assert res["estado"] == "tiempo_agotado"


def test_ejecutor_error_legible():
    res = ejecutar(_ejemplo_rapido(), fuente="desconocida", timeout_s=60)
    assert res["estado"] == "error" and "desconocida" in res["mensaje"]
