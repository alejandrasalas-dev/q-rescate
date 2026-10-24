"""Deterministic tests for actual multi-stop vehicle routing (no quantum run)."""
import itertools

import numpy as np
import pytest
from routing import (
    STOPS, road_network, travel_matrix, tour_cost, exact_tour,
    greedy_tour, quadratic_program, decode_tour, benchmark
)


@pytest.mark.parametrize("scenario", ["normal", "bridge_closed", "flood_risk"])
@pytest.mark.parametrize("n", [2, 3, 4])
def test_exact_solution_matches_all_tours(scenario, n):
    matrix = travel_matrix(road_network(scenario), STOPS[:n])
    brute = min(tour_cost(matrix, route) for route in itertools.permutations(range(n)))
    exact = exact_tour(matrix)
    assert exact["cost"] == brute
    assert sorted(exact["tour"]) == list(range(n))
    assert greedy_tour(matrix)["cost"] >= exact["cost"]


def test_blocked_road_is_removed_from_graph_and_changes_travel_matrix():
    base = road_network("normal")
    changed = road_network("bridge_closed")
    assert base.has_edge("X", "B")
    assert not changed.has_edge("X", "B")
    assert not changed.has_edge("B", "X")
    normal = travel_matrix(base, STOPS[:3])
    closed = travel_matrix(changed, STOPS[:3])
    assert not np.array_equal(normal, closed)


def test_risk_scenario_changes_road_costs_without_deleting_connections():
    base = road_network("normal")
    risky = road_network("flood_risk")
    assert risky.number_of_edges() == base.number_of_edges()
    assert risky["N"]["A"]["weight"] > base["N"]["A"]["weight"]


@pytest.mark.parametrize("n", [2, 3])
def test_qubo_energy_equals_original_cost_for_every_valid_tour(n):
    matrix = travel_matrix(road_network("normal"), STOPS[:n])
    model = quadratic_program(matrix)
    for tour in itertools.permutations(range(n)):
        bits = np.zeros(n * n)
        for p, i in enumerate(tour):
            bits[n * p + i] = 1
        assert np.isclose(model.objective.evaluate(bits), tour_cost(matrix, tour))
        assert decode_tour(bits, n) == list(tour)


@pytest.mark.parametrize("n", [2, 3])
def test_qubo_penalties_prevent_invalid_global_optimum(n):
    matrix = travel_matrix(road_network("normal"), STOPS[:n])
    model = quadratic_program(matrix)
    optimum = exact_tour(matrix)["cost"]
    for mask in range(1 << (n*n)):
        bits = [(mask >> idx) & 1 for idx in range(n*n)]
        if decode_tour(bits, n) is None:
            assert model.objective.evaluate(bits) > optimum


def test_invalid_routes_and_bad_input_rejected():
    matrix = travel_matrix(road_network("normal"), STOPS[:3])
    with pytest.raises(ValueError):
        tour_cost(matrix, [0, 0, 1])
    with pytest.raises(ValueError):
        road_network("not_a_scenario")
    assert decode_tour([1] * 9, 3) is None


def test_benchmark_classical_only_has_sizes_and_scenarios():
    result = benchmark(quantum=False)
    assert result["quantum_hardware_used"] is False
    assert {e["size"] for e in result["entries"]} == {2, 3, 4}
    assert {e["scenario"] for e in result["entries"]} == {
        "normal", "bridge_closed", "flood_risk"}
    assert all("qaoa" not in e for e in result["entries"])
