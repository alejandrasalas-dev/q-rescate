"""Regresiones de evaluación: sin simulaciones grandes ni resultados inventados."""
import itertools
import subprocess

import numpy as np
import pytest
import routing
from experiments import benchmark_reliability as b


@pytest.mark.parametrize('cost,optimum,expected', [(115,100,15),(100,100,0),(0,0,0),(1,0,None),(None,10,None),(float('nan'),10,None)])
def test_gap(cost, optimum, expected):
    assert b.gap_percent(cost, optimum) == expected


@pytest.mark.parametrize('scenario', routing.SCENARIOS)
@pytest.mark.parametrize('n', [2,3])
def test_qubo_cost_and_penalties_for_all_bitstrings(scenario,n):
    matrix = routing.travel_matrix(routing.road_network(scenario), routing.STOPS[:n])
    model = routing.quadratic_program(matrix)
    optimum = routing.exact_tour(matrix)['cost']
    for mask in range(1 << (n*n)):
        bits = [(mask>>i)&1 for i in range(n*n)]
        route = routing.decode_tour(bits,n)
        energy = model.objective.evaluate(bits)
        if route is None:
            assert energy > optimum
        else:
            assert energy == pytest.approx(routing.tour_cost(matrix,route))


@pytest.mark.parametrize('bits', [[-1,2,2,-1], [.5,.5,.5,.5], [1,0], [float('nan')]*4, [float('inf')]*4, ['bad']*4])
def test_decoder_rejects_nonbinary_or_malformed_samples(bits):
    assert routing.decode_tour(bits,2) is None


def test_valid_quantum_route_is_audited_and_bad_cost_rejected():
    matrix = routing.travel_matrix(routing.road_network(), routing.STOPS[:3])
    exact = routing.exact_tour(matrix)
    r = dict(exact, status='completed', feasible=True)
    assert b.audit_result(r,matrix,exact['cost'])['optimal']
    bad = b.audit_result(dict(r,cost=exact['cost']+1),matrix,exact['cost'])
    assert bad['status']=='invalid_result'
    assert bad['gap_percent'] is None
    bad = b.audit_result(dict(r,tour=[0,0,1]),matrix,exact['cost'])
    assert not bad['validated_feasible']


def test_directed_cost_is_not_silently_symmetrized():
    matrix = np.array([[0,2,9],[8,0,3],[4,7,0]],dtype=float)
    assert routing.tour_cost(matrix,[0,1]) == 9
    assert routing.tour_cost(matrix,[1,0]) == 24
    for solver in [routing.exact_tour,routing.greedy_tour]:
        result=solver(matrix)
        assert b.audit_result(result,matrix,9)['validated_feasible']


def test_matrix_identity_and_no_mutation_between_methods(monkeypatch):
    matrix = routing.travel_matrix(routing.road_network('bridge_closed'),routing.STOPS[:3])
    original = matrix.copy()
    seen = []
    def fake_worker(command, **kwargs):
        import json
        data=json.loads(kwargs['input'])
        worker_matrix=np.array(data['matrix'])
        seen.append(worker_matrix)
        result=dict(routing.exact_tour(worker_matrix),status='completed',feasible=True,
                    matrix_sha256=b.matrix_hash(worker_matrix))
        return subprocess.CompletedProcess(command,0,json.dumps(result),'')
    monkeypatch.setattr(b.subprocess,'run',fake_worker)
    params=dict(seed=3,maxiter=35,reps=1,shots=512,max_qubits=9)
    q=b.bounded_qaoa(matrix,params,1)
    results=[routing.exact_tour(matrix),routing.greedy_tour(matrix),q]
    audited=[b.audit_result(r,matrix,results[0]['cost']) for r in results]
    assert len({r['matrix_sha256'] for r in audited})==1
    assert np.array_equal(matrix,original)
    assert np.array_equal(seen[0],original)


def test_qubit_guard_prevents_launch(monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail('No debe iniciar un proceso de 16 qubits')
    monkeypatch.setattr(b.subprocess,'run',forbidden)
    matrix=routing.travel_matrix(routing.road_network(),routing.STOPS)
    r=b.bounded_qaoa(matrix,dict(seed=42,maxiter=35,reps=1,shots=512,max_qubits=9),1)
    assert r['status']=='skipped' and r['qubits']==16
    assert routing.qaoa_tour(matrix,max_qubits=9)['status']=='skipped'


def test_timeout_is_reported(monkeypatch):
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired(args[0],kwargs['timeout'])
    monkeypatch.setattr(b.subprocess,'run',timeout)
    matrix=routing.travel_matrix(routing.road_network(),routing.STOPS[:2])
    r=b.bounded_qaoa(matrix,dict(seed=7,maxiter=35,reps=1,shots=512,max_qubits=9),0.01)
    assert r['status']=='timeout'
    assert r['timeout_seconds']==0.01


def test_different_matrix_from_worker_is_rejected(monkeypatch):
    monkeypatch.setattr(b.subprocess,'run',lambda *a,**k: subprocess.CompletedProcess(a[0],0,'{"matrix_sha256":"wrong"}',''))
    matrix=routing.travel_matrix(routing.road_network(),routing.STOPS[:2])
    r=b.bounded_qaoa(matrix,dict(seed=3,maxiter=35,reps=1,shots=512,max_qubits=9),1)
    assert r['status']=='error'


def test_resume_keeps_completed_results_but_retries_timeouts(tmp_path,monkeypatch):
    import json
    import sys
    matrix=routing.travel_matrix(routing.road_network(),routing.STOPS[:2])
    params=dict(maxiter=35,reps=1,shots=512,max_qubits=9)
    completed=dict(routing.exact_tour(matrix),method='QAOA',status='completed',feasible=True,seed=3,**params)
    previous=dict(environment={'routing_sha256':'same'},cases=[dict(scenario='normal',size=2,
        matrix_sha256=b.matrix_hash(matrix),results=[completed,dict(method='QAOA',status='timeout',seed=7,**params)])])
    old=tmp_path/'previous.json';old.write_text(json.dumps(previous))
    output=tmp_path/'new.json'
    calls=[]
    def worker(m,p,timeout):
        calls.append((len(m)-1,p['seed']))
        return dict(routing.exact_tour(m),status='completed',feasible=True,**p)
    monkeypatch.setattr(b,'bounded_qaoa',worker)
    monkeypatch.setattr(b,'environment',lambda: {'routing_sha256':'same'})
    monkeypatch.setattr(sys,'argv',['benchmark','--seeds','3','7','--resume-from',str(old),'--output',str(output)])
    b.main()
    report=json.loads(output.read_text())
    assert (2,3) not in calls and (2,7) in calls
    assert report['cases'][0]['results'][2]['reused_from_previous_run']
    assert report['previous_run']==previous
    assert output.with_suffix('.csv').exists()
