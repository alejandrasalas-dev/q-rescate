import pytest
from engine.ejemplos import ejemplo
from engine.contrato import Solicitud
from engine.cobertura import planificar
from engine.motor import calcular_recorridos
from engine.red_vial import red_sintetica

def test_wide_query_contains_stops_beyond_eight_km():
    from shapely.geometry import Point
    raw=ejemplo('satipo_3_destinos');raw['zona_operacion']=None
    raw['destinos'][1].update(lat=-11.43,lon=-74.49)
    polygon,info=planificar(Solicitud.desde_dict(raw))
    assert polygon.bounds[3]-polygon.bounds[1]>.2 and info['area_km2']>100
    assert all(polygon.covers(Point(p['lon'],p['lat'])) for p in [raw['base']]+raw['destinos'])

def test_operation_area_rejects_outside_stops_instead_of_cropping():
    raw=ejemplo('satipo_3_destinos');raw['zona_operacion']['radio_m']=100
    with pytest.raises(ValueError,match='zona de operación'):planificar(Solicitud.desde_dict(raw))

def test_32_km_operation_is_not_reduced_to_8_km():
    raw=ejemplo('satipo_3_destinos');raw['zona_operacion']['radio_m']=32000
    _,info=planificar(Solicitud.desde_dict(raw))
    assert info['area_km2']>1000

def test_far_snapping_is_an_error_not_a_successful_route():
    raw=ejemplo('satipo_3_destinos');raw['metodos']=['exacto'];raw['destinos'][0]['lat']-=.2
    result=calcular_recorridos(raw,G=red_sintetica(-11.2537,-74.6378))
    assert result.estado=='error' and '1000 m' in result.mensaje and not result.metodos

def test_engine_emits_classical_partial_result_before_final():
    raw=ejemplo('satipo_3_destinos');raw['metodos']=['exacto','voraz'];parts=[]
    result=calcular_recorridos(raw,fuente='sintetica',parcial=parts.append)
    assert result.estado=='ok' and len(parts)==2
    assert parts[0]['metodos'][0]['metodo']=='exacto' and parts[0]['estado']=='en_curso'
