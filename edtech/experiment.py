"""Quantum Probability Lab: educational Monte Carlo vs iterative QAE with Qiskit.

A known toy Bernoulli probability p is encoded in a quantum preparation circuit.
The oracle contains p by construction: this is a teaching example, NOT an
end-to-end quantum speedup or estimation of an inaccessible real-world risk.
"""
from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np


def check_inputs(p: float, samples: int, epsilon: float, alpha: float) -> None:
    if not math.isfinite(p) or not 0.0 < p < 1.0:
        raise ValueError("p debe estar entre 0 y 1, sin incluir extremos")
    if samples < 1 or samples > 100_000:
        raise ValueError("samples debe estar entre 1 y 100000")
    if not 0.0 < epsilon <= 0.5:
        raise ValueError("epsilon debe estar entre 0 y 0.5")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha debe estar entre 0 y 1")


def monte_carlo(p: float, samples: int, seed: int) -> dict:
    """Estimate Bernoulli p using an explicitly seeded classical sample."""
    start = time.perf_counter()
    rng = np.random.default_rng(seed)
    successes = int(np.count_nonzero(rng.random(samples) < p))
    estimate = successes / samples
    return {
        "method": "Monte Carlo clásico",
        "estimate": float(estimate),
        "absolute_error": float(abs(estimate - p)),
        "samples": samples,
        "successes": successes,
        "seconds": float(time.perf_counter() - start),
    }


def iterative_qae(p: float, epsilon: float, alpha: float, seed: int,
                  shots: int) -> dict:
    """Qiskit IQAE on a one-qubit pedagogical oracle, using a local simulator."""
    from qiskit import QuantumCircuit
    from qiskit.primitives import StatevectorSampler
    from qiskit_algorithms import EstimationProblem, IterativeAmplitudeEstimation

    preparation = QuantumCircuit(1)
    preparation.ry(2 * math.asin(math.sqrt(p)), 0)
    problem = EstimationProblem(state_preparation=preparation, objective_qubits=[0])
    start = time.perf_counter()
    solver = IterativeAmplitudeEstimation(
        epsilon_target=epsilon,
        alpha=alpha,
        sampler=StatevectorSampler(default_shots=shots, seed=seed),
    )
    result = solver.estimate(problem)
    estimate = float(result.estimation)
    lower, upper = (float(x) for x in result.confidence_interval)
    return {
        "method": "Qiskit Iterative Amplitude Estimation",
        "estimate": estimate,
        "absolute_error": abs(estimate - p),
        "confidence_interval": [lower, upper],
        "interval_covers_reference": bool(lower <= p <= upper),
        "epsilon_target": epsilon,
        "alpha": alpha,
        "shots_per_circuit": shots,
        "grover_oracle_queries_reported_by_qiskit": int(result.num_oracle_queries),
        "seconds": float(time.perf_counter() - start),
        "qubits": 1,
        "backend": "StatevectorSampler (simulación clásica)",
    }


def experiment(p: float = 0.2, samples: int = 256, epsilon: float = 0.1,
               alpha: float = 0.05, seed: int = 42, shots: int = 100) -> dict:
    check_inputs(p, samples, epsilon, alpha)
    if shots < 1 or shots > 5000:
        raise ValueError("shots debe estar entre 1 y 5000")
    return {
        "project": "Quantum Probability Lab",
        "scope": "demo educativa con probabilidad sintética conocida",
        "reference_probability": p,
        "monte_carlo": monte_carlo(p, samples, seed),
        "quantum": iterative_qae(p, epsilon, alpha, seed, shots),
        "scientific_caveats": [
            "La probabilidad p se codifica en el circuito RY; no es desconocida para quien prepara el oráculo.",
            "Las consultas al oráculo Grover no son equivalentes una a una a muestras clásicas.",
            "Una sola corrida no demuestra ventaja práctica ni garantía estadística observada.",
            "Los tiempos del simulador clásico no miden rendimiento en hardware cuántico.",
            "La aceleración cuadrática de QAE es teórica, en el modelo adecuado de consultas.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Experimento educativo QAE vs Monte Carlo")
    parser.add_argument("--probability", type=float, default=0.2)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--epsilon", type=float, default=0.1)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shots", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(experiment(args.probability, args.samples, args.epsilon,
                                args.alpha, args.seed, args.shots), indent=2))


if __name__ == "__main__":
    main()
