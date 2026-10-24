"""Deterministic regression tests for separate road-network/TSP scaling study."""
import itertools

import networkx as nx
import pytest

from experiments.scale_study import (
    SCENARIOS, benchmark, road_grid, select_stops, distance_matrix,
    tour_cost, held_karp_exact, nearest_neighbor, two_opt, quantum_guard
)


@pytest.mark.parametrize("side", [5, 10, 20])
def test_closures_preserve_common_road_weights_and_connectivity(side):
    normal, _ = road_grid(side, "normal")
    closed, info = road_grid(side, "closure")
    assert info["removed_undirected_roads"] > 0
    assert closed.number_of_edges() < normal.number_of_edges()
    assert nx.is_strongly_connected(closed)
    for u, v, edge in closed.edges(data=True):
        assert normal[u][v]["weight"] == edge["weight"]


@pytest.mark.parametrize("side", [5, 10, 20])
def test_risk_only_increases_costs(side):
    normal, _ = road_grid(side, "normal")
    risky, info = road_grid(side, "risk")
    assert info["risk_penalized_undirected_roads"] > 0
    assert set(risky.edges) == set(normal.edges)
    assert any(risky[u][v]["weight"] > normal[u][v]["weight"] for u, v in normal.edges)
    assert all(risky[u][v]["weight"] >= normal[u][v]["weight"] for u, v in normal.edges)


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("n", [3, 4, 5])
def test_exact_dp_matches_bruteforce_and_heuristics(scenario, n):
    graph, _ = road_grid(5, scenario)
    matrix = distance_matrix(graph, select_stops(5, n))
    exact = held_karp_exact(matrix)
    exhaustive = min(tour_cost(matrix, p) for p in itertools.permutations(range(n)))
    assert exact["cost"] == exhaustive
    assert tour_cost(matrix, exact["tour"]) == exhaustive
    assert nearest_neighbor(matrix)["cost"] >= exhaustive
    assert two_opt(matrix)["cost"] >= exhaustive


def test_quantum_guard_distinguishes_graph_scale_from_tsp_scale():
    assert quantum_guard(3)["qubits_required"] == 9
    assert quantum_guard(3)["qaoa_allowed"]
    assert quantum_guard(6)["qubits_required"] == 36
    assert not quantum_guard(6)["qaoa_allowed"]
    assert quantum_guard(10)["qubits_required"] == 100
    assert not quantum_guard(10)["qaoa_allowed"]


def test_all_27_cases_reproducible():
    data = benchmark(seed=2026, quantum=False)
    cases = data["cases"]
    assert len(cases) == 27
    assert {x["road_nodes"] for x in cases} == {25, 100, 400}
    assert {x["service_stops"] for x in cases} == {3, 6, 10}
    assert {x["scenario"] for x in cases} == set(SCENARIOS)
    assert all(x["classical_exact"]["cost"] <= x["classical_greedy"]["cost"] for x in cases)
    assert all(x["classical_exact"]["cost"] <= x["classical_2opt"]["cost"] for x in cases)
    assert all("qaoa" not in x for x in cases)
    assert [x["distance_matrix"] for x in cases] == [
        x["distance_matrix"] for x in benchmark(seed=2026, quantum=False)["cases"]
    ]
