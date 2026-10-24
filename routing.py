"""Q-Rescate routing study: *actual multi-stop tours*, not one-to-one assignment.

Synthetic directed road network. All service stops are visited exactly once, starting
and ending at the hospital. Road closures are handled by shortest-path preprocessing.
Quantum optimization addresses visit *order*, not road-edge selection.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from typing import Sequence

import networkx as nx
import numpy as np

DEPOT = "H"
STOPS = ("A", "B", "C", "D")
# (start, end, forward_minutes, backward_minutes): fictitious data; no real locations.
ROADS = (
    ("H", "N", 2, 3), ("N", "A", 2, 3), ("N", "B", 6, 5),
    ("N", "X", 3, 4), ("A", "X", 3, 2), ("X", "B", 2, 3),
    ("X", "C", 4, 5), ("B", "S", 2, 2), ("S", "C", 2, 3),
    ("S", "H", 7, 6), ("H", "X", 8, 7), ("A", "S", 8, 7),
    ("C", "D", 2, 3), ("D", "S", 3, 2), ("D", "X", 5, 4),
)
SCENARIOS = ("normal", "bridge_closed", "flood_risk")


def road_network(scenario: str = "normal") -> nx.DiGraph:
    """Build a directed network: asymmetric travel times, real edge closures."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    graph = nx.DiGraph()
    for a, b, forward, backward in ROADS:
        graph.add_edge(a, b, weight=float(forward))
        graph.add_edge(b, a, weight=float(backward))
    if scenario == "bridge_closed":
        graph.remove_edge("X", "B")
        graph.remove_edge("B", "X")
    elif scenario == "flood_risk":
        # Conservative travel-time penalties (not actual closure probabilities).
        for a, b in (("N", "A"), ("A", "N"), ("B", "S"), ("S", "B")):
            graph[a][b]["weight"] += 8.0
    return graph


def travel_matrix(graph: nx.DiGraph, stops: Sequence[str]) -> np.ndarray:
    """Shortest legal road distances between hospital and every service stop."""
    nodes = (DEPOT, *stops)
    matrix = np.zeros((len(nodes), len(nodes)))
    for i, start in enumerate(nodes):
        distances = nx.single_source_dijkstra_path_length(graph, start, weight="weight")
        for j, dest in enumerate(nodes):
            if dest not in distances:
                raise ValueError(f"Destination {dest} unreachable from {start}")
            matrix[i, j] = distances[dest]
    return matrix


def tour_cost(matrix: np.ndarray, tour: Sequence[int]) -> float:
    """Tour is a permutation of service stop indices 0..n-1."""
    n = len(matrix) - 1
    if len(tour) != n or sorted(tour) != list(range(n)):
        raise ValueError("Invalid tour: every service stop must be visited exactly once")
    path = [0] + [i + 1 for i in tour] + [0]
    return float(sum(matrix[path[k], path[k + 1]] for k in range(len(path) - 1)))


def exact_tour(matrix: np.ndarray) -> dict:
    n = len(matrix) - 1
    begin = time.perf_counter()
    cost, tour = min((tour_cost(matrix, perm), perm)
                     for perm in itertools.permutations(range(n)))
    return {"tour": list(tour), "cost": cost,
            "runtime_seconds": time.perf_counter() - begin, "method": "exact_enumeration"}


def greedy_tour(matrix: np.ndarray) -> dict:
    n = len(matrix) - 1
    begin = time.perf_counter()
    remaining = set(range(n))
    prev = 0
    tour = []
    while remaining:
        nxt = min(remaining, key=lambda idx: (matrix[prev, idx + 1], idx))
        tour.append(nxt)
        remaining.remove(nxt)
        prev = nxt + 1
    return {"tour": tour, "cost": tour_cost(matrix, tour),
            "runtime_seconds": time.perf_counter() - begin, "method": "nearest_neighbor"}


