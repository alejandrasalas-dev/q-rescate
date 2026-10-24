"""
Motor de Q-Rescate (Tabla 2, tareas 3-6 y 8).

Función principal para la interfaz:

    from engine.motor import calcular_recorridos
    resultado = calcular_recorridos(solicitud)          # Solicitud o dict
    resultado.a_dict()                                  # JSON para dibujar

Pasos:
  3. Ajusta base y destinos al nodo transitable más cercano.
  4. Quita los tramos dentro de los círculos de exclusión y detecta destinos inaccesibles.
  5. Matriz de tiempos (min) con Dijkstra; la base es el índice 0.
  6. Ejecuta exact_tour, greedy_tour y qaoa_tour de routing.py.
  8. Devuelve geometrías [[lat, lon], ...], métricas y exportación JSON/CSV.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Callable, Optional

import networkx as nx
import numpy as np

from engine.contrato import Circulo, Punto, Resultado, ResultadoMetodo, Solicitud
from engine.red_vial import haversine_m, red_para_solicitud, resumen_red

MAX_QUBITS = 9                 # límite duro del simulador en la demo
DIST_AJUSTE_AVISO_M = 300.0    # avisar si un punto queda lejos de la calle

Progreso = Optional[Callable[[str], None]]


# --------------------------------------------------------- tarea 4: exclusiones
def _dentro(lat: float, lon: float, circulos: list[Circulo]) -> bool:
    return any(haversine_m(lat, lon, c.lat, c.lon) <= c.radio_m for c in circulos)


def _puntos_arista(G, u, v, d) -> list[tuple[float, float]]:
    """(lat, lon) de los extremos, la geometría (si hay) y el punto medio."""
    pts = [(G.nodes[u]["y"], G.nodes[u]["x"]), (G.nodes[v]["y"], G.nodes[v]["x"])]
    geom = d.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        pts += [(y, x) for x, y in geom.coords]
    pts.append(((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2))
    return pts


def aplicar_exclusiones(G: nx.MultiDiGraph, exclusiones: list[Circulo]) -> tuple[nx.MultiDiGraph, int]:
    """Copia del grafo sin los tramos que tocan algún círculo. Devuelve (grafo, n_quitadas)."""
    H = G.copy()
    if not exclusiones:
        return H, 0
    quitar = [(u, v, k) for u, v, k, d in H.edges(keys=True, data=True)
              if any(_dentro(la, lo, exclusiones) for la, lo in _puntos_arista(H, u, v, d))]
    H.remove_edges_from(quitar)
    return H, len(quitar)


# ------------------------------------------------- tarea 3: ajuste a la red
def _componente_principal(G: nx.MultiDiGraph) -> list:
    """Nodos de la mayor componente fuertemente conexa (evita fragmentos del borde)."""
    if G.number_of_nodes() == 0:
        return []
    return list(max(nx.strongly_connected_components(G), key=len))


def ajustar_puntos(G: nx.MultiDiGraph, puntos: list[Punto], candidatos: list) -> list[dict]:
    """Nodo más cercano (haversine vectorizado) para cada punto."""
    if not candidatos:
        raise ValueError("La red vial está vacía en esta zona.")
    lats = np.radians([G.nodes[n]["y"] for n in candidatos])
    lons = np.radians([G.nodes[n]["x"] for n in candidatos])
    salida = []
    for p in puntos:
        la, lo = np.radians(p.lat), np.radians(p.lon)
        a = np.sin((lats - la) / 2) ** 2 + np.cos(la) * np.cos(lats) * np.sin((lons - lo) / 2) ** 2
        dist = 2 * 6_371_008.8 * np.arcsin(np.sqrt(a))
        k = int(np.argmin(dist))
        nodo = candidatos[k]
        salida.append({
            "id": p.id, "nombre": p.nombre, "lat": p.lat, "lon": p.lon,
            "nodo": nodo if isinstance(nodo, (int, str)) else str(nodo),
            "lat_red": float(G.nodes[nodo]["y"]), "lon_red": float(G.nodes[nodo]["x"]),
            "distancia_m": round(float(dist[k]), 1),
        })
    return salida


# ---------------------------------------------- tarea 5: matriz de tiempos
def matriz_tiempos(G: nx.MultiDiGraph, nodos: list) -> tuple[np.ndarray, dict]:
    """Minutos entre todos los pares (dirigido). inf si no hay camino. También caminos."""
    n = len(nodos)
    M = np.full((n, n), np.inf)
    caminos: dict[tuple[int, int], list] = {}
    for i, s in enumerate(nodos):
        dist, path = nx.single_source_dijkstra(G, s, weight="travel_time")
        for j, t in enumerate(nodos):
            if t in dist:
                M[i, j] = dist[t] / 60.0
                caminos[(i, j)] = path[t]
    np.fill_diagonal(M, 0.0)
    return M, caminos


def destinos_inaccesibles(M: np.ndarray) -> list[int]:
    """Índices (1..n) sin ida o sin vuelta desde la base."""
    return [j for j in range(1, len(M)) if not (np.isfinite(M[0, j]) and np.isfinite(M[j, 0]))]


# ------------------------------------------------- tarea 8: geometría
def _coords_tramo(G: nx.MultiDiGraph, u, v) -> list[list[float]]:
    datos = G.get_edge_data(u, v)
    d = min(datos.values(), key=lambda e: e.get("travel_time", float("inf")))
    geom = d.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        coords=[[float(y), float(x)] for x, y in geom.coords]
        start=G.nodes[u]
        if haversine_m(start['y'],start['x'],*coords[-1])<haversine_m(start['y'],start['x'],*coords[0]):coords.reverse()
        return coords
    return [[G.nodes[u]["y"], G.nodes[u]["x"]], [G.nodes[v]["y"], G.nodes[v]["x"]]]


def geometria_recorrido(G: nx.MultiDiGraph, caminos: dict, indices: list[int]) -> list[list[float]]:
    """Polilínea [[lat, lon], ...] siguiendo las calles para la secuencia de índices."""
    linea: list[list[float]] = []
    for a, b in zip(indices, indices[1:]):
        nodos = caminos.get((a, b), [])
        for u, v in zip(nodos, nodos[1:]):
            tramo = _coords_tramo(G, u, v)
            if linea and tramo and linea[-1] == tramo[0]:
                tramo = tramo[1:]
            linea.extend(tramo)
    return linea


# ---------------------------------------------- tarea 6: métodos
def _ejecutar_metodo(metodo: str, M: np.ndarray, sol: Solicitud) -> dict:
    import routing  # código existente del repositorio
    if metodo == "exacto":
        return routing.exact_tour(M)
    if metodo == "voraz":
        return routing.greedy_tour(M)
    if metodo == "qaoa":
        n = len(M) - 1
        if n < 2:
            return {"status": "skipped", "reason": "QAOA necesita al menos 2 destinos accesibles."}
        return routing.qaoa_tour(M, seed=sol.semilla, shots=sol.shots,
                                 max_qubits=min(sol.max_qubits, MAX_QUBITS))
    raise ValueError(metodo)


def _tour_valido(tour, n: int) -> bool:
    return tour is not None and sorted(tour) == list(range(n))


# --------------------------------------------------------------- principal
def calcular_recorridos(solicitud, fuente: str = "osm", G: Optional[nx.MultiDiGraph] = None,
                        progreso: Progreso = None, parcial=None) -> Resultado:
    """Punto de entrada único. `G` permite inyectar una red (tests)."""
    avisar = progreso or (lambda _m: None)
    try:
        sol = Solicitud.desde_dict(solicitud) if isinstance(solicitud, dict) else solicitud
        sol.validar()
    except (KeyError, TypeError, ValueError) as e:
        return Resultado(estado="error", mensaje=f"Solicitud inválida: {e}")

    try:
        if G is None:
            avisar("Obteniendo calles…")
            G = red_para_solicitud(sol, fuente=fuente)
    except Exception as e:
        return Resultado(estado="error", mensaje=str(e))

    avisar("Aplicando exclusiones…")
    H, n_excl = aplicar_exclusiones(G, sol.exclusiones)
    info_red = resumen_red(G)
    info_red["aristas_excluidas"] = n_excl
    if G.graph.get('coverage_json'):info_red['coverage']=json.loads(G.graph['coverage_json'])
    if G.graph.get('cache_key'):info_red['cache_key']=G.graph['cache_key']

    avisar("Ajustando puntos a la red…")
    principal = set(_componente_principal(G))
    # Sin exigir grado > 0 en H: un destino aislado por exclusiones debe quedar inaccesible,
    # no "saltar" a otra calle.
    candidatos = [n for n in principal
                  if not _dentro(G.nodes[n]["y"], G.nodes[n]["x"], sol.exclusiones)]
    try:
        puntos = ajustar_puntos(G, [sol.base] + sol.destinos, candidatos)
    except ValueError as e:
        return Resultado(estado="error", mensaje=str(e), red=info_red)
    for p in puntos:
        p["lejos_de_calle"] = p["distancia_m"] > DIST_AJUSTE_AVISO_M
    # Never present a far-away stop snapped to a small/disconnected road fragment as served.
    if any(p['distancia_m']>1000 for p in puntos):
        return Resultado(estado='error',mensaje='Cobertura vial insuficiente: ajuste a la vía mayor de 1000 m. Selecciona un punto más cercano a una vía transitable; no se calcularon rutas.',puntos=puntos,red=info_red)

    avisar("Calculando tiempos entre puntos…")
    M_total, _ = matriz_tiempos(H, [p["nodo"] for p in puntos])
    ids = [p["id"] for p in puntos]
    excl_idx = [j for j in range(1, len(puntos))
                if _dentro(sol.destinos[j - 1].lat, sol.destinos[j - 1].lon, sol.exclusiones)]
    malos = sorted(set(destinos_inaccesibles(M_total)) | set(excl_idx))
    inaccesibles = [ids[j] for j in malos]
    activos = [0] + [j for j in range(1, len(puntos)) if j not in malos]

    base_kw = dict(puntos=puntos, inaccesibles=inaccesibles, red=info_red)
    if _dentro(sol.base.lat, sol.base.lon, sol.exclusiones):
        return Resultado(estado="error", mensaje="La base está dentro de una zona de exclusión.", **base_kw)
    if len(activos) < 2:
        return Resultado(estado="error", mensaje="Ningún destino es accesible desde la base.",
                         matriz_min=_lista(M_total), **base_kw)

    nodos_activos = [puntos[j]["nodo"] for j in activos]
    M, caminos = matriz_tiempos(H, nodos_activos)
    ids_act = [ids[j] for j in activos]
    n = len(activos) - 1

    metodos: list[ResultadoMetodo] = []
    def publicar():
        if parcial:
            parcial(Resultado(estado='en_curso',mensaje='Resultados parciales; cálculo en curso.',
                              matriz_min=_lista(M),metodos=metodos,**base_kw).a_dict())
    costo_exacto = None
    orden_metodos = sorted(sol.metodos, key=lambda m: ("exacto", "voraz", "qaoa").index(m))
    for m in orden_metodos:
        avisar(f"Ejecutando método {m}…")
        t0 = time.perf_counter()
        try:
            r = _ejecutar_metodo(m, M, sol)
        except Exception as e:  # noqa: BLE001 — se informa a la interfaz
            metodos.append(ResultadoMetodo(m, "error", duracion_s=time.perf_counter() - t0,
                                           detalle=f"{type(e).__name__}: {e}"))
            publicar()
            continue
        dur = r.get("runtime_seconds", time.perf_counter() - t0)
        if r.get("status") == "skipped":
            metodos.append(ResultadoMetodo(m, "omitido", duracion_s=dur, detalle=r.get("reason", "")))
            publicar()
            continue
        tour = r.get("tour")
        valida = _tour_valido(tour, n)
        rm = ResultadoMetodo(m, "ok", valida=valida, duracion_s=round(float(dur), 4))
        if valida:
            idx = [0] + [i + 1 for i in tour] + [0]
            rm.orden = [ids_act[i] for i in idx]
            rm.costo_min = round(float(r["cost"]), 3)
            rm.geometria = geometria_recorrido(H, caminos, idx)
            if m == "exacto":
                costo_exacto = rm.costo_min
        else:
            rm.detalle = "QAOA devolvió una muestra que no es un recorrido válido."
        if m == "qaoa":
            info = f"{r.get('qubits')} qubits, {r.get('backend', '')}".strip()
            rm.detalle = f"{rm.detalle} {info}".strip()
        metodos.append(rm)
        publicar()

    if costo_exacto is not None:
        for rm in metodos:
            if rm.costo_min is not None:
                rm.gap_pct = (round(100 * (rm.costo_min - costo_exacto) / abs(costo_exacto), 2)
                              if costo_exacto else (0.0 if rm.costo_min==0 else None))

    msg = "Cálculo completado."
    if inaccesibles:
        msg += f" Destinos inaccesibles: {', '.join(inaccesibles)}."
    lejos = [p["id"] for p in puntos if p["lejos_de_calle"]]
    if lejos:
        msg += f" Lejos de una calle (>{int(DIST_AJUSTE_AVISO_M)} m): {', '.join(lejos)}."
    return Resultado(estado="ok", mensaje=msg, matriz_min=_lista(M), metodos=metodos, **base_kw)


def _lista(M: np.ndarray) -> list[list[Optional[float]]]:
    """Matriz JSON-segura: inf -> None."""
    return [[round(float(x), 3) if np.isfinite(x) else None for x in fila] for fila in M]


# ---------------------------------------------------------- exportación
def exportar_json(resultado: Resultado | dict, ruta: str | Path) -> Path:
    datos = resultado.a_dict() if isinstance(resultado, Resultado) else resultado
    ruta = Path(ruta)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def exportar_csv(resultado: Resultado | dict, ruta: str | Path) -> Path:
    """Una fila por método (sin geometría). utf-8-sig para abrir bien en Excel."""
    datos = resultado.a_dict() if isinstance(resultado, Resultado) else resultado
    ruta = Path(ruta)
    campos = ["metodo", "estado", "orden", "costo_min", "gap_pct", "valida", "duracion_s", "detalle"]
    with ruta.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for m in datos.get("metodos", []):
            fila = {k: m.get(k) for k in campos}
            fila["orden"] = " → ".join(m.get("orden") or [])
            w.writerow(fila)
    return ruta
