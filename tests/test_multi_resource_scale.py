"""Multi-resource QUBO and geographic-scaling tests; QAOA runs separately in CI."""
from itertools import combinations
import math

import networkx as nx
import numpy as np
import pytest

from experiments.multi_resource_scale import (
    road_graph, locations, make_problem, route_score, route_pair,
    allocation_cost, exact_allocation, greedy_allocation,
    local_swap_allocation, build_four_qubit_qubo, assignment_to_plan,
    benchmark, SPANS_KM, SCENARIOS
)


@pytest.mark.parametrize("span_km", SPANS_KM)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_graph_connected_and_directed_with_real_closures(span_km, scenario):
    graph, info=road_graph(span_km,scenario)
    assert graph.number_of_nodes()==100
    assert nx.is_strongly_connected(graph)
    normal,_=road_graph(span_km,"normal")
    if scenario=="blocked_roads":
        assert info["closed_bidirectional_roads"]>0
        assert graph.number_of_edges()<normal.number_of_edges()
        for u,v,data in graph.edges(data=True):
            assert data["weight"]==normal[u][v]["weight"]
    if scenario=="high_risk":
        assert info["risk_penalized_bidirectional_roads"]>0
        assert graph.number_of_edges()==normal.number_of_edges()
        assert all(graph[u][v]["weight"]>=normal[u][v]["weight"]
                   for u,v in normal.edges)


@pytest.mark.parametrize("vehicles", [2,3,4])
def test_exact_allocation_respects_all_resources_and_capacity(vehicles):
    p=make_problem(200,"blocked_roads",vehicles)
    exact=exact_allocation(p)
    assert len(exact["plan"])==vehicles
    assert all(len(route)==2 for route in exact["plan"])
    assert math.isclose(allocation_cost(p,exact["plan"]),exact["cost"])
    assert exact["cost"]<=greedy_allocation(p)["cost"]+1e-6
    assert exact["cost"]<=local_swap_allocation(p)["cost"]+1e-6


def test_multiple_resources_exact_against_six_manual_allocations():
    p=make_problem(20,"normal",2)
    exact=exact_allocation(p)
    costs=[]
    for selected in combinations(range(4),2):
        other=tuple(i for i in range(4) if i not in selected)
        a=route_pair(p,0,*selected)[1]
        b=route_pair(p,1,*other)[1]
        costs.append(allocation_cost(p,(a,b)))
    assert len(costs)==6
    assert exact["cost"]==pytest.approx(min(costs))


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("span_km", SPANS_KM)
def test_qubo_energy_matches_true_cost_and_penalizes_invalid(scenario,span_km):
    p=make_problem(span_km,scenario,2)
    qp,penalty=build_four_qubit_qubo(p)
    assert len(qp.variables)==4
    optimum=exact_allocation(p)["cost"]
    assert penalty>0
    for mask in range(16):
        bits=tuple((mask>>i)&1 for i in range(4))
        energy=float(qp.objective.evaluate(np.asarray(bits,dtype=float)))
        if sum(bits)==2:
            assert energy==pytest.approx(allocation_cost(
                p,assignment_to_plan(p,bits)),abs=1e-5,rel=1e-9)
        else:
            assert energy>optimum


def test_geo_span_changes_cost_not_number_of_tasks_or_qubits():
    small=make_problem(20,"normal",2)
    big=make_problem(1800,"normal",2)
    assert len(small["tasks"])==len(big["tasks"])==4
    assert small["depots"]==big["depots"]
    assert small["tasks"]==big["tasks"]
    assert big["matrix"]==pytest.approx(small["matrix"]*90,rel=1e-9)
    assert exact_allocation(big)["cost"]==pytest.approx(
        exact_allocation(small)["cost"]*90,rel=1e-9)
    assert len(build_four_qubit_qubo(small)[0].variables)==4
    assert len(build_four_qubit_qubo(big)[0].variables)==4


def test_bad_capacities_are_rejected():
    p=make_problem(20,"normal",2)
    with pytest.raises(ValueError):
        allocation_cost(p,((0,1,2),(3,)))
    with pytest.raises(ValueError):
        allocation_cost(p,((0,1),(1,2)))
    with pytest.raises(ValueError):
        assignment_to_plan(p,(1,1,1,0))


def test_27_classical_cases_and_consistent_geo_scope():
    report=benchmark(include_quantum=False)
    assert len(report["cases"])==27
    assert {x["span_km"] for x in report["cases"]}==set(SPANS_KM)
    assert {x["scenario"] for x in report["cases"]}==set(SCENARIOS)
    assert {x["resource_count"] for x in report["cases"]}=={2,3,4}
    assert report["real_Peru_road_network"] is False
    assert all(x["exact"]["cost"]<=x["local_swap"]["cost"]+1e-6
               for x in report["cases"])
    assert all(x["quantum"]["status"]=="not_run" for x in report["cases"])
