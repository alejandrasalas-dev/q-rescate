"""
Contrato de datos entre la interfaz (PySide6) y el motor.

La interfaz construye una `Solicitud` (o su dict/JSON equivalente) y recibe un
`Resultado`. Todo es serializable a JSON para pasarlo entre procesos.

Ejemplo de solicitud (JSON):
{
  "base":      {"id": "H", "nombre": "Hospital base", "lat": -5.1945, "lon": -80.6328},
  "destinos": [{"id": "A", "nombre": "Punto 1", "lat": -5.1860, "lon": -80.6290}, ...],
  "zona_operacion": {"lat": -5.1945, "lon": -80.6328, "radio_m": 3000},
  "exclusiones": [{"lat": -5.1900, "lon": -80.6200, "radio_m": 300}],
  "metodos": ["exacto", "voraz", "qaoa"],
  "semilla": 3, "shots": 512, "max_qubits": 9, "timeout_s": 180
}
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

METODOS_VALIDOS = ("exacto", "voraz", "qaoa")


@dataclass
class Punto:
    id: str
    lat: float
    lon: float
    nombre: str = ""


@dataclass
class Circulo:
    lat: float
    lon: float
    radio_m: float


@dataclass
class Solicitud:
    base: Punto
    destinos: list[Punto]
    zona_operacion: Optional[Circulo] = None
    exclusiones: list[Circulo] = field(default_factory=list)
    metodos: list[str] = field(default_factory=lambda: ["exacto", "voraz", "qaoa"])
    semilla: int = 42
    shots: int = 512
    max_qubits: int = 9
    timeout_s: float = 180.0

    def validar(self) -> None:
        if not 2 <= len(self.destinos) <= 4:
            raise ValueError("Se necesitan entre 2 y 4 destinos.")
        ids = [self.base.id] + [d.id for d in self.destinos]
        if len(set(ids)) != len(ids):
            raise ValueError("Los identificadores de base y destinos deben ser únicos.")
        for m in self.metodos:
            if m not in METODOS_VALIDOS:
                raise ValueError(f"Método desconocido: {m}")
        for c in ([self.zona_operacion] if self.zona_operacion else []) + self.exclusiones:
            if c.radio_m <= 0:
                raise ValueError("Los radios deben ser positivos.")

    @staticmethod
    def desde_dict(d: dict) -> "Solicitud":
        zona = d.get("zona_operacion")
        return Solicitud(
            base=Punto(**d["base"]),
            destinos=[Punto(**p) for p in d["destinos"]],
            zona_operacion=Circulo(**zona) if zona else None,
            exclusiones=[Circulo(**c) for c in d.get("exclusiones", [])],
            metodos=list(d.get("metodos", ["exacto", "voraz", "qaoa"])),
            semilla=int(d.get("semilla", 42)),
            shots=int(d.get("shots", 512)),
            max_qubits=int(d.get("max_qubits", 9)),
            timeout_s=float(d.get("timeout_s", 180)),
        )

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResultadoMetodo:
    metodo: str                      # "exacto" | "voraz" | "qaoa"
    estado: str                      # "ok" | "omitido" | "error"
    orden: list[str] = field(default_factory=list)       # ["H", "A", "C", "B", "H"]
    costo_min: Optional[float] = None
    gap_pct: Optional[float] = None  # respecto al exacto
    valida: Optional[bool] = None
    duracion_s: Optional[float] = None
    geometria: list[list[float]] = field(default_factory=list)  # [[lat, lon], ...] recorrido completo
    detalle: str = ""                # motivo de omisión/error o info (qubits, backend)


@dataclass
class Resultado:
    estado: str                      # "ok" | "error" | "cancelado" | "tiempo_agotado"
    mensaje: str = ""
    puntos: list[dict] = field(default_factory=list)       # puntos ajustados a la red
    inaccesibles: list[str] = field(default_factory=list)  # ids de destinos sin camino
    matriz_min: list[list[float]] = field(default_factory=list)
    metodos: list[ResultadoMetodo] = field(default_factory=list)
    red: dict = field(default_factory=dict)                # info: nodos, aristas, aristas_excluidas, fuente

    def a_dict(self) -> dict:
        return asdict(self)
