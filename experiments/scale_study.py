"""Q-Route: two independent scaling axes, classical road nodes and TSP service stops.

All road networks and costs are synthetic. Qiskit, if enabled, is only applied
to a three-stop TSP, not to the full road graph. No practical speedup claimed.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from typing import Sequence

import networkx as nx
import numpy as np

SCENARIOS = ("normal", "closure", "risk")
SIZES = (5, 10, 20)  # 25, 100, 400 graph nodes
STOPS = (3, 6, 10)


def road_grid(side: int, scenario: str = "normal", seed: int = 2026):
    """Directed, asymmetric-cost grid with a bidirectional spanning tree."""
    if side < 3 or scenario not in SCENARIOS:
        raise ValueError("Invalid grid size or scenario")
    rng = random.Random(seed + 1009 * side)
    graph = nx.DiGraph()
    graph.add_nodes_from(range(side * side))
    closed = risky = 0
    for row in range(side):
        for col in range(side):
            u = row * side + col
            neighbors = []
            if col < side - 1:
                neighbors.append((u + 1, "horizontal"))
            if row < side - 1:
                neighbors.append((u + side, "vertical"))
            for v, axis in neighbors:
                # Draw weights before removing edges to ensure matching common
                # roads have the exact same costs in every scenario.
                forward = float(rng.randint(2, 10))
                backward = float(rng.randint(2, 10))
                # Horizontal roads and first-column vertical roads form a
                # spanning tree, so closing other roads preserves connectivity.
                if (scenario == "closure" and axis == "vertical" and col > 0
                        and random.Random(seed + u*13007 + v*3259).random() < 0.25):
                    closed += 1
                    continue
                if scenario == "risk" and (u*7 + v*11 + seed) % 5 == 0:
                    forward += 12.0
                    backward += 12.0
                    risky += 1
                graph.add_edge(u, v, weight=forward)
                graph.add_edge(v, u, weight=backward)
    assert nx.is_strongly_connected(graph)
    return graph, {"removed_undirected_roads": closed,
                   "risk_penalized_undirected_roads": risky,
                   "road_nodes": graph.number_of_nodes(),
                   "directed_roads": graph.number_of_edges()}


def select_stops(side: int, n: int, seed: int = 2026) -> list[int]:
    if n < 2 or n >= side*side:
        raise ValueError("Invalid service stop count")
    rng = random.Random(seed + 2027*side)
    # Prefixes are nested for cases with 3, 6 and 10 destinations.
    return rng.sample(range(1, side*side), n)


def distance_matrix(graph: nx.DiGraph, stops: Sequence[int]) -> np.ndarray:
    nodes = [0, *stops]
    matrix = np.zeros((len(nodes), len(nodes)))
    for i, node in enumerate(nodes):
        lengths = nx.single_source_dijkstra_path_length(graph, node, weight="weight")
        for j, destination in enumerate(nodes):
            if destination not in lengths:
                raise ValueError("Unreachable node")
            matrix[i, j] = lengths[destination]
    return matrix


def tour_cost(matrix: np.ndarray, tour: Sequence[int]) -> float:
    n = len(matrix) - 1
    if len(tour) != n or sorted(tour) != list(range(n)):
        raise ValueError("Tour must visit each service node once")
    path = [0] + [int(i)+1 for i in tour] + [0]
    return float(sum(matrix[path[i], path[i+1]] for i in range(len(path)-1)))


def held_karp_exact(matrix: np.ndarray) -> dict:
    """Exact directed depot-fixed TSP, O(n² 2^n); guard 13 stops."""
    start = time.perf_counter()
    n = len(matrix)-1
    if n > 13:
        raise ValueError("Exact DP is limited to 13 stops")
    state = {(1 << i, i): (float(matrix[0, i+1]), (i,)) for i in range(n)}
    for mask in range(1, 1 << n):
        for last in range(n):
            entry = state.get((mask, last))
            if entry is None:
                continue
            subtotal, order = entry
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                key = (mask | (1 << nxt), nxt)
                candidate = (subtotal + matrix[last+1, nxt+1], order + (nxt,))
                prior = state.get(key)
                if prior is None or candidate < prior:
                    state[key] = candidate
    full = (1 << n)-1
    best_cost, best_order = min(
        (entry[0] + matrix[last+1, 0], entry[1])
        for last in range(n)
        if (entry := state.get((full, last))) is not None
    )
    return {"method": "exact_Held_Karp", "cost": float(best_cost),
            "tour": list(best_order), "seconds": time.perf_counter()-start}


def nearest_neighbor(matrix: np.ndarray) -> dict:
    start = time.perf_counter()
    remaining = set(range(len(matrix)-1))
    current, tour = 0, []
    while remaining:
        nxt = min(remaining, key=lambda j: (matrix[current, j+1], j))
        tour.append(nxt)
        remaining.remove(nxt)
        current = nxt+1
    return {"method": "nearest_neighbor", "cost": tour_cost(matrix, tour),
            "tour": tour, "seconds": time.perf_counter()-start}


def two_opt(matrix: np.ndarray) -> dict:
    """Improve nearest-neighbor with directed, full-cost 2-opt reversals."""
    start = time.perf_counter()
    greedy = nearest_neighbor(matrix)
    route, incumbent = greedy["tour"], greedy["cost"]
    improved = True
    while improved:
        improved = False
        for i in range(len(route)-1):
            for j in range(i+1, len(route)):
                candidate = route[:i] + list(reversed(route[i:j+1])) + route[j+1:]
                value = tour_cost(matrix, candidate)
                if value + 1e-9 < incumbent:
                    route, incumbent = candidate, value
                    improved = True
                    break
            if improved:
                break
    return {"method": "directed_2opt", "cost": incumbent,
            "tour": route, "seconds": time.perf_counter()-start}


def quantum_guard(n: int, limit: int = 9) -> dict:
    qubits = n*n
    return {
        "qubits_required": qubits,
        "ideal_statevector_bytes_lower_bound": 16 * (2 ** qubits),
        "qaoa_allowed": qubits <= limit,
        "reason": "Position encoding uses n squared binary variables",
    }


def measure_case(side: int, n: int, scenario: str, seed: int = 2026):
    start = time.perf_counter()
    graph, info = road_grid(side, scenario, seed)
    stops = select_stops(side, n, seed)
    matrix = distance_matrix(graph, stops)
    preprocessing = time.perf_counter()-start
    exact = held_karp_exact(matrix)
    greedy = nearest_neighbor(matrix)
    improvement = two_opt(matrix)
    for result in (exact, greedy, improvement):
        if abs(tour_cost(matrix, result["tour"])-result["cost"]) > 1e-8:
            raise AssertionError("Incorrect tour cost")
        if exact["cost"] > result["cost"]+1e-8:
            raise AssertionError("Exact reference worse than approximate method")
    record = {
        "scenario": scenario,
        "grid_side": side,
        "road_nodes": side*side,
        "service_stops": n,
        "depot_node": 0,
        "stop_nodes": stops,
        "synthetic": True,
        "roads": info,
        "preprocessing_seconds": preprocessing,
        "classical_exact": exact,
        "classical_greedy": greedy,
        "classical_2opt": improvement,
        "quantum_feasibility": quantum_guard(n),
        "distance_matrix": matrix.tolist(),
    }
    return record, matrix


def benchmark(seed: int = 2026, quantum: bool = False) -> dict:
    cases = []
    for side in SIZES:
        for scenario in SCENARIOS:
            for n in STOPS:
                record, matrix = measure_case(side, n, scenario, seed)
                if quantum and (side, scenario, n) == (10, "closure", 3):
                    # Exactly one additional Qiskit run, not Carlos's seed sweep.
                    from routing import qaoa_tour
                    q = qaoa_tour(matrix, seed=42, maxiter=35,
                                  reps=1, shots=512, max_qubits=9)
                    if q.get("status") == "completed":
                        route = q.get("tour")
                        valid = route is not None and sorted(route) == list(range(n))
                        q["feasible"] = bool(valid)
                        q["cost"] = tour_cost(matrix, route) if valid else None
                        q["gap_percent"] = (
                            100 * (q["cost"]-record["classical_exact"]["cost"])
                            / record["classical_exact"]["cost"]
                        ) if valid else None
                    record["qaoa"] = q
                cases.append(record)
    return {
        "study": "Q-Route: two-axis scaling (road network vs destinations)",
        "data_origin": "deterministic synthetic roads, NOT real Peru emergencies",
        "seed": seed, "quantum_hardware_used": False,
        "physical_scope": "one vehicle, no capacity or time windows",
        "road_node_counts": [s*s for s in SIZES],
        "destination_counts": list(STOPS),
        "scenarios": list(SCENARIOS),
        "quantum_study": "one QAOA run on closure/100 road nodes/3 stops" if quantum else "none",
        "methodology": [
            "NetworkX shortest paths process all road edges CLASSICALLY.",
            "Held-Karp provides the exact TSP minimum; greedy and directed 2-opt are classical baselines.",
            "For 3 stops, QUBO always uses 9 qubits, regardless of road count.",
            "QAOA is simulated, not executed on an IBM QPU.",
            "Increasing roads is NOT evidence that QAOA solves the full map.",
            "Statevector memory bound is not a measured hardware benchmark.",
        ],
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--quantum", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    data = benchmark(seed=args.seed, quantum=args.quantum)
    payload = json.dumps(data, indent=2, allow_nan=False)
    if args.output:
        from pathlib import Path
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
