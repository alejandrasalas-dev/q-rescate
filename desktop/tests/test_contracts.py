import json
from dataclasses import replace
import pytest
from qrescate_desktop.models import *
from qrescate_desktop.backend import DisconnectedBackend

def scenario():
    return Scenario(base=Point('h','Base',-11.25,-74.63),destinations=[Point('a','A',-11.3,-74.6)])

def test_json_round_trip_preserves_full_scenario():
    s=scenario();s.zones=[Zone('z','Zona',-11.2,-74.7,3000,'exclusion')]
    assert Scenario.from_dict(json.loads(s.dumps()))==s
    c=s.clone();c.destinations[0].name='Otro';assert s.destinations[0].name=='A'

@pytest.mark.parametrize('patch',[{'schema_version':2},{'base':{'id':'h','name':'H','lat':float('nan'),'lng':0}},{'destinations':[{'id':'x','name':'A','lat':0,'lng':0}]*2},{'config':{'shots':0}},{'config':{'methods':['grover']}},{'config':{'seed':True}},{'zones':[{'id':'z','name':'Z','lat':0,'lng':0,'radius_m':-1,'kind':'operation'}]}])
def test_invalid_import_is_rejected(patch):
    raw=Scenario().to_dict();raw.update(patch)
    with pytest.raises((ValueError,TypeError)):Scenario.from_dict(raw)

def test_disconnected_backend_never_computes():
    b=DisconnectedBackend();assert not b.capabilities().connected
    assert 'Backend no conectado' in validate_for_run(scenario(),b.capabilities())
    with pytest.raises(ConnectionError):b.submit(scenario())

def test_limits_come_from_capabilities():
    s=scenario();caps=Capabilities(connected=True)
    assert not validate_for_run(s,caps)
    s.destinations += [Point(str(i),str(i),0,0) for i in range(3)]
    assert validate_for_run(s,caps)
    assert not validate_for_run(s,replace(caps,max_destinations=4,max_qaoa_destinations=4,max_qubits=16))
    s.config.shots=9000;assert validate_for_run(s,caps)

def test_geometry_is_geojson_and_finite():
    assert Geometry(coordinates=[[-74,-11],[-74.1,-11.2]]).type=='LineString'
    with pytest.raises(ValueError):Geometry(coordinates=[[-74,float('nan')],[-75,-11]])

def test_result_allows_missing_metrics_without_fabrication():
    r=MethodResult('qaoa');assert r.cost is None and r.geometry is None and r.valid is None
    with pytest.raises(ValueError):JobSnapshot('id','inventado')
