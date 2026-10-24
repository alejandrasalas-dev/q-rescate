"""Explicit UI/engine conversion; Qiskit only runs in Calculo's spawned child."""
from __future__ import annotations
from dataclasses import dataclass,field
import copy
import importlib.util
from threading import RLock
import uuid
from .models import Capabilities,Scenario,Config,Point,Zone,Geometry,MethodResult,JobSnapshot,BackendError,validate_for_run
from .geography import validate_coverage

TO_ENGINE={'exact':'exacto','greedy':'voraz','qaoa':'qaoa'}
FROM_ENGINE={v:k for k,v in TO_ENGINE.items()}

def capabilities():
    return Capabilities(connected=True,min_destinations=2,max_destinations=4,max_qaoa_destinations=3,
                        max_operation_zones=1,fixed_reps=1,fixed_maxiter=35,cancellation=True,experiments=False)

def to_request(scenario:Scenario):
    from engine.contrato import Solicitud
    error=validate_for_run(scenario,capabilities())
    if error:raise ValueError(error)
    validate_coverage(scenario)
    point=lambda p:{'id':p.id,'nombre':p.name,'lat':p.lat,'lon':p.lng}
    circle=lambda z:{'lat':z.lat,'lon':z.lng,'radio_m':z.radius_m}
    operations=[z for z in scenario.zones if z.kind=='operation']
    raw={'base':point(scenario.base),'destinos':[point(p) for p in scenario.destinations],
         'zona_operacion':circle(operations[0]) if operations else None,
         'exclusiones':[circle(z) for z in scenario.zones if z.kind=='exclusion'],
         'metodos':[TO_ENGINE[m] for m in scenario.config.methods],'semilla':scenario.config.seed,
         'shots':scenario.config.shots,'max_qubits':9,'timeout_s':scenario.config.timeout_seconds}
    Solicitud.desde_dict(raw).validar()
    from engine.cobertura import planificar
    planificar(Solicitud.desde_dict(raw))  # Reject invalid operation area before starting work.
    return raw

def from_example(name='satipo_3_destinos'):
    from engine.ejemplos import ejemplo
    raw=ejemplo(name)
    point=lambda p:Point(p['id'],p.get('nombre') or p['id'],p['lat'],p['lon'])
    zones=[]
    if raw.get('zona_operacion'):
        c=raw['zona_operacion'];zones.append(Zone('operation-example','Zona de operación',c['lat'],c['lon'],c['radio_m'],'operation'))
    for i,c in enumerate(raw.get('exclusiones',[])):
        zones.append(Zone(f'exclusion-{i}','Exclusión de ejemplo',c['lat'],c['lon'],c['radio_m'],'exclusion'))
    return Scenario(name='Ejemplo OSM · Satipo',base=point(raw['base']),destinations=[point(p) for p in raw['destinos']],
                    zones=zones,config=Config(methods=[FROM_ENGINE[m] for m in raw['metodos']],seed=raw['semilla'],shots=raw['shots']))

