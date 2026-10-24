"""Solicitudes de ejemplo para el botón «Cargar ejemplo» de la interfaz (Satipo, Junín).

Coordenadas aproximadas para la demo; no representan instalaciones reales.
"""
from __future__ import annotations

import copy

_BASE = {"id": "H", "nombre": "Base (centro de Satipo)", "lat": -11.2537, "lon": -74.6378}

EJEMPLOS: dict[str, dict] = {
    "satipo_3_destinos": {
        "base": _BASE,
        "destinos": [
            {"id": "A", "nombre": "Punto 1", "lat": -11.2480, "lon": -74.6340},
            {"id": "B", "nombre": "Punto 2", "lat": -11.2600, "lon": -74.6420},
            {"id": "C", "nombre": "Punto 3", "lat": -11.2560, "lon": -74.6300},
        ],
        "zona_operacion": {"lat": -11.2537, "lon": -74.6378, "radio_m": 1500},
        "exclusiones": [],
        "metodos": ["exacto", "voraz", "qaoa"],
        "semilla": 42, "shots": 512, "max_qubits": 9, "timeout_s": 180,
    },
    "satipo_con_exclusion": {
        "base": _BASE,
        "destinos": [
            {"id": "A", "nombre": "Punto 1", "lat": -11.2480, "lon": -74.6340},
            {"id": "B", "nombre": "Punto 2", "lat": -11.2600, "lon": -74.6420},
            {"id": "C", "nombre": "Punto 3", "lat": -11.2560, "lon": -74.6300},
        ],
        "zona_operacion": {"lat": -11.2537, "lon": -74.6378, "radio_m": 1500},
        "exclusiones": [{"lat": -11.2510, "lon": -74.6360, "radio_m": 120}],
        "metodos": ["exacto", "voraz", "qaoa"],
        "semilla": 42, "shots": 512, "max_qubits": 9, "timeout_s": 180,
    },
}

EJEMPLOS['satipo_2_destinos'] = copy.deepcopy(EJEMPLOS['satipo_3_destinos'])
EJEMPLOS['satipo_2_destinos']['destinos'] = EJEMPLOS['satipo_2_destinos']['destinos'][:2]
EJEMPLOS['satipo_2_destinos']['timeout_s'] = 300


def ejemplo(nombre: str) -> dict:
    """Copia independiente (la interfaz puede modificarla sin afectar el original)."""
    return copy.deepcopy(EJEMPLOS[nombre])
