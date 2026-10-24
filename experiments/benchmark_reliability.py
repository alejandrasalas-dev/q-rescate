"""Experimentos reproducibles, secuenciales y acotados para routing.py.

python experiments/benchmark_reliability.py --output experiments/results/reliability.json
No cambia el QUBO ni ejecuta hardware cuántico. Cada QAOA corre en un
subproceso cancelable; el límite de nueve qubits no se puede elevar aquí.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import numpy as np
from routing import STOPS, SCENARIOS, road_network, travel_matrix, exact_tour, greedy_tour, qaoa_tour, tour_cost

CASES = [('normal', 2), ('normal', 3), ('bridge_closed', 3), ('flood_risk', 3), ('normal', 4)]


def matrix_hash(matrix):
    return hashlib.sha256(json.dumps(np.asarray(matrix).tolist(), separators=(',', ':')).encode()).hexdigest()


def gap_percent(cost, optimum):
    """Gap de minimización. Con referencia cero y costo no cero es indefinido."""
    if cost is None or not math.isfinite(cost) or not math.isfinite(optimum):
        return None
    if optimum == 0:
        return 0.0 if cost == 0 else None
    return 100.0 * (cost - optimum) / abs(optimum)


def audit_result(result, matrix, optimum):
    """Recalcula validez y costo; nunca confía solamente en feasible del solver."""
    result = dict(result)
    result['matrix_sha256'] = matrix_hash(matrix)
    result['validated_feasible'] = False
    result['gap_percent'] = None
    result['optimal'] = False
    if result.get('status', 'completed') != 'completed':
        return result
    try:
        actual = tour_cost(matrix, result['tour'])
        if not math.isfinite(actual) or not math.isclose(actual, float(result['cost']), abs_tol=1e-8):
            raise ValueError('El costo reportado no coincide con el recorrido')
        if actual < optimum - 1e-8:
            raise ValueError('Costo inferior a la referencia exacta: revisar datos/modelo')
        if result.get('feasible') is False:
            raise ValueError('El solver declara el resultado inviable')
    except (TypeError, ValueError, KeyError, IndexError) as error:
        result['status'] = 'invalid_result'
        result['validation_error'] = str(error)
        return result
    result.update(validated_feasible=True, recomputed_cost=actual,
                  gap_percent=gap_percent(actual, optimum),
                  optimal=bool(math.isclose(actual, optimum, abs_tol=1e-8)))
    return result


def bounded_qaoa(matrix, params, timeout_seconds):
    qubits = (len(matrix) - 1) ** 2
    if qubits > params['max_qubits'] or qubits > 9:
        return dict(status='skipped', reason='Límite de qubits', qubits=qubits, **params)
    payload = {'matrix': np.asarray(matrix).tolist(), 'params': params}
    start = time.perf_counter()
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    try:
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'],
                           input=json.dumps(payload), text=True, capture_output=True,
                           timeout=timeout_seconds, env=env, cwd=ROOT)
    except subprocess.TimeoutExpired:
        return dict(status='timeout', qubits=qubits, timeout_seconds=timeout_seconds,
                    wall_seconds=time.perf_counter()-start, **params)
    wall = time.perf_counter()-start
    if p.returncode:
        return dict(status='error', reason=p.stderr[-6000:], returncode=p.returncode,
                    qubits=qubits, wall_seconds=wall, **params)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError:
        return dict(status='error', reason='Salida no JSON del trabajador',
                    stdout=p.stdout[-2000:], stderr=p.stderr[-2000:],
                    qubits=qubits, wall_seconds=wall, **params)
    if result.get('matrix_sha256') != matrix_hash(matrix):
        return dict(status='error', reason='Matriz distinta en trabajador', qubits=qubits, **params)
    result = dict(params, **result)
    result['wall_seconds'] = wall
    result['timeout_seconds'] = timeout_seconds
    result['worker_stderr'] = p.stderr[-6000:]
    return result


def environment():
    versions = {}
    for name in ('qiskit', 'qiskit-algorithms', 'qiskit-optimization', 'numpy', 'scipy', 'networkx', 'pytest'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, text=True, capture_output=True).stdout
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                machine=platform.machine(), logical_cpus=os.cpu_count(), dependencies=versions,
                base_commit=commit, working_tree_dirty=bool(dirty),
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                routing_sha256=hashlib.sha256((ROOT/'routing.py').read_bytes()).hexdigest(),
                worker_thread_limits={k: '1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})


def write_results(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)
    columns = ['scenario', 'size', 'method', 'seed', 'status', 'validated_feasible',
               'cost', 'gap_percent', 'optimal', 'runtime_seconds', 'wall_seconds',
               'qubits', 'reps', 'maxiter', 'shots', 'matrix_sha256']
    with path.with_suffix('.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for case in report['cases']:
            for result in case['results']:
                writer.writerow(dict(result, scenario=case['scenario'], size=case['size']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--seeds', nargs='+', type=int, default=[3, 7, 42])
    parser.add_argument('--max-qubits', type=int, default=9, choices=range(1, 10))
    parser.add_argument('--timeout-seconds', type=float, default=120)
    parser.add_argument('--total-seconds', type=float, default=900)
    parser.add_argument('--resume-from', type=Path, help='Reutiliza sólo ejecuciones completas con igual modelo y parámetros')
    parser.add_argument('--reps', type=int, default=1)
    parser.add_argument('--maxiter', type=int, default=35)
    parser.add_argument('--shots', type=int, default=512)
    parser.add_argument('--output', type=Path, default=ROOT/'experiments/results/reliability.json')
    args = parser.parse_args()
    if args.worker:
        data = json.load(sys.stdin)
        matrix = np.array(data['matrix'], dtype=float)
        if (len(matrix)-1)**2 > 9 or data['params']['max_qubits'] > 9:
            raise ValueError('Trabajador: más de nueve qubits prohibido')
        r = qaoa_tour(matrix, **data['params'])
        r['matrix_sha256'] = matrix_hash(matrix)
        print(json.dumps(r, allow_nan=False))
        return
    if (any(s < 0 for s in args.seeds) or
        any(x <= 0 or not math.isfinite(x) for x in [args.timeout_seconds, args.total_seconds, args.reps, args.maxiter, args.shots])):
        parser.error('Semillas no negativas y recursos positivos y finitos')
    previous = json.loads(args.resume_from.read_text()) if args.resume_from else None
    current_environment = environment()
    if previous and previous['environment']['routing_sha256'] != current_environment['routing_sha256']:
        parser.error('El código routing.py cambió; no se pueden reutilizar ejecuciones')
    report = dict(experiment='reliability_directed_TSP', created_utc=datetime.now(timezone.utc).isoformat(),
                  synthetic=True, quantum_hardware_used=False, environment=current_environment,
                  configuration=dict(seeds=args.seeds, max_qubits=args.max_qubits,
                    per_run_timeout_seconds=args.timeout_seconds, total_quantum_budget_seconds=args.total_seconds,
                    reps=args.reps, maxiter=args.maxiter, shots=args.shots, optimizer='COBYLA'),
                  observations=['Tiempo wall incluye inicio/importaciones del subproceso; runtime del solver no.',
                    'Sin corrección de muestras ni sustitución por respuesta clásica.',
                    'Las semillas cambian aleatoriedad del solver, no generan nuevos escenarios.',
                    'Riesgo es una penalización determinista de viaje; no se usa Monte Carlo.',
                    'No se afirma ventaja cuántica.'], cases=[])
    if previous:
        report['previous_run'] = previous
    deadline = time.perf_counter() + args.total_seconds
    for scenario, n in CASES:
        matrix = travel_matrix(road_network(scenario), STOPS[:n])
        exact = exact_tour(matrix)
        greedy = greedy_tour(matrix)
        case = dict(scenario=scenario, size=n, stops=list(STOPS[:n]),
                    distance_matrix=matrix.tolist(), matrix_sha256=matrix_hash(matrix), results=[])
        report['cases'].append(case)
        for r in (exact, greedy):
            case['results'].append(audit_result(dict(r, status='completed', qubits=0), matrix, exact['cost']))
        for seed in dict.fromkeys(args.seeds):
            params = dict(seed=seed, maxiter=args.maxiter, reps=args.reps, shots=args.shots, max_qubits=args.max_qubits)
            left = deadline - time.perf_counter()
            reusable = []
            if previous:
                for old_case in previous['cases']:
                    if old_case['scenario'] == scenario and old_case['size'] == n and old_case['matrix_sha256'] == case['matrix_sha256']:
                        reusable.extend(r for r in old_case['results'] if r.get('method') == 'QAOA' and r.get('status') == 'completed' and all(r.get(k) == v for k,v in params.items()))
            if reusable:
                result = dict(reusable[-1], reused_from_previous_run=True)
            elif n*n > args.max_qubits:
                result = dict(status='skipped', reason='Límite de qubits', qubits=n*n, **params)
            elif left <= 0:
                result = dict(status='skipped', reason='Presupuesto global agotado', qubits=n*n, **params)
            else:
                result = bounded_qaoa(matrix, params, min(args.timeout_seconds, left))
            case['results'].append(audit_result(dict(result, method='QAOA'), matrix, exact['cost']))
            write_results(report, args.output)  # Checkpoint aun con timeouts/fallos.
            last = case['results'][-1]
            print(f"{scenario} n={n} seed={seed}: {last['status']}, cost={last.get('cost')}, gap={last['gap_percent']}", flush=True)
    write_results(report, args.output)
    print(f'Resultados: {args.output}')
    if any(r['status'] in ('error', 'timeout', 'invalid_result') for c in report['cases'] for r in c['results']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
