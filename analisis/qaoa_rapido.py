"""
QAOA rápido para análisis (mismo circuito que qiskit_algorithms.QAOA, pero
evaluando el statevector directamente). Permite ver la DISTRIBUCIÓN completa,
no solo la mejor muestra.
"""
import numpy as np
from scipy.optimize import minimize
from qiskit.quantum_info import SparsePauliOp, Statevector

try:
    from qiskit.circuit.library import qaoa_ansatz as _qaoa
except ImportError:
    from qiskit.circuit.library import QAOAAnsatz as _qaoa


def diagonal(op: SparsePauliOp):
    """Energía de cada estado base del Hamiltoniano de Ising (diagonal)."""
    nq = op.num_qubits
    idx = np.arange(2 ** nq)
    z = 1 - 2 * ((idx[:, None] >> np.arange(nq)) & 1)
    d = np.zeros(2 ** nq)
    for pauli, coef in zip(op.paulis, op.coeffs):
        d += coef.real * np.prod(np.where(pauli.z, z, 1), axis=1)
    return d


def qaoa_distribucion(op, reps=1, maxiter=35, alpha=1.0, seed=42, normalizar=False):
    """Devuelve la distribución de probabilidad final sobre los 2^n estados.
    alpha=1 -> valor esperado (QAOA estándar); alpha<1 -> CVaR."""
    if normalizar:
        op = (op / np.max(np.abs(op.coeffs))).simplify()
    diag = diagonal(op)
    orden = np.argsort(diag)
    circ = _qaoa(op, reps=reps)

    def objetivo(theta):
        p = Statevector(circ.assign_parameters(theta)).probabilities()
        if alpha >= 1:
            return float(p @ diag)
        ps, acum = p[orden], np.cumsum(p[orden])
        c = np.searchsorted(acum, alpha) + 1
        q = ps[:c].copy(); q[-1] -= max(acum[c - 1] - alpha, 0)
        return float(q @ diag[orden][:c] / alpha)

    rng = np.random.default_rng(seed)
    r = minimize(objetivo, rng.uniform(0, np.pi, circ.num_parameters),
                 method="COBYLA", options={"maxiter": maxiter})
    return Statevector(circ.assign_parameters(r.x)).probabilities()
