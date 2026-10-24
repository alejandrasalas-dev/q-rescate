"""Scientific regression checks for Q-Route Grover oracle demonstration."""
import math
import numpy as np
import pytest

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from experiments.multi_resource_scale import (
    make_problem, greedy_allocation, exact_allocation,
)
from experiments.grover_impact import (
    classify_truth_table, phase_oracle, grover_circuit, experiment,
)


def test_marked_states_are_feasible_and_better_than_greedy():
    problem = make_problem(1800, "blocked_roads", 2)
    greedy = greedy_allocation(problem)
    exact = exact_allocation(problem)
    labels = classify_truth_table(problem, greedy["cost"])
    assert len(labels["rows"]) == 16
    assert labels["classical_feasible_plans_checked_to_compile_oracle"] == 6
    assert labels["marked_masks"] == [5]
    marked_costs = [r["cost"] for r in labels["rows"] if r["marked"]]
    assert marked_costs == pytest.approx([exact["cost"]])
    assert exact["cost"] < greedy["cost"]


def test_oracle_marks_only_better_feasible_states():
    problem = make_problem(1800, "blocked_roads", 2)
    labels = classify_truth_table(problem, greedy_allocation(problem)["cost"])
    oracle = phase_oracle(labels["marked_masks"])
    for mask in range(16):
        circuit = QuantumCircuit(4)
        for bit in range(4):
            if (mask >> bit) & 1:
                circuit.x(bit)
        circuit.compose(oracle, inplace=True)
        state = Statevector.from_instruction(circuit)
        measured_amplitude = state.data[mask]
        sign = -1 if mask in labels["marked_masks"] else 1
        assert measured_amplitude == pytest.approx(sign)
        assert sum(abs(x)**2 for x in state.data) == pytest.approx(1.0)


def test_grover_probability_matches_analytic_formula():
    mark = [5]
    initial_theta = math.asin(1 / 4)
    rates = []
    for iteration in range(4):
        state = Statevector.from_instruction(grover_circuit(mark, iteration))
        measured = float(state.probabilities()[5])
        expected = math.sin((2*iteration+1)*initial_theta)**2
        assert measured == pytest.approx(expected, abs=1e-8)
        rates.append(measured)
    assert rates[0] == pytest.approx(1/16)
    assert rates[1] > 0.45
    assert rates[2] > 0.90
    assert rates[3] > 0.95


def test_end_to_end_qiskit_sampler_is_better_than_blind_random_sampling():
    report = experiment(shots=512, seed=42)
    assert report["marked_masks"] == [5]
    assert report["classical_oracle_compilation"]["all_binary_states_enumerated"] == 16
    assert report["classical_oracle_compilation"]["feasible_plans_costed"] == 6
    assert report["classical_exact"]["cost"] < report["greedy"]["cost"]
    assert report["random_baseline"]["one_uniform_feasible_plan_draw_success"] == pytest.approx(1/6)
    assert report["grover"][3]["ideal_success_probability"] > 0.95
    assert report["grover"][3]["observed_success_rate"] > 0.85
    assert report["quantum_hardware_used"] is False
    assert "ALL 16 binary states" in " ".join(report["limitations"])
