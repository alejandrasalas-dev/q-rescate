"""Tests del modelo matemático (Angelo): cota de penalidad, orden de qubits e Ising."""
import itertools

import numpy as np
import pytest

from routing import STOPS, decode_tour, exact_tour, quadratic_program, road_network, tour_cost, travel_matrix


@pytest.mark.parametrize("scenario", ["normal", "bridge_closed", "flood_risk"])
def test_penalidad_justo_sobre_el_optimo_basta(scenario):
    """Proposición: A > C* => ningún estado inválido es mínimo global."""
    n = 3
    m = travel_matrix(road_network(scenario), STOPS[:n])
    opt = exact_tour(m)["cost"]
    model = quadratic_program(m, penalty=opt + 1e-3)
    for mask in range(1 << (n * n)):
        bits = [(mask >> k) & 1 for k in range(n * n)]
        if decode_tour(bits, n) is None:
            assert model.objective.evaluate(bits) > opt


@pytest.mark.parametrize("scenario", ["normal", "bridge_closed", "flood_risk"])
def test_ising_tiene_minimo_en_la_ruta_optima(scenario):
    """El estado fundamental del Hamiltoniano de Ising es la ruta óptima."""
    n = 3
    m = travel_matrix(road_network(scenario), STOPS[:n])
    opt = exact_tour(m)["cost"]
    op, offset = quadratic_program(m, penalty=opt + 1).to_ising()
    diag = np.real(np.diag(op.to_matrix())) + offset
    idx = int(np.argmin(diag))
    tour = decode_tour([(idx >> k) & 1 for k in range(n * n)], n)
    assert tour is not None
    assert np.isclose(tour_cost(m, tour), opt)
    assert np.isclose(diag[idx], opt)


def test_orden_de_qubits_x_p_i_es_n_por_p_mas_i():
    n = 3
    m = travel_matrix(road_network("normal"), STOPS[:n])
    names = [v.name for v in quadratic_program(m).variables]
    assert names == [f"x_{p}_{i}" for p in range(n) for i in range(n)]


@pytest.mark.parametrize("n", [2, 3])
def test_estados_validos_son_exactamente_las_n_factorial_permutaciones(n):
    """Proposición 1: R1+R2 <=> matriz de permutación (n! rutas, sin subtours)."""
    validos = set()
    for mask in range(1 << (n * n)):
        t = decode_tour([(mask >> k) & 1 for k in range(n * n)], n)
        if t is not None:
            validos.add(tuple(t))
    assert validos == set(itertools.permutations(range(n)))
