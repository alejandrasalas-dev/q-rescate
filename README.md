# Q-Rescate: Quantum versus classical optimization

Exploratory prototype for Qiskit Fall Fest 2026. All inputs and costs are **synthetic** and are not operational emergency guidance.

## What it tests
Qiskit QAOA and exact enumeration on 3 brigades and 3 communities, with one-to-one assignments under three scenarios: normal roads, a blocked road, and increased travel risk. The exact classical optimum considers all six valid permutations. QAOA runs locally with nine binary variables mapped to qubits.

## Run
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python qrescate.py
```

## Interpretation and limitations
- QAOA results are approximate and stochastic. Compare the **original objective** and hard feasibility constraints against the exact optimum.
- A classical simulation **cannot demonstrate practical quantum speedup**. The small assignment model is easily solved exactly by classical methods.
- The blocked-road scenario is currently modeled with a large finite cost in the QUBO; the exact evaluator separately treats that route as forbidden. A QAOA result selecting it is reported as infeasible; a subsequent revision should encode hard exclusions explicitly.
- Tests target feasibility, model penalty sufficiency, and exact baseline correctness. Benchmark results must not be claimed until actually executed and recorded.
- Future expansion to real multi-stop routing needs explicit sequence/capacity constraints. This MVP optimizes **assignments**, not full vehicle routing.

See GitHub issue #1 for the broader experimental plan.
