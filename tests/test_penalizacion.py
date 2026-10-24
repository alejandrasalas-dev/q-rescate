"""Tests de la penalización QUBO (issue #5, tarea 3).

Estos tests FALLAN con la penalización fija penalty=1000 y pasan con la
penalización calculada a partir de la matriz (penalty_bound)."""
import numpy as np
import pytest

from routing import STOPS, decode_tour, exact_tour, quadratic_program, road_network, travel_matrix


def _argmin_qubo(model, n):
    """Mínimo global del QUBO por enumeración exhaustiva (n <= 3)."""
    best_q, best_bits = None, None
    for mask in range(1 << (n * n)):
        bits = [(mask >> k) & 1 for k in range(n * n)]
        q = model.objective.evaluate(bits)
        if best_q is None or q < best_q:
            best_q, best_bits = q, bits
    return best_q, best_bits


@pytest.mark.parametrize("scenario", ["normal", "bridge_closed", "flood_risk"])
def test_penalidad_por_defecto_valida_con_tiempos_en_segundos(scenario):
    """Mismo problema expresado en segundos y con trayectos ~3 veces más largos
    (escala realista de Lima Este). Cambiar de unidades NO debe cambiar la solución.
    Con penalty=1000 fijo, el mínimo del QUBO pasa a ser una ruta INVÁLIDA."""
    n = 3
    m = travel_matrix(road_network(scenario), STOPS[:n]) * 60 * 3  # minutos -> segundos, x3
    q, bits = _argmin_qubo(quadratic_program(m), n)
    assert decode_tour(bits, n) is not None
    assert np.isclose(q, exact_tour(m)["cost"])


def test_penalidad_no_positiva_se_rechaza():
    """Con A <= 0 el QUBO premia violar restricciones (el estado vacío gana)."""
    m = travel_matrix(road_network("normal"), STOPS[:3])
    for bad in (0, -5):
        with pytest.raises(ValueError):
            quadratic_program(m, penalty=bad)


@pytest.mark.parametrize("scenario", ["normal", "bridge_closed", "flood_risk"])
def test_penalidad_por_defecto_no_cambia_resultados_actuales(scenario):
    """Compatibilidad: con los datos actuales (minutos) se sigue usando A = 1000,
    así que el benchmark del equipo no cambia."""
    from routing import penalty_bound
    m = travel_matrix(road_network(scenario), STOPS[:3])
    assert penalty_bound(m) < 1000
    default = quadratic_program(m)
    explicit = quadratic_program(m, penalty=1000)
    for mask in range(1 << 9):
        bits = [(mask >> k) & 1 for k in range(9)]
        assert default.objective.evaluate(bits) == explicit.objective.evaluate(bits)
