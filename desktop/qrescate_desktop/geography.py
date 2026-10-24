"""Referential INEI province geometry distributed by Osinergmin, UBIGEO 1206."""
import json
from pathlib import Path

BOUNDARY = json.loads((Path(__file__).parent / 'assets' / 'satipo.geojson').read_text(encoding='utf-8'))
GEOMETRY = BOUNDARY['features'][0]['geometry']
POLYGONS = [GEOMETRY['coordinates']] if GEOMETRY['type'] == 'Polygon' else GEOMETRY['coordinates']

def in_ring(lng, lat, ring):
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        cross = (lng-a[0])*(b[1]-a[1])-(lat-a[1])*(b[0]-a[0])
        if abs(cross) < 1e-10 and min(a[0],b[0])-1e-10 <= lng <= max(a[0],b[0])+1e-10 and min(a[1],b[1])-1e-10 <= lat <= max(a[1],b[1])+1e-10:
            return True
        if (a[1] > lat) != (b[1] > lat) and lng < (b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside

def in_satipo(lat, lng):
    return any(in_ring(lng,lat,p[0]) and not any(in_ring(lng,lat,hole) for hole in p[1:]) for p in POLYGONS)

def validate_coverage(scenario):
    points=([scenario.base] if scenario.base else [])+scenario.destinations+scenario.zones
    outside=[p.name for p in points if not in_satipo(p.lat,p.lng)]
    if outside:
        raise ValueError('Solo se admiten ubicaciones dentro de Satipo, Junín: '+', '.join(outside))
