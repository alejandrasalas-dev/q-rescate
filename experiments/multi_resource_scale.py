"""Q-Route: two-to-four vehicles, priority deliveries and synthetic geographic scale.

Exact reference: assignment of exactly two destinations per vehicle, with each
vehicle's two-stop route ordered optimally. Quantum: only the two-vehicle,
four-destination case, using four QUBO variables with exactly-two constraint.

All roads, deadlines, depots and geography are SYNTHETIC; Peru-scale refers
only to an illustrative geographic span, NOT an actual Peruvian road network.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
from itertools import combinations, product
import json
import math
import random
import time

import networkx as nx
import numpy as np

SEED = 2026
SPANS_KM = (20, 200, 1800)
FLEETS = (2, 3, 4)
SCENARIOS = ("normal", "blocked_roads", "high_risk")
GRID_SIDE = 10
COST_UNITS = "synthetic weighted travel-km equivalent"


def road_graph(span_km: float, scenario: str, seed: int = SEED):
    """Directed grid scaled to a hypothetical regional or national extent.

    One fixed topology, rescaled from 20 to 1800 km per grid side. This
    isolates geographic distance from number of dispatch decisions/qubits.
    """
    if not math.isfinite(span_km) or span_km <= 0:
        raise ValueError("span_km must be positive and finite")
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario")
    side = GRID_SIDE
    rng = random.Random(seed)
    graph = nx.DiGraph()
    graph.add_nodes_from(range(side*side))
    step_km = span_km / (side-1)
    blocked = risky = 0
    for r in range(side):
        for c in range(side):
            u = r*side+c
            for v, direction in ((u+1, "horizontal"), (u+side, "vertical")):
                if direction == "horizontal" and c == side-1:
                    continue
                if direction == "vertical" and r == side-1:
                    continue
                forward = step_km*rng.uniform(0.85, 1.25)
                backward = step_km*rng.uniform(0.85, 1.25)
                # Keep first-column vertical spine plus every horizontal row.
                # Closing other vertical edges preserves strong connectivity.
                if (scenario == "blocked_roads" and direction == "vertical"
                        and c > 0 and ((u*17+v*31+seed) % 7 < 2)):
                    blocked += 1
                    continue
                if scenario == "high_risk" and (u*7+v*11+seed) % 6 == 0:
                    forward *= 1.7
                    backward *= 1.7
                    risky += 1
                graph.add_edge(u, v, weight=float(forward))
                graph.add_edge(v, u, weight=float(backward))
    if not nx.is_strongly_connected(graph):
        raise AssertionError("synthetic graph unexpectedly disconnected")
    return graph, {"nodes": graph.number_of_nodes(),
                   "directed_edges": graph.number_of_edges(),
                   "closed_bidirectional_roads": blocked,
                   "risk_penalized_bidirectional_roads": risky}


def locations(num_vehicles: int, seed: int = SEED):
    if num_vehicles not in FLEETS:
        raise ValueError("unsupported fleet")
    side = GRID_SIDE
    depots = (0, side*side-1, side-1, side*(side-1))[:num_vehicles]
    rng = random.Random(seed+2027)
    tasks = tuple(rng.sample([n for n in range(side*side) if n not in depots],
                             num_vehicles*2))
    return depots, tasks


def make_problem(span_km: float, scenario: str,
                 num_vehicles: int, seed: int = SEED):
    graph, info = road_graph(span_km, scenario, seed)
    depots, tasks = locations(num_vehicles, seed)
    nodes = depots + tasks
    lengths = {
        origin: nx.single_source_dijkstra_path_length(graph, origin, weight="weight")
        for origin in nodes
    }
    matrix = np.asarray([[lengths[u][v] for v in nodes] for u in nodes],
                        dtype=float)
    n = len(tasks)
    # Every service has an explicit synthetic deadline and priority. These
    # are NOT real emergency-service SLAs or incident measurements.
    deadlines = tuple(span_km*(0.25+0.10*(i%3)) for i in range(n))
    priority = tuple(1+(i%3) for i in range(n))
    return {
        "span_km": span_km, "scenario": scenario, "vehicles": num_vehicles,
        "depots": depots, "tasks": tasks,
        "deadline_weighted_units": deadlines, "priorities": priority,
        "matrix": matrix, "road_info": info,
        "synthetic": True,
    }


def route_score(problem, vehicle: int, tasks_order: tuple[int, ...]) -> float:
    """Trip score = directed travel distance plus deadline-lateness penalty."""
    vcount = problem["vehicles"]
    matrix = problem["matrix"]
    depot_index = vehicle
    prev = depot_index
    elapsed = total = 0.0
    for task in tasks_order:
        node = vcount+task
        leg = float(matrix[prev, node])
        total += leg
        elapsed += leg
        deadline = problem["deadline_weighted_units"][task]
        total += max(0.0, elapsed-deadline)*problem["priorities"][task]*0.5
        prev = node
    total += float(matrix[prev, depot_index])
    return float(total)


def route_pair(problem, vehicle: int, i: int, j: int):
    if i == j:
        raise ValueError("distinct destinations required")
    options = ((i, j), (j, i))
    return min(((route_score(problem, vehicle, order), order) for order in options),
               key=lambda pair: (pair[0], pair[1]))


def pair_table(problem):
    n = len(problem["tasks"])
    return {
        (v, i, j): route_pair(problem, v, i, j)
        for v in range(problem["vehicles"])
        for i, j in combinations(range(n), 2)
    }


def allocation_cost(problem, plan):
    """Validate one assignment and recalculate its true original objective."""
    n = len(problem["tasks"])
    v = problem["vehicles"]
    if len(plan) != v:
        raise ValueError("one route per resource is required")
    seen = []
    total = 0.0
    for resource, order in enumerate(plan):
        if len(order) != 2:
            raise ValueError("resource capacity is exactly two services")
        seen.extend(order)
        total += route_score(problem, resource, tuple(order))
    if sorted(seen) != list(range(n)):
        raise ValueError("every destination must be served exactly once")
    return float(total)


def exact_allocation(problem):
    """Exact DP over service-subsets: O(v * 2^n * n^2), n<=8."""
    start = time.perf_counter()
    n, vcount = len(problem["tasks"]), problem["vehicles"]
    table = pair_table(problem)
    @lru_cache(None)
    def solve(v, remaining_mask):
        if v == vcount:
            return (0.0, ()) if remaining_mask == 0 else (math.inf, ())
        available = [i for i in range(n) if remaining_mask & (1 << i)]
        best = (math.inf, ())
        for i, j in combinations(available, 2):
            subcost, subplan = solve(v+1, remaining_mask ^ (1<<i) ^ (1<<j))
            stepcost, order = table[(v, i, j)]
            candidate = (stepcost+subcost, (order,)+subplan)
            if candidate < best:
                best = candidate
        return best
    cost, plan = solve(0, (1<<n)-1)
    check = allocation_cost(problem, plan)
    if abs(check-cost) > 1e-7:
        raise AssertionError("DP returned inconsistent route cost")
    return {"method": "exact_classical_DP", "cost": cost,
            "plan": [list(x) for x in plan],
            "seconds": time.perf_counter()-start,
            "resources": vcount}


def greedy_allocation(problem):
    start = time.perf_counter()
    n, vcount = len(problem["tasks"]), problem["vehicles"]
    table = pair_table(problem)
    remaining = set(range(n))
    plan = []
    for v in range(vcount):
        _, order = min((table[(v,i,j)] for i,j in combinations(sorted(remaining),2)),
                       key=lambda x: (x[0], x[1]))
        plan.append(order)
        remaining.difference_update(order)
    return {"method": "greedy_allocation", "cost": allocation_cost(problem, plan),
            "plan": [list(x) for x in plan],
            "seconds": time.perf_counter()-start}


def local_swap_allocation(problem):
    """Local-search baseline: swap assigned tasks between two resources."""
    start = time.perf_counter()
    table = pair_table(problem)
    plan = [tuple(route) for route in greedy_allocation(problem)["plan"]]
    cost = allocation_cost(problem, plan)
    while True:
        best = (cost, tuple(tuple(x) for x in plan))
        for va, vb in combinations(range(problem["vehicles"]), 2):
            for ia, ib in product(range(2), repeat=2):
                proposal = [list(route) for route in plan]
                proposal[va][ia], proposal[vb][ib] = proposal[vb][ib], proposal[va][ia]
                proposed_plan = []
                for vehicle, route in enumerate(proposal):
                    i, j = sorted(route)
                    proposed_plan.append(table[(vehicle,i,j)][1])
                proposed_cost = allocation_cost(problem, proposed_plan)
                if proposed_cost < best[0]-1e-8:
                    best = (proposed_cost, tuple(proposed_plan))
        if best[0] >= cost-1e-8:
            break
        cost, plan = best
    return {"method": "classical_local_swap", "cost": cost,
            "plan": [list(x) for x in plan],
            "seconds": time.perf_counter()-start}


def build_four_qubit_qubo(problem):
    """Exactly 2 vehicles, 4 tasks and capacity 2: exact QUBO over valid plans.

    z_i=1 means task i belongs to vehicle 0, 0 to vehicle 1.
    The objective is a quadratic expansion of singleton/pair trip costs.
    It is *exact on feasible two-task-per-vehicle assignments*; outside that
    domain its energy is an algebraic extrapolation, controlled by penalties.
    """
    if problem["vehicles"] != 2 or len(problem["tasks"]) != 4:
        raise ValueError("4-qubit QUBO only valid for 2 resources, 4 services")
    from qiskit_optimization import QuadraticProgram
    n = 4
    single = {(v,i): route_score(problem,v,(i,))
              for v in range(2) for i in range(n)}
    pairs = {(v,i,j): route_pair(problem,v,i,j)[0]
             for v in range(2) for i,j in combinations(range(n),2)}
    delta = {(v,i,j): pairs[(v,i,j)]-single[(v,i)]-single[(v,j)]
             for v in range(2) for i,j in combinations(range(n),2)}
    constant = sum(single[(1,i)] for i in range(n))
    constant += sum(delta[(1,i,j)] for i,j in combinations(range(n),2))
    linear = {
        i: single[(0,i)]-single[(1,i)]-
        sum(delta[(1,min(i,j),max(i,j))] for j in range(n) if j != i)
        for i in range(n)
    }
    quadratic = {(i,j): delta[(0,i,j)]+delta[(1,i,j)]
                 for i,j in combinations(range(n),2)}
    def unpenalized(bits):
        return constant+sum(linear[i]*bits[i] for i in range(n))+sum(
            quadratic[(i,j)]*bits[i]*bits[j] for i,j in combinations(range(n),2))
    enumerated = list(product((0,1), repeat=n))
    valid = [unpenalized(b) for b in enumerated if sum(b)==2]
    invalid = [unpenalized(b) for b in enumerated if sum(b)!=2]
    penalty = float(max(1.0, max(valid)-min(invalid)+1.0,
                        2*max(pairs.values())))
    qp = QuadraticProgram("two_resources_four_services")
    for i in range(n):
        qp.binary_var(name=f"z_{i}")
    # Constraint penalty P*(sum_i z_i - 2)^2:
    # 4P - 3P sum_i z_i + 2P sum_{i<j} z_i*z_j.
    qp.minimize(
        constant=constant+4*penalty,
        linear={f"z_{i}":linear[i]-3*penalty for i in range(n)},
        quadratic={(f"z_{i}",f"z_{j}"):quadratic[(i,j)]+2*penalty
                   for i,j in combinations(range(n),2)}
    )
    exact = exact_allocation(problem)["cost"]
    for bits in enumerated:
        energy = float(qp.objective.evaluate(np.array(bits,dtype=float)))
        if sum(bits) == 2:
            plan = assignment_to_plan(problem, bits)
            actual = allocation_cost(problem, plan)
            if not math.isclose(energy, actual, rel_tol=1e-9, abs_tol=1e-5):
                raise AssertionError(f"QUBO vs real cost mismatch: {bits}")
        elif energy <= exact+1e-7:
            raise AssertionError("QUBO infeasible assignment could beat exact optimum")
    return qp, penalty


def assignment_to_plan(problem, bits):
    if len(bits)!=4 or any(x not in (0,1) for x in bits) or sum(bits)!=2:
        raise ValueError("infeasible resource assignment")
    groups = ([i for i,z in enumerate(bits) if z==1],
              [i for i,z in enumerate(bits) if z==0])
    return (route_pair(problem,0,*groups[0])[1],
            route_pair(problem,1,*groups[1])[1])


def qaoa_vehicles(problem, seed: int = 42, shots: int = 512,
                  maxiter: int = 45):
    from qiskit.primitives import StatevectorSampler
    from qiskit_algorithms import QAOA
    from qiskit_algorithms.optimizers import COBYLA
    from qiskit_algorithms.utils import algorithm_globals
    from qiskit_optimization.algorithms import MinimumEigenOptimizer

    qp, penalty = build_four_qubit_qubo(problem)
    algorithm_globals.random_seed=seed
    start=time.perf_counter()
    result=MinimumEigenOptimizer(QAOA(
        sampler=StatevectorSampler(seed=seed,default_shots=shots),
        optimizer=COBYLA(maxiter=maxiter),reps=1)).solve(qp)
    seconds=time.perf_counter()-start
    raw=np.asarray(result.x,dtype=float)
    feasible = (len(raw)==4 and np.all(np.isfinite(raw)) and
                np.all((raw==0)|(raw==1)) and np.sum(raw)==2)
    plan=assignment_to_plan(problem,tuple(int(x) for x in raw)) if feasible else None
    return {"method":"Qiskit_QAOA_4qubits","status":"completed",
            "feasible":bool(feasible),
            "assignment_bits":raw.tolist(),
            "plan":[list(x) for x in plan] if plan is not None else None,
            "cost":allocation_cost(problem,plan) if plan is not None else None,
            "seconds":seconds,"seed":seed,"shots":shots,"maxiter":maxiter,
            "reps":1,"qubits":4,"penalty":penalty,
            "simulator":"StatevectorSampler local (classical CPU)"}


def benchmark(include_quantum=False, seed=SEED):
    cases=[]
    for span in SPANS_KM:
        for scenario in SCENARIOS:
            for vehicles in FLEETS:
                start=time.perf_counter()
                problem=make_problem(span,scenario,vehicles,seed)
                preprocessing=time.perf_counter()-start
                exact=exact_allocation(problem)
                greedy=greedy_allocation(problem)
                swap=local_swap_allocation(problem)
                assert exact["cost"]<=min(greedy["cost"],swap["cost"])+1e-6
                result={"span_km":span, "scenario":scenario,
                        "road_nodes":problem["road_info"]["nodes"],
                        "resource_count":vehicles,"task_count":2*vehicles,
                        "capacity_per_resource":2,
                        "priorities":list(problem["priorities"]),
                        "deadlines":list(problem["deadline_weighted_units"]),
                        "depots":list(problem["depots"]),
                        "task_nodes":list(problem["tasks"]),
                        "roads":problem["road_info"],
                        "preprocessing_seconds":preprocessing,
                        "exact":exact,"greedy":greedy,"local_swap":swap,
                        "estimated_simple_assignment_bit_count":2*vehicles*vehicles,
                        "quantum": {"status":"not_run", "reason":
                           "No general multi-resource QUBO implemented for this size"}}
                if include_quantum and span==1800 and scenario=="blocked_roads" and vehicles==2:
                    q=qaoa_vehicles(problem)
                    q["gap_percent"]=(100*(q["cost"]-exact["cost"])/exact["cost"]
                                      if q["feasible"] else None)
                    result["quantum"]=q
                cases.append(result)
    return {
        "project":"Q-Route",
        "experiment":"multi-resource regional-to-Peru-scale synthetic geography",
        "data_origin":"synthetic 10x10 grid, synthetic priority and deadlines",
        "real_Peru_road_network":False,
        "physical_IBM_QPU":False,
        "objective":"total asymmetric travel score plus weighted tardiness",
        "constraints":["each task served exactly once",
                       "two tasks per resource (capacity two)",
                       "resource-specific depot",
                       "directed road closures and penalties",
                       "priorities and delivery deadlines"],
        "cases":cases
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--quantum",action="store_true")
    parser.add_argument("--output",default="")
    args=parser.parse_args()
    payload=json.dumps(benchmark(include_quantum=args.quantum),indent=2,allow_nan=False)
    if args.output:
        from pathlib import Path
        path=Path(args.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(payload+"\n",encoding="utf-8")
    else:
        print(payload)


if __name__=="__main__":
    main()
