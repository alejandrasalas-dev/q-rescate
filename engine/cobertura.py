"""Bounded OSM coverage for any selected points in Satipo; no radius truncation.

Operation circle limits eligible stops, not road detours. A buffered convex hull
of stops AND the operation circle is downloaded, capped by the province plus
10 km detour margin. Cache keys include the exact query polygon and policy.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
import networkx as nx

MAX_AREA_KM2=60000
MAX_NODES=250000
MAX_EDGES=750000
MAX_SNAP_M=1000
MARGIN_M=5000
POLICY='satipo-drive-v1'

def _geo():
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform
    forward=Transformer.from_crs(4326,32718,always_xy=True).transform
    inverse=Transformer.from_crs(32718,4326,always_xy=True).transform
    path=Path(__file__).resolve().parents[1]/'desktop'/'qrescate_desktop'/'assets'/'satipo.geojson'
    if not path.exists():path=Path(__file__).resolve().parents[1]/'qrescate_desktop'/'assets'/'satipo.geojson'
    province=shape(json.loads(path.read_text(encoding='utf-8'))['features'][0]['geometry'])
    return province,forward,inverse,transform

def planificar(sol):
    from shapely.geometry import MultiPoint,Point
    province,forward,inverse,transform=_geo()
    points=[sol.base]+sol.destinos
    if any(not province.covers(Point(p.lon,p.lat)) for p in points):
        raise ValueError('Fuera de cobertura: todos los puntos deben pertenecer a Satipo, Junín.')
    if any(not province.covers(Point(c.lon,c.lat)) for c in sol.exclusiones+([sol.zona_operacion] if sol.zona_operacion else [])):
        raise ValueError('Fuera de cobertura: centro de zona fuera de Satipo.')
    projected=[Point(*forward(p.lon,p.lat)) for p in points]
    area=MultiPoint(projected).convex_hull
    if sol.zona_operacion:
        c=sol.zona_operacion
        if not 0<c.radio_m<=250000:raise ValueError('Radio de operación permitido: 0 a 250 km.')
        disk=Point(*forward(c.lon,c.lat)).buffer(c.radio_m,quad_segs=48)
        if any(not disk.covers(p) for p in projected):
            raise ValueError('Hay base o destinos fuera de la zona de operación. Amplía el radio o elimina esa zona; no se recorta silenciosamente.')
        area=area.union(disk).convex_hull
    query=area.buffer(MARGIN_M).intersection(transform(forward,province).buffer(10000))
    km2=query.area/1e6
    if query.is_empty or km2>MAX_AREA_KM2:
        raise ValueError(f'Cobertura solicitada {km2:.0f} km² excede el límite {MAX_AREA_KM2} km².')
    polygon=transform(inverse,query)
    return polygon,{'policy':POLICY,'area_km2':round(km2,3),'margin_m':MARGIN_M,
                    'operation_policy':'eligible_points_only_detours_allowed','max_snap_m':MAX_SNAP_M,
                    'bounds_lng_lat':list(polygon.bounds)}

def obtener(sol,cache_dir=None,usar_cache=True):
    from engine.red_vial import _osmnx,normalizar,directorio_cache,VELOCIDAD_DEFECTO_KPH
    polygon,coverage=planificar(sol)
    ox=_osmnx()
    # The whole process also has an external deadline enforced by Calculo.
    ox.settings.requests_timeout=45
    ox.settings.use_cache=True
    root=Path(cache_dir) if cache_dir else directorio_cache()
    root.mkdir(parents=True,exist_ok=True)
    ox.settings.cache_folder=str(root/'http')
    ox.settings.log_console=False
    key=hashlib.sha256(POLICY.encode()+polygon.wkb).hexdigest()[:24]
    path=root/f'coverage_{key}.graphml'
    cached=usar_cache and path.exists()
    if cached:
        G=ox.load_graphml(path)
    else:
        try:
            G=ox.graph_from_polygon(polygon,network_type='drive',simplify=True,retain_all=True,truncate_by_edge=True)
            G=ox.routing.add_edge_speeds(G,fallback=VELOCIDAD_DEFECTO_KPH)
            G=ox.routing.add_edge_travel_times(G)
        except Exception as exc:
            raise RuntimeError(f'No se pudo descargar la cobertura OSM solicitada ({coverage["area_km2"]:.0f} km²): {exc}. No se usó red sintética.') from exc
    if G.number_of_nodes()>MAX_NODES or G.number_of_edges()>MAX_EDGES:
        raise ValueError(f'Red excede recursos: máximo {MAX_NODES} nodos y {MAX_EDGES} aristas. Reduce la selección o usa una caché preparada con límites revisados.')
    G=normalizar(G,'osm')
    G.graph['desde_cache']=cached
    G.graph['coverage_json']=json.dumps(coverage)
    G.graph['cache_key']=key
    if not cached:
        tmp=path.with_suffix('.tmp.graphml')
        ox.save_graphml(G,tmp);tmp.replace(path)
    return G
