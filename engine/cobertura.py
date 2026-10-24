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

OVERPASS_ENDPOINTS=('https://overpass-api.de/api','https://overpass.private.coffee/api')

class OSMDownloadError(RuntimeError):
    def __init__(self,attempts):
        self.attempts=attempts
        super().__init__('No se pudieron descargar las calles: los servidores OSM no están disponibles ahora. Reintenta en unos momentos o utiliza un escenario cuya red ya esté guardada en caché. No es un fallo de QAOA.')

def _fail_retryable_response(response,*args,**kwargs):
    # OSMnx otherwise retries 429/504 recursively with 55-second sleeps. Let our
    # bounded endpoint loop choose another real OSM server instead.
    if response.status_code in (429,502,503,504):response.raise_for_status()

def _probe_endpoint(endpoint):
    import requests
    response=requests.get(endpoint+'/status',timeout=(5,7),headers={'User-Agent':'Q-Rescate/1.0 (OSMnx desktop)'})
    response.raise_for_status()
    # Respect occupied slots without blocking the whole job on one instance.
    lines=response.text.splitlines()
    if len(lines)>4 and lines[4].startswith(('Slot ','Currently ')):
        raise RuntimeError('Servidor ocupado; se probará otra instancia OSM.')

def _download(ox,polygon,progreso):
    previous={key:getattr(ox.settings,key) for key in ('overpass_url','requests_kwargs')}
    attempts=[]
    try:
        for index,endpoint in enumerate(OVERPASS_ENDPOINTS,1):
            progreso(f'Descargando calles OSM: servidor {index}/{len(OVERPASS_ENDPOINTS)}…')
            try:
                _probe_endpoint(endpoint)
                ox.settings.overpass_url=endpoint
                options=dict(previous['requests_kwargs'])
                hooks=dict(options.get('hooks',{}));hooks['response']=[_fail_retryable_response]
                options['hooks']=hooks;ox.settings.requests_kwargs=options
                graph=ox.graph_from_polygon(polygon,network_type='drive',simplify=True,retain_all=True,truncate_by_edge=True)
                graph.graph['overpass_endpoint']=endpoint
                return graph
            except Exception as exc:
                attempts.append({'endpoint':endpoint,'type':type(exc).__name__,'detail':str(exc)})
        raise OSMDownloadError(attempts)
    finally:
        for key,value in previous.items():setattr(ox.settings,key,value)

def _covering_cache(root,polygon):
    from shapely.geometry import shape
    # Only manifests recording the FULL original query polygon are eligible.
    # Never infer coverage merely from a graph's bounding box or nearest nodes.
    manifests=sorted(root.glob('coverage_*.coverage.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]
    for manifest in manifests:
        try:
            info=json.loads(manifest.read_text(encoding='utf-8'))
            path=root/info['graph_file']
            if path.parent!=root or not path.exists() or info.get('policy')!=POLICY:continue
            if shape(info['polygon']).covers(polygon):return path
        except (OSError,ValueError,KeyError,TypeError):continue
    return None

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

def obtener(sol,cache_dir=None,usar_cache=True,progreso=None):
    from engine.red_vial import _osmnx,normalizar,directorio_cache,VELOCIDAD_DEFECTO_KPH
    polygon,coverage=planificar(sol)
    avisar=progreso or (lambda message:None)
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
    if usar_cache and not path.exists():
        covering=_covering_cache(root,polygon)
        if covering is not None:path=covering
    cached=usar_cache and path.exists()
    if cached:
        avisar('Usando calles OSM guardadas en caché (sin descargar)…')
        G=ox.load_graphml(path)
        actual=json.loads(G.graph.get('coverage_json','{}'))
        if actual:
            actual['requested_area_km2']=coverage['area_km2'];coverage=actual
    else:
        G=_download(ox,polygon,avisar)
        G=ox.routing.add_edge_speeds(G,fallback=VELOCIDAD_DEFECTO_KPH)
        G=ox.routing.add_edge_travel_times(G)
    if G.number_of_nodes()>MAX_NODES or G.number_of_edges()>MAX_EDGES:
        raise ValueError(f'Red excede recursos: máximo {MAX_NODES} nodos y {MAX_EDGES} aristas. Reduce la selección o usa una caché preparada con límites revisados.')
    G=normalizar(G,'osm')
    G.graph['desde_cache']=cached
    G.graph['coverage_json']=json.dumps(coverage)
    G.graph['cache_key']=path.stem.removeprefix('coverage_')
    if not cached:
        tmp=path.with_suffix('.tmp.graphml')
        ox.save_graphml(G,tmp);tmp.replace(path)
    if not cached or path.stem=='coverage_'+key:
        from shapely.geometry import mapping
        manifest=path.with_suffix('.coverage.json')
        data={'policy':POLICY,'graph_file':path.name,'polygon':mapping(polygon)}
        manifest_tmp=manifest.with_suffix('.tmp');manifest_tmp.write_text(json.dumps(data),encoding='utf-8');manifest_tmp.replace(manifest)
    return G