def quadratic_program(matrix: np.ndarray, penalty: float = 1000):
    """QUBO of a depot-fixed, position-encoded Traveling Salesperson Problem.

    x[p,i] == 1 means service stop i is visited at position p (0..n-1).
    Exactly one stop per position and one position per stop. Position variables
    create a single ordered tour, thus no disconnected subtours are possible.
    """
    from qiskit_optimization import QuadraticProgram
    from qiskit_optimization.converters import QuadraticProgramToQubo
    n = len(matrix) - 1
    if n < 2 or n > 4:
        raise ValueError("Research model supports 2-4 stops")
    qp = QuadraticProgram("multi_stop_routing")
    for p in range(n):
        for i in range(n):
            qp.binary_var(name=f"x_{p}_{i}")
    linear = {}
    quadratic = {}
    for i in range(n):
        linear[f"x_0_{i}"] = float(matrix[0, i + 1])
        last = f"x_{n-1}_{i}"
        linear[last] = linear.get(last, 0.0) + float(matrix[i + 1, 0])
    for p in range(n - 1):
        for i in range(n):
            for j in range(n):
                quadratic[(f"x_{p}_{i}", f"x_{p+1}_{j}")] = float(matrix[i + 1, j + 1])
    qp.minimize(linear=linear, quadratic=quadratic)
    for p in range(n):
        qp.linear_constraint(
            {f"x_{p}_{i}": 1 for i in range(n)}, "==", 1, name=f"position_{p}")
    for i in range(n):
        qp.linear_constraint(
            {f"x_{p}_{i}": 1 for p in range(n)}, "==", 1, name=f"stop_{i}")
    return QuadraticProgramToQubo(penalty=penalty).convert(qp)


def decode_tour(bits: Sequence[float], n: int) -> list[int] | None:
    try:
        arr = np.asarray(bits, dtype=float).reshape(n, n)
    except (TypeError, ValueError):
        return None
    # Integer row/column sums alone also admit e.g. [[-1, 2], [2, -1]].
    if not np.all(np.isfinite(arr)) or not np.all((arr == 0) | (arr == 1)):
        return None
    if not np.all(arr.sum(axis=0) == 1) or not np.all(arr.sum(axis=1) == 1):
        return None
    return [int(np.argmax(row)) for row in arr]


def qaoa_tour(matrix: np.ndarray, seed: int = 42,
              maxiter: int = 35, reps: int = 1, shots: int = 512,
              max_qubits: int = 9) -> dict:
    """Bounded local-simulator QAOA. Invalid samples are reported, not hidden."""
    n = len(matrix) - 1
    qubits = n * n
    if qubits > max_qubits:
        return {"status": "skipped", "reason": f"{qubits} qubits > guard {max_qubits}",
                "qubits": qubits}
    from qiskit.primitives import StatevectorSampler
    from qiskit_algorithms import QAOA
    from qiskit_algorithms.optimizers import COBYLA
    from qiskit_algorithms.utils import algorithm_globals
    from qiskit_optimization.algorithms import MinimumEigenOptimizer

    algorithm_globals.random_seed = seed
    begin = time.perf_counter()
    solver = MinimumEigenOptimizer(QAOA(
        sampler=StatevectorSampler(seed=seed, default_shots=shots),
        optimizer=COBYLA(maxiter=maxiter), reps=reps))
    result = solver.solve(quadratic_program(matrix))
    elapsed = time.perf_counter() - begin
    route = decode_tour(result.x, n)
    return {"status": "completed", "feasible": route is not None,
            "tour": route, "cost": tour_cost(matrix, route) if route is not None else None,
            "runtime_seconds": elapsed, "seed": seed, "reps": reps,
            "optimizer": "COBYLA", "maxiter": maxiter, "shots": shots,
            "qubits": qubits, "backend": "Qiskit StatevectorSampler (classical simulation)"}


def benchmark(quantum: bool = True, max_qubits: int = 9) -> dict:
    entries = []
    for scenario, count in (("normal", 2), ("normal", 3),
                            ("bridge_closed", 3), ("flood_risk", 3),
                            ("normal", 4)):
        stops = STOPS[:count]
        graph = road_network(scenario)
        matrix = travel_matrix(graph, stops)
        exact = exact_tour(matrix)
        greedy = greedy_tour(matrix)
        item = {"scenario": scenario, "stops": list(stops), "size": count,
                "synthetic": True, "distance_matrix": matrix.tolist(),
                "classical_exact": exact, "classical_greedy": greedy}
        if quantum:
            q = qaoa_tour(matrix, max_qubits=max_qubits)
            q["gap_percent"] = (
                100 * (q["cost"] - exact["cost"]) / exact["cost"]
                if q.get("feasible") and exact["cost"] else None)
            item["qaoa"] = q
        entries.append(item)
    return {"experiment": "depot_fixed_multi_stop_route", "data_type": "synthetic",
            "quantum_hardware_used": False, "entries": entries}


def main():
    parser = argparse.ArgumentParser(description="Benchmark genuine multi-stop routing")
    parser.add_argument("--classical-only", action="store_true")
    parser.add_argument("--max-qubits", type=int, default=9)
    args = parser.parse_args()
    print(json.dumps(benchmark(quantum=not args.classical_only,
                               max_qubits=args.max_qubits), indent=2))


if __name__ == "__main__":
    main()
