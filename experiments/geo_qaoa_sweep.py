"""Nine bounded simulated QAOA runs: geography 20/200/1800 km x 3 seeds.

Scientific purpose: compare the *same* 4-qubit resource-allocation QUBO
structure at different road distances, not prove an intrinsic speed advantage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from experiments.multi_resource_scale import (
    SPANS_KM, make_problem, exact_allocation, greedy_allocation,
    local_swap_allocation, qaoa_vehicles
)

SEEDS = (3, 7, 42)


def experiment():
    cases=[]
    for span in SPANS_KM:
        problem=make_problem(span,"blocked_roads",2)
        exact=exact_allocation(problem)
        greedy=greedy_allocation(problem)
        local=local_swap_allocation(problem)
        samples=[]
        for seed in SEEDS:
            q=qaoa_vehicles(problem,seed=seed,shots=512,maxiter=45)
            q["gap_percent"] = (100*(q["cost"]-exact["cost"])/exact["cost"]
                                if q["feasible"] else None)
            samples.append(q)
        cases.append({
            "span_km":span, "scenario":"blocked_roads",
            "road_nodes":problem["road_info"]["nodes"],
            "vehicles":2, "tasks":4, "qubits":4,
            "exact":exact, "greedy":greedy, "local_swap":local,
            "qaoa_by_seed":samples,
            "feasible_runs":sum(int(s["feasible"]) for s in samples),
            "optimal_runs":sum(int(s["feasible"] and
                  abs(s["cost"]-exact["cost"])<1e-6) for s in samples)
        })
    return {"purpose":"controlled distance scaling, not quantum advantage",
            "inputs":"same topology, depot/task indices and constraints; synthetic distance scale",
            "physical_quantum_hardware":False,"seeds":list(SEEDS),
            "cases":cases,
            "limits":[
                "Only one QUBO size (4 qubits), no demonstrated computational complexity scaling.",
                "Simulation on CPU; no QPU-time or energy benchmark.",
                "Three seeds per case too few for general statistical claims.",
                "Vehicle assignment is QAOA; within-route order precomputed classically.",
                "NOT a map of real Peru or road closures."
            ]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="")
    args=parser.parse_args()
    payload=json.dumps(experiment(),indent=2,allow_nan=False)
    if args.output:
        path=Path(args.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(payload+"\n",encoding="utf-8")
    else:
        print(payload)


if __name__=="__main__":
    main()
