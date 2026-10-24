"""Deterministic checks; no claimed quantum speedup."""
import math
import pytest

from edtech.experiment import check_inputs, monte_carlo, experiment


@pytest.mark.parametrize("p", [-0.1, 0, 1, 1.1, float("nan")])
def test_invalid_probability(p):
    with pytest.raises(ValueError):
        check_inputs(p, 100, 0.1, 0.05)


def test_classical_seed_reproducible():
    a = monte_carlo(0.2, 256, 42)
    b = monte_carlo(0.2, 256, 42)
    assert a["estimate"] == b["estimate"]
    assert 0 <= a["estimate"] <= 1
    assert a["successes"] <= a["samples"]


def test_qae_one_qubit_toy_simulation_runs():
    result = experiment(p=0.2, samples=100, epsilon=0.15,
                        alpha=0.05, seed=42, shots=100)
    quantum = result["quantum"]
    assert quantum["qubits"] == 1
    assert math.isfinite(quantum["estimate"])
    assert 0 <= quantum["estimate"] <= 1
    assert quantum["grover_oracle_queries_reported_by_qiskit"] >= 0
    lo, hi = quantum["confidence_interval"]
    assert 0 <= lo <= hi <= 1
    assert "simulaci" in quantum["backend"]
    assert result["reference_probability"] == 0.2
    assert len(result["scientific_caveats"]) >= 4
