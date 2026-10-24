"""Q-Route: Grover amplitude amplification for better-than-greedy resource plans.

Grover's oracle is CLASSICALLY COMPILED from a complete truth table of 16
binary assignments. This is an educational demonstration in the *oracle query
model*, not an end-to-end quantum computational advantage. The exact classical
and local-search solvers already win on time and overall efficiency here.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from itertools import product

import numpy as np

from experiments.multi_resource_scale import (
    make_problem, assignment_to_plan, allocation_cost, exact_allocation,
    greedy_allocation, local_swap_allocation,
)

QUANTUM_BITS = 4


def classify_truth_table(problem, cutoff: float) -> dict:
    """Classically enumerate binary candidates to compile the pedagogical oracle."""
    if problem["vehicles"] != 2 or len(problem["tasks"]) != 4:
        raise ValueError("This 4-qubit Grover demo handles exactly 2 vehicles and 4 tasks")
    start = time.perf_counter()
    rows = []
    for mask in range(1 << QUANTUM_BITS):
        bits = tuple((mask >> i) & 1 for i in range(QUANTUM_BITS))
        feasible = sum(bits) == 2
        actual = None
        if feasible:
            plan = assignment_to_plan(problem, bits)
            actual = allocation_cost(problem, plan)
        marked = bool(feasible and actual < cutoff - 1e-7)
        rows.append({"mask": mask, "bits_le": list(bits),
                     "feasible": feasible, "cost": actual, "marked": marked})
    marked_masks = [r["mask"] for r in rows if r["marked"]]
    if not marked_masks:
        raise ValueError("No feasible plan beats the classical greedy baseline")
    return {"rows": rows, "marked_masks": marked_masks,
            "classical_candidates_checked_to_compile_oracle": len(rows),
            "classical_feasible_plans_checked_to_compile_oracle": sum(r["feasible"] for r in rows),
            "oracle_construction_classical_seconds": time.perf_counter()-start}


def phase_oracle(marked_masks: list[int]):
    """Apply a -1 phase to each marked 4-qubit basis state (little-endian)."""
    from qiskit import QuantumCircuit

    oracle = QuantumCircuit(QUANTUM_BITS, name="better_than_greedy")
    for mask in marked_masks:
        if not 0 <= mask < (1 << QUANTUM_BITS):
            raise ValueError("Invalid marked mask")
        zero_qubits = [i for i in range(QUANTUM_BITS) if not ((mask >> i) & 1)]
        for i in zero_qubits:
            oracle.x(i)
        oracle.h(QUANTUM_BITS - 1)
        oracle.mcx(list(range(QUANTUM_BITS - 1)), QUANTUM_BITS - 1)
        oracle.h(QUANTUM_BITS - 1)
        for i in zero_qubits:
            oracle.x(i)
    return oracle


def grover_circuit(marked_masks: list[int], iterations: int, measure: bool = False):
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import grover_operator

    if not 0 <= iterations <= 8:
        raise ValueError("Grover iterations out of bounded educational range")
    circ = QuantumCircuit(QUANTUM_BITS, name="QRoute_Grover")
    circ.h(range(QUANTUM_BITS))
    if iterations:
        g = grover_operator(phase_oracle(marked_masks))
        for _ in range(iterations):
            circ.compose(g, inplace=True)
    if measure:
        circ.measure_all()
    return circ


def experiment(span_km: float = 1800.0, scenario: str = "blocked_roads",
               shots: int = 2048, seed: int = 42) -> dict:
    """Classical baseline + ideal Qiskit Grover simulation for one instance."""
    from qiskit.quantum_info import Statevector
    from qiskit.primitives import StatevectorSampler
    if shots <= 0 or shots > 10_000:
        raise ValueError("shots must be in 1..10000")
    problem = make_problem(span_km, scenario, 2)
    exact = exact_allocation(problem)
    greedy = greedy_allocation(problem)
    swap = local_swap_allocation(problem)
    oracle_data = classify_truth_table(problem, cutoff=greedy["cost"])
    marked = oracle_data["marked_masks"]
    n = 1 << QUANTUM_BITS
    m = len(marked)
    theta = math.asin(math.sqrt(m/n))
    candidate_count = oracle_data["classical_feasible_plans_checked_to_compile_oracle"]
    record = {
        "experiment": "Q-Route resource assignment + Grover amplitude amplification",
        "data": "synthetic graph, resource depots, costs, deadlines and priorities",
        "scenario": scenario, "synthetic_span_km": span_km,
        "quantum_hardware_used": False,
        "qubits": QUANTUM_BITS, "all_binary_states": n,
        "feasible_classical_plans": candidate_count,
        "marked_states": m, "marked_masks": marked,
        "threshold": {"definition": "strictly lower total objective cost than greedy plan",
                      "value": greedy["cost"],
                      "chosen_from": "greedy baseline; does NOT require the exact optimum"},
        "greedy": greedy, "classical_exact": exact, "classical_local_swap": swap,
        "truth_table": oracle_data["rows"],
        "classical_oracle_compilation": {
            "all_binary_states_enumerated": oracle_data["classical_candidates_checked_to_compile_oracle"],
            "feasible_plans_costed": candidate_count,
            "seconds": oracle_data["oracle_construction_classical_seconds"],
        },
        "random_baseline": {
            "one_uniform_4bit_draw_success": m/n,
            "one_uniform_feasible_plan_draw_success": m/candidate_count,
            "three_independent_feasible_plan_draws_with_replacement_success":
                1 - (1-m/candidate_count)**3,
            "note": "blind random sampling, NOT a competitive optimized classical solver",
        },
        "grover": [],
        "limitations": [
            "Grover only amplifies the probability of finding a plan below the GREEDY cutoff.",
            "This truth-table oracle was constructed after evaluating ALL 16 binary states classically.",
            "Six feasible assignments were already checked to construct the oracle; no end-to-end quantum advantage.",
            "A Grover oracle query is not equivalent in runtime to a simple classical cost calculation.",
            "Classical exact DP and local search find the true optimum faster for this instance.",
            "Ideal Qiskit statevector simulation on classical CPU, not IBM quantum hardware.",
            "Do not generalize these 4-qubit results to national multi-vehicle optimization.",
            "A priori knowing which states to mark from the truth table makes this a demonstration of amplitude amplification, not scalable oracle synthesis.",
        ],
    }
    sampler = StatevectorSampler(default_shots=shots, seed=seed)
    for iterations in (0, 1, 2, 3):
        start = time.perf_counter()
        qc = grover_circuit(marked, iterations)
        state = Statevector.from_instruction(qc)
        probs = state.probabilities()
        ideal_success = float(sum(probs[x] for x in marked))
        expected_success = math.sin((2*iterations+1)*theta)**2
        if abs(ideal_success-expected_success) > 1e-8:
            raise AssertionError("Grover amplitude amplification does not match ideal analytic formula")
        measured_circuit = qc.copy()
        measured_circuit.measure_all()
        result = sampler.run([measured_circuit], shots=shots).result()
        counts = result[0].data.meas.get_counts()
        successes = sum(int(value) for label, value in counts.items()
                        if int(label.replace(" ", ""), 2) in marked)
        record["grover"].append({
            "iterations": iterations,
            "oracle_queries_per_shot": iterations,
            "shots": shots,
            "seed": seed,
            "successes": successes,
            "observed_success_rate": successes / shots,
            "ideal_success_probability": ideal_success,
            "statevector_seconds": time.perf_counter()-start,
        })
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--span-km", type=float, default=1800)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = experiment(shots=args.shots, seed=args.seed, span_km=args.span_km)
    payload = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        from pathlib import Path
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
