# Q-Rescate: real multi-stop routing experiment

**New experiment, separate from the former 3×3 assignment benchmark.**

## Core problem
One ambulance departs from a hospital, must visit 2-4 distinct emergency points in some order, and returns to the hospital. A **directed** synthetic road graph models one-way/asymmetric travel, road closure and increased risk-related travel cost. NetworkX recomputes shortest *legal* paths on the road graph after each change.

This is a small directed **traveling salesperson problem (TSP)** with a fixed depot, not yet the multiple-vehicle capacity-constrained VRP. QAOA optimizes the *order* of stops using a position-encoded QUBO, with `n^2` binary decision variables and one-hot constraints for each position and stop.

## Three comparators
- Exact classical solver checks all `n!` permutations and certifies the minimum for these small examples.
- Nearest-neighbor baseline returns a simple feasible heuristic tour.
- Qiskit QAOA attempts the same TSP/QUBO using a **classically simulated quantum circuit**. It might return an invalid sample, and if so the run is reported as infeasible. There is **no presumption of quantum advantage**.

## Experiment matrix
- Normal, 2 stops (4 qubits, QAOA enabled).
- Normal, 3 stops (9 qubits, QAOA enabled).
- Bridge closure, 3 stops (9 qubits, QAOA enabled).
- Increased risk, 3 stops (9 qubits, QAOA enabled).
- Normal, 4 stops (16 qubits; QAOA **skipped** by a 9-qubit guard; classical comparison available).

All values are synthetic test costs; they are **not** real Peruvian travel times or road condition forecasts. Optimizing sequence is legitimate but does not yet model actual patient triage, medical eligibility, travel time windows, capacity or multiple ambulances. Future risk likelihood Monte Carlo would be a classical scenario-generation extension, not part of this proof of concept.

## Locally
```bash
python -m pip install -r requirements.txt
python -m pytest tests/test_routing.py -q
python routing.py --classical-only
python routing.py --max-qubits 9
```

The GitHub Actions workflow `Test multi-stop routing and QAOA benchmark` saves `routing-benchmark.json` and `routing-classical.json` as artifacts. Review the workflow run for actual measured outputs.

## Interpretation
- Report exact cost, greedy cost, QAOA cost/gap, feasibility and runtime *per scenario*.
- Compare the **same shortest-path travel cost matrix** for all solvers. The circuit dimension grows as `n^2` and statevector simulation memory roughly exponentially in qubits.
- Simulator runtimes do not demonstrate real quantum hardware acceleration.
- Do not claim a practical dispatch solution or real disaster response readiness.

Related tracking task: [issue #3](https://github.com/alejandrasalas-dev/q-rescate/issues/3).
