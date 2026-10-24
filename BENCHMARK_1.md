# Benchmark 1: Qiskit QAOA vs exact baseline

Source: [GitHub Actions run 40111045679](https://github.com/alejandrasalas-dev/q-rescate/actions/runs/40111045679), 2026-10-24, branch `feat/qaoa-poc`.

All costs are **synthetic arbitrary cost units** (not measured travel times). Qiskit 2.6.1, Qiskit Algorithms 0.4.0, Qiskit Optimization 0.7.0, Python 3.11.17, `StatevectorSampler` with 2048 shots, QAOA reps=1, COBYLA maxiter=80, seed=42. Runs on **classical simulator**.

| Scenario | Exact cost | QAOA cost | Gap | Exact assignment (zero-based) | QAOA assignment (zero-based) | QAOA feasible | QAOA runtime |
|---|---:|---:|---:|---|---|---|---:|
| Normal | 9 | 15 | 6 | (0,1,2) | (1,0,2) | Yes | 91.79 s |
| Blocked road | 18 | 20 | 2 | (0,2,1) | (2,1,0) | Yes | 103.45 s |
| Increased risk | 21 | 30 | 9 | (2,0,1) | (2,1,0) | Yes | 85.74 s |

**Interpretation:** QAOA returned feasible assignments in all three cases but did not reach the exact optimum with these hyperparameters. There is no demonstrated quantum advantage, and no fair end-to-end speed comparison: exact baseline runtime wasn't measured, and QAOA is simulated classically. Repeated seeds, penalty sensitivity and depth tuning are needed to evaluate robustness.

**Scope caveat:** The current formulation is one-to-one **brigade assignment**, not multi-stop vehicle routing. The blocked edge is a surrogate finite QUBO cost plus feasibility validation; explicitly enforce its exclusion before claiming an operationally valid constrained formulation. No claims of suitability for real disaster dispatch.
