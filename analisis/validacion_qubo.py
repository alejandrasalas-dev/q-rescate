"""
Validación del modelo QUBO y de QAOA (Angelo).

Preguntas que responde:
  1. ¿Qué penalidad mínima garantiza que ninguna ruta inválida sea el óptimo?
  2. ¿La penalidad fija de 1000 perjudica a QAOA?
  3. ¿QAOA concentra probabilidad en la ruta óptima, o "acierta" solo porque
     512 shots casi cubren los 512 estados posibles de 9 qubits?

Ejecutar desde la raíz:  python -m analisis.validacion_qubo
"""
import itertools
import json
import sys

import numpy as np

sys.path.insert(0, ".")
from routing import STOPS, decode_tour, exact_tour, quadratic_program, road_network, tour_cost, travel_matrix  # noqa: E402
from analisis.qaoa_rapido import qaoa_distribucion  # noqa: E402

SHOTS = 512
SEMILLAS = range(10)


def info_estados(matrix, n):
    """Para cada uno de los 2^(n²) estados: factible?, óptimo?"""
    opt = exact_tour(matrix)["cost"]
    nq = n * n
    fact = np.zeros(2 ** nq, bool)
    optimo = np.zeros(2 ** nq, bool)
    for idx in range(2 ** nq):
        bits = [(idx >> k) & 1 for k in range(nq)]
        t = decode_tour(bits, n)
        if t is not None:
            fact[idx] = True
            optimo[idx] = abs(tour_cost(matrix, t) - opt) < 1e-9
    return fact, optimo, opt


def p_acierto_con_shots(p_opt, shots=SHOTS):
    """Probabilidad de que AL MENOS una de las muestras sea la ruta óptima."""
    return 1 - (1 - p_opt) ** shots


def analizar(escenario, n=3):
    m = travel_matrix(road_network(escenario), STOPS[:n])
    fact, optimo, opt = info_estados(m, n)
    peor = max(tour_cost(m, t) for t in itertools.permutations(range(n)))
    nq = n * n
    p_azar = optimo.sum() / 2 ** nq
    filas = {"escenario": escenario, "costo_optimo": opt, "peor_ruta": peor,
             "penalidad_minima_suficiente": f"> {opt} (todo costo >= 0, cada violación suma >= A)",
             "azar": {"P_optima_por_shot": p_azar, "P_acierta_en_512": p_acierto_con_shots(p_azar)},
             "configs": []}
    configs = [  # (nombre, A, alpha, reps, maxiter, normalizar)
        ("Equipo: A=1000, p=1, 35 iter", 1000, 1.0, 1, 35, False),
        ("A calibrada, p=1, 35 iter", peor, 1.0, 1, 35, False),
        ("A calibrada + CVaR, p=1, 35 iter", peor, 0.25, 1, 35, False),
        ("MEJORADO: A calibrada + normalizado + CVaR, p=2, 150 iter", peor, 0.25, 2, 150, True),
    ]
    for nombre, A, alpha, reps, maxiter, norm in configs:
        op, _ = quadratic_program(m, penalty=A).to_ising()
        res = []
        for s in SEMILLAS:
            p = qaoa_distribucion(op, reps=reps, maxiter=maxiter, alpha=alpha, seed=s, normalizar=norm)
            res.append((p[fact].sum(), p[optimo].sum()))
        res = np.array(res)
        filas["configs"].append({
            "config": nombre, "A": A,
            "P_factible_media": round(res[:, 0].mean(), 4),
            "P_optima_media": round(res[:, 1].mean(), 4),
            "P_optima_min_max": [round(res[:, 1].min(), 4), round(res[:, 1].max(), 4)],
            "amplificacion_vs_azar": round(res[:, 1].mean() / p_azar, 1),
            "P_acierta_en_512_shots": round(p_acierto_con_shots(res[:, 1].mean()), 3),
        })
    return filas


if __name__ == "__main__":
    salida = [analizar(e) for e in ("normal", "bridge_closed", "flood_risk")]
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    with open("analisis/resultados_validacion.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