def to_snapshot(job_id,raw,request=None,stage=''):
    status=raw.get('estado','error')
    state={'ok':'completed','error':'error','cancelado':'cancelled','tiempo_agotado':'error','en_curso':'running'}.get(status,'error')
    messages=[raw['mensaje']] if raw.get('mensaje') else []
    if stage and state=='running':messages.append(stage)
    inaccessible=raw.get('inaccesibles',[])
    if inaccessible:messages.append('Atención parcial. Destinos inaccesibles/no atendidos: '+', '.join(inaccessible))
    if inaccessible and raw.get('red',{}).get('coverage'):
        messages.append('Inaccesibilidad referida a la red descargada. Amplía la zona de operación para buscar desvíos más largos si procede.')
    for p in raw.get('puntos',[]):
        if p.get('lejos_de_calle'):messages.append(f"{p['id']}: ajustado {p.get('distancia_m')} m hasta la vía.")
    results=[]
    for item in raw.get('metodos',[]):
        method=FROM_ENGINE.get(item['metodo'])
        if method is None:raise ValueError('Método desconocido en respuesta del motor')
        coords=item.get('geometria') or []
        geometry=Geometry(coordinates=[[p[1],p[0]] for p in coords]) if coords else None
        details=[item['detalle']] if item.get('detalle') else []
        method_state=item.get('estado','error')
        if method_state!='ok':details.insert(0,'Método '+method_state)
        if inaccessible:details.append('Recorrido parcial: no incluye todos los destinos solicitados.')
        results.append(MethodResult(method,cost=item.get('costo_min'),gap_percent=item.get('gap_pct'),
                       valid=item.get('valida'),duration_seconds=item.get('duracion_s'),visit_order=list(item.get('orden') or []),
                       geometry=geometry,messages=details,unit='min',status=method_state,
                       metadata={'covers_all_destinations':not inaccessible,'engine_method':copy.deepcopy(item)}))
    if state=='completed' and not any(r.status=='ok' for r in results):
        state='error';messages.append('Ningún método completó un resultado correcto.')
    error=None
    if state=='error':
        code='TIMEOUT' if status=='tiempo_agotado' else 'ENGINE_ERROR'
        error=BackendError(code,raw.get('mensaje') or 'Error del motor',details={'engine_state':status})
    return JobSnapshot(job_id,state,results=results,messages=messages,error=error,
                       metadata={'engine_result':copy.deepcopy(raw),'engine_request':copy.deepcopy(request),
                                 'unreachable_ids':list(inaccessible),'snapped_points':copy.deepcopy(raw.get('puntos',[]))})

@dataclass
class _Job:
    calculation: object
    request: dict
    lock: object=field(default_factory=RLock)
    final: JobSnapshot|None=None

class LocalBackend:
    def __init__(self,source='osm',calculation_factory=None):
        if source not in ('osm','sintetica'):raise ValueError('Fuente desconocida')
        self.source=source;self.factory=calculation_factory;self.jobs={};self.lock=RLock();self.closed=False

    def capabilities(self):
        return capabilities()

    def submit(self,scenario):
        request=to_request(scenario)
        from engine.ejecutor import Calculo
        with self.lock:
            if self.closed:raise RuntimeError('El backend ya está cerrado')
            # One simulator process per desktop instance. Terminal jobs stay queryable.
            if any(j.final is None for j in self.jobs.values()):raise RuntimeError('Ya hay un cálculo activo')
            calculation=(self.factory or Calculo)(request,fuente=self.source,timeout_s=request['timeout_s'])
            job_id=uuid.uuid4().hex;self.jobs[job_id]=_Job(calculation,request)
            return job_id

    def _job(self,job_id):
        with self.lock:
            if job_id not in self.jobs:raise KeyError('Trabajo desconocido: '+job_id)
            return self.jobs[job_id]

    def _poll(self,job_id,job):
        if job.final:return copy.deepcopy(job.final)
        raw=job.calculation.consultar()
        if raw is None:
            partial=job.calculation.parcial or {'estado':'en_curso','metodos':[]}
            return to_snapshot(job_id,partial,job.request,job.calculation.etapa)
        try:job.final=to_snapshot(job_id,raw,job.request)
        except Exception as exc:job.final=JobSnapshot(job_id,'error',error=BackendError('PROTOCOL',str(exc)),metadata={'engine_result':copy.deepcopy(raw)})
        finally:job.calculation.cerrar()
        return copy.deepcopy(job.final)

    def status(self,job_id):
        job=self._job(job_id)
        with job.lock:return self._poll(job_id,job)

    def cancel(self,job_id):
        job=self._job(job_id)
        with job.lock:
            if job.final:return
            job.calculation.cancelar();self._poll(job_id,job)

    def submit_experiments(self,scenario,seeds):
        raise NotImplementedError('Experimentos no disponibles: ejecuta cálculos individuales con plazo y cancelación.')

    def shutdown(self):
        with self.lock:
            self.closed=True;jobs=list(self.jobs.values())
        for job in jobs:
            with job.lock:
                if job.final is None:job.calculation.cancelar()
                job.calculation.cerrar()
