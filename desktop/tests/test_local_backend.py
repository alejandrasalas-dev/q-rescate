import copy
import time
from dataclasses import asdict
import pytest
from qrescate_desktop.local_backend import LocalBackend,to_request,to_snapshot,from_example,capabilities
from qrescate_desktop.models import Point,Zone,validate_for_run

def small():
    s=from_example();s.config.methods=['exact','greedy'];s.destinations=s.destinations[:2];return s

def test_request_fields_units_and_ids_are_explicit():
    s=small();s.scenario_unused='ignored by dataclass clone'
    s.base.name='Hospital';s.zones.append(Zone('x','Bloqueo',-11.25,-74.64,100,'exclusion'))
    d=to_request(s)
    assert d['base']=={'id':'H','nombre':'Hospital','lat':s.base.lat,'lon':s.base.lng}
    assert d['metodos']==['exacto','voraz'] and d['semilla']==42 and d['shots']==512
    assert d['zona_operacion']['radio_m']==1500 and d['exclusiones'][0]['radio_m']==100
    assert d['max_qubits']==9 and d['timeout_s']==300

@pytest.mark.parametrize('change',[lambda s:s.destinations.pop(),lambda s:setattr(s.config,'reps',2),lambda s:setattr(s.config,'maxiter',40),lambda s:s.zones.append(Zone('op','Otra',s.base.lat,s.base.lng,3000,'operation')),lambda s:setattr(s.destinations[0],'lat',0)])
def test_unsupported_settings_never_silently_ignored(change):
    s=small();change(s)
    with pytest.raises(ValueError):to_request(s)

def raw_result(state='ok'):
    return {'estado':state,'mensaje':'Mensaje motor','puntos':[{'id':'A','distancia_m':450,'lejos_de_calle':True,'lat_red':-11.24,'lon_red':-74.63}],
            'inaccesibles':['B'],'red':{'fuente':'osm'},'metodos':[
             {'metodo':'exacto','estado':'ok','costo_min':4.5,'gap_pct':0,'valida':True,'duracion_s':.12,'orden':['H','A','H'],'geometria':[[-11.2537,-74.6378],[-11.248,-74.634]],'detalle':'real'},
             {'metodo':'qaoa','estado':'omitido','detalle':'No hay suficientes destinos accesibles'}]}

def test_geometry_swaps_once_and_retains_partial_and_method_omissions():
    raw=raw_result();s=to_snapshot('job',raw,{'request':'kept'})
    assert s.job_id=='job' and s.state=='completed'
    assert s.results[0].geometry.coordinates[0]==[-74.6378,-11.2537]
    assert s.results[0].cost==4.5 and s.results[0].unit=='min' and s.results[0].visit_order==['H','A','H']
    assert s.results[1].status=='omitido' and s.results[1].cost is None
    assert not s.results[0].metadata['covers_all_destinations']
    assert s.metadata['unreachable_ids']==['B'] and s.metadata['snapped_points']==raw['puntos']
    assert '450' in ' '.join(s.messages)

@pytest.mark.parametrize('engine,ui,code',[('ok','completed',None),('error','error','ENGINE_ERROR'),('cancelado','cancelled',None),('tiempo_agotado','error','TIMEOUT'),('en_curso','running',None)])
def test_terminal_and_partial_states(engine,ui,code):
    s=to_snapshot('same',raw_result(engine));assert s.state==ui and s.job_id=='same' and s.progress_percent is None
    assert (s.error.code if s.error else None)==code

class FakeCalculation:
    def __init__(self,request,**options):self.request=request;self.options=options;self.parcial=raw_result('en_curso');self.etapa='Optimizando';self.final=None;self.closed=False
    def consultar(self):return self.final
    def cancelar(self):self.final=raw_result('cancelado')
    def cerrar(self):self.closed=True

def test_job_registry_retains_final_and_cancellation_is_idempotent():
    b=LocalBackend(calculation_factory=FakeCalculation);job=b.submit(small());calc=b.jobs[job].calculation
    assert b.status(job).state=='running'
    with pytest.raises(RuntimeError):b.submit(small())
    b.cancel(job);first=b.status(job);b.cancel(job)
    assert first.state=='cancelled' and b.status(job)==first and calc.closed
    with pytest.raises(KeyError):b.status('unknown')
    b.shutdown()

def test_shutdown_terminates_active_owned_jobs():
    b=LocalBackend(calculation_factory=FakeCalculation);job=b.submit(small());calc=b.jobs[job].calculation;b.shutdown()
    assert calc.closed and calc.final['estado']=='cancelado'
    with pytest.raises(RuntimeError):b.submit(small())

def test_actual_spawned_engine_and_cancel_without_internet():
    b=LocalBackend(source='sintetica');job=b.submit(small());end=time.monotonic()+60
    while time.monotonic()<end:
        s=b.status(job)
        if s.state!='running':break
        time.sleep(.05)
    assert s.state=='completed',asdict(s)
    assert s.metadata['engine_result']['red']['fuente']=='sintetica'
    assert [r.method for r in s.results]==['exact','greedy']
    assert all(r.visit_order[0]==r.visit_order[-1]=='H' for r in s.results)
    job=b.submit(small());b.cancel(job);assert b.status(job).state=='cancelled';b.shutdown()

def test_qaoa_four_destinations_is_rejected():
    s=from_example();s.destinations.append(Point('D','D',-11.253,-74.635))
    assert validate_for_run(s,capabilities())
