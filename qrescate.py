"""Small, explicitly synthetic emergency assignment optimization benchmark."""
import itertools
import json
import time
import numpy as np

BASE = np.array([[4, 7, 9], [6, 3, 8], [8, 6, 2]], dtype=float)
SCENARIOS = {
    "normal": BASE,
    "blocked_road": np.array([[4, 7, 9], [6, 3, 8], [8, 6, 35]], dtype=float),
    "increased_risk": np.array([[14, 7, 9], [6, 13, 8], [8, 6, 12]], dtype=float),
}
# The 35 cost is a surrogate penalty for a closed road, not a physically allowed route.
BLOCKED = {"normal": set(), "blocked_road": {(2, 2)}, "increased_risk": set()}

def assignments():
    return itertools.permutations(range(3))

def evaluate(cost, assignment, blocked=()):
    if sorted(assignment) != [0, 1, 2]:
        raise ValueError("Expected a permutation of three communities")
    if any((i, j) in blocked for i, j in enumerate(assignment)):
        return float("inf")
    return float(sum(cost[i, j] for i, j in enumerate(assignment)))

def exact(cost, blocked=()):
    return min(((evaluate(cost, a, blocked), a) for a in assignments()), key=lambda x: x[0])

def quadratic_program(cost, penalty=100.0):
    """One-hot assignment constraints converted to QUBO with a dominant penalty."""
    from qiskit_optimization import QuadraticProgram
    from qiskit_optimization.converters import QuadraticProgramToQubo
    qp = QuadraticProgram("brigade_assignment")
    for i in range(3):
        for j in range(3):
            qp.binary_var(name=f"x_{i}_{j}")
    qp.minimize(linear={f"x_{i}_{j}": float(cost[i, j]) for i in range(3) for j in range(3)})
    for i in range(3):
        qp.linear_constraint({f"x_{i}_{j}": 1 for j in range(3)}, "==", 1, name=f"brigade_{i}")
    for j in range(3):
        qp.linear_constraint({f"x_{i}_{j}": 1 for i in range(3)}, "==", 1, name=f"community_{j}")
    return QuadraticProgramToQubo(penalty=penalty).convert(qp)

def decode(bits):
    selected = np.asarray(bits).reshape(3, 3)
    if not np.all(selected.sum(axis=0) == 1) or not np.all(selected.sum(axis=1) == 1):
        return None
    return tuple(int(np.argmax(row)) for row in selected)

def quantum(cost, blocked=(), seed=42, reps=1, maxiter=80):
    """Run genuine Qiskit QAOA on a local statevector-based simulator."""
    from qiskit.primitives import StatevectorSampler
    from qiskit_algorithms import QAOA
    from qiskit_algorithms.optimizers import COBYLA
    from qiskit_algorithms.utils import algorithm_globals
    from qiskit_optimization.algorithms import MinimumEigenOptimizer
    algorithm_globals.random_seed = seed
    qp = quadratic_program(cost)
    solver = MinimumEigenOptimizer(
        QAOA(sampler=StatevectorSampler(seed=seed, default_shots=2048),
             optimizer=COBYLA(maxiter=maxiter), reps=reps)
    )
    start = time.perf_counter()
    result = solver.solve(qp)
    elapsed = time.perf_counter() - start
    a = decode(result.x)
    value = evaluate(cost, a, blocked) if a is not None else float("inf")
    return {"assignment": a, "feasible": bool(np.isfinite(value)), "cost": value,
            "runtime_seconds": elapsed, "seed": seed, "reps": reps, "maxiter": maxiter,
            "shots": 2048, "solver": "QAOA/StatevectorSampler"}

def benchmark(with_quantum=True):
    output = {}
    for scenario, cost in SCENARIOS.items():
        blocked = BLOCKED[scenario]
        optimum, assign = exact(cost, blocked)
        item = {"exact_cost": optimum, "exact_assignment": assign, "synthetic": True}
        if with_quantum:
            q = quantum(cost, blocked)
            q["optimality_gap"] = q["cost"] - optimum if q["feasible"] else None
            item["qaoa"] = q
        output[scenario] = item
    return output

if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2, allow_nan=False))
