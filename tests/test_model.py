import itertools
import numpy as np
from qrescate import BASE, BLOCKED, SCENARIOS, assignments, decode, evaluate, exact, quadratic_program

def test_exact_is_minimum():
    cost, assignment = exact(BASE)
    assert cost == min(evaluate(BASE, a) for a in assignments())
    assert sorted(assignment) == [0, 1, 2]

def test_change_in_road_access_changes_solution():
    normal = exact(SCENARIOS["normal"], BLOCKED["normal"])
    blocked = exact(SCENARIOS["blocked_road"], BLOCKED["blocked_road"])
    assert normal[1] != blocked[1]
    assert not any((i, j) in BLOCKED["blocked_road"] for i, j in enumerate(blocked[1]))

def test_decode_feasibility():
    assert decode([1,0,0,0,1,0,0,0,1]) == (0,1,2)
    assert decode([1,1,0,0,0,0,0,0,1]) is None

def test_qubo_feasible_energies_match_objective():
    qp = quadratic_program(BASE)
    for assignment in itertools.permutations(range(3)):
        bits = np.zeros(9)
        for i, j in enumerate(assignment):
            bits[3*i+j] = 1
        assert np.isclose(qp.objective.evaluate(bits), evaluate(BASE, assignment))

def test_qubo_penalizes_invalid_solutions():
    qp = quadratic_program(BASE)
    valid_opt, _ = exact(BASE)
    for mask in range(1 << 9):
        bits = [(mask >> k) & 1 for k in range(9)]
        if decode(bits) is None:
            assert qp.objective.evaluate(bits) > valid_opt
