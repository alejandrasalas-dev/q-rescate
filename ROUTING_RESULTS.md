# Validated routing benchmark: 24 October 2026

[GitHub Actions run #40113271525](https://github.com/alejandrasalas-dev/q-rescate/actions/runs/40113271525) on commit `6db95966faa6fb71cde4668a40b3215718939534`. All 17 routing tests passed. The pipeline completed successfully and uploaded the JSON benchmark.

## Results (synthetic travel-cost units)

| Scenario | Stops | Exact classic | Greedy classic | QAOA | Gap vs exact | QAOA runtime | Qubits |
|---|---:|---:|---:|---:|---:|---:|---:|
| Normal | 2 | 17 | 17 | **17** | 0% | 0.58 s | 4 |
| Normal | 3 | 23 | 23 | **23** | 0% | 52.38 s | 9 |
| Bridge closed | 3 | 24 | 24 | **24** | 0% | 45.05 s | 9 |
| Increased flood risk | 3 | **28** | 29 | **28** | 0% | 44.49 s | 9 |
| Normal | 4 | 25 | 25 | Not run | N/A | N/A | 16 (skipped) |

QAOA returned feasible tours in all four runs where it was executed. On the flood-risk scenario, QAOA matched the exact optimum and outperformed **nearest-neighbor only** (28 versus 29), which is not evidence of quantum superiority over an exact solver or competitive classical routing algorithms.

QAOA configuration: Qiskit `StatevectorSampler` (classically simulated quantum circuits), seed 42, COBYLA, depth/reps 1, 35 max iterations, 512 shots. Four stops would require 16 qubits for this position encoding; the workflow deliberately skipped it due to the 9-qubit runtime guard. The classical exact solver enumerated permutations for 2, 3 and 4 stops.

## Correct scientific claims

1. **Demonstrated:** A Qiskit QAOA circuit can solve the small, genuine multi-stop routing TSP formulation with feasible routes and exact-optimal costs in the tested cases.
2. **Not demonstrated:** Any practical quantum advantage, better asymptotic runtime, faster execution, or superiority over strong classical solvers. QAOA was orders of magnitude slower on the 3-stop cases when executed on a classical simulator.
3. **Limits:** These costs and geographic structures are synthetic; only one vehicle is considered. No patient triage, ambulance capacity, time windows, live emergency data or real road maps are present. QAOA needs repeated seeds to assess robustness.

## Next step

Add multi-seed reliability measurements and compare with a stronger classical VRP baseline. To support multiple ambulances with real constraints, model a capacitated multi-vehicle VRP in a separate controlled phase, using decomposition rather than naively expanding statevector simulation.
