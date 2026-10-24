from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Literal
import json
import uuid

METHODS = {"exact": ("Clásico exacto", "#1673e6"), "greedy": ("Greedy", "#e99b20"), "qaoa": ("QAOA simulado", "#8025dc")}
STATES = {"ready": "Listo", "running": "Calculando", "completed": "Completado", "cancelled": "Cancelado", "error": "Error"}

def uid():
    return uuid.uuid4().hex[:12]

def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value) or not low <= value <= high:
        raise ValueError(f"Número fuera de rango: {value!r} ({low} a {high})")
    return value

@dataclass
class Point:
    id: str
    name: str
    lat: float
    lng: float

    def __post_init__(self):
        number(self.lat, -90, 90)
        number(self.lng, -180, 180)
        if not isinstance(self.id, str) or not self.id or not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 150:
            raise ValueError("Identificador o nombre de punto inválido")

@dataclass
class Zone:
    id: str
    name: str
    lat: float
    lng: float
    radius_m: float
    kind: Literal["operation", "exclusion"]

    def __post_init__(self):
        Point(self.id, self.name, self.lat, self.lng)
        number(self.radius_m, 10, 500000)
        if self.kind not in ("operation", "exclusion"):
            raise ValueError("Tipo de zona desconocido")

@dataclass
class Config:
    methods: list[str] = field(default_factory=lambda: ["exact", "qaoa"])
    seed: int = 42
    shots: int = 512
    reps: int = 1
    maxiter: int = 35
    vehicles: int = 1
    timeout_seconds: int = 300

    def __post_init__(self):
        if not isinstance(self.methods, list) or any(m not in METHODS for m in self.methods) or len(set(self.methods)) != len(self.methods):
            raise ValueError("Métodos inválidos")
        for attr, low, high in (("seed", 0, 2147483647), ("shots", 1, 10000000), ("reps", 1, 1000), ("maxiter", 1, 1000000), ("vehicles", 1, 100), ("timeout_seconds",1,900)):
            v = getattr(self, attr)
            number(v, low, high)
            if not isinstance(v, int):
                raise ValueError(f"{attr} debe ser entero")

@dataclass
class Scenario:
    name: str = "Nuevo escenario"
    base: Point | None = None
    destinations: list[Point] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    config: Config = field(default_factory=Config)
    schema_version: int = 1

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("Se requiere schema_version 1")
        allowed = {"schema_version", "name", "base", "destinations", "zones", "config"}
        if set(raw) - allowed:
            raise ValueError("Campos de escenario desconocidos")
        name = raw.get("name", "Nuevo escenario")
        if not isinstance(name, str) or not name.strip() or len(name) > 150:
            raise ValueError("Nombre de escenario inválido")
        ds, zs = raw.get("destinations", []), raw.get("zones", [])
        if not isinstance(ds, list) or len(ds) > 1000 or not isinstance(zs, list) or len(zs) > 1000:
            raise ValueError("Lista de destinos o zonas inválida")
        result = cls(name=name, base=Point(**raw["base"]) if raw.get("base") else None,
                     destinations=[Point(**p) for p in ds], zones=[Zone(**z) for z in zs], config=Config(**raw.get("config", {})))
        ids = [p.id for p in result.destinations + result.zones] + ([result.base.id] if result.base else [])
        if len(set(ids)) != len(ids):
            raise ValueError("Identificadores duplicados")
        return result

    def clone(self):
        return self.from_dict(self.to_dict())

    def dumps(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)

@dataclass(frozen=True)
class Capabilities:
    connected: bool = False
    max_bases: int = 1
    max_vehicles: int = 1
    max_destinations: int = 3
    max_qaoa_destinations: int = 3
    max_qubits: int = 9
    shots_min: int = 1
    shots_max: int = 8192
    reps_max: int = 10
    maxiter_max: int = 1000
    methods: tuple[str, ...] = ("exact", "greedy", "qaoa")
    experiments: bool = False
    cancellation: bool = False
    qubit_encoding: str = "position_n_squared"
    min_destinations: int = 1
    max_operation_zones: int = 1
    fixed_reps: int | None = None
    fixed_maxiter: int | None = None
    timeout_max_seconds: int = 900

@dataclass
class BackendError:
    code: str
    message: str
    details: dict = field(default_factory=dict)
    retryable: bool = False

@dataclass
class Geometry:
    # GeoJSON: [longitude, latitude], EPSG:4326. Never a synthetic straight line.
    type: str = "LineString"
    coordinates: list[list[float]] = field(default_factory=list)

    def __post_init__(self):
        if self.type != "LineString":
            raise ValueError("Se requiere GeoJSON LineString")
        if self.coordinates and len(self.coordinates) < 2:
            raise ValueError("La geometría necesita al menos dos puntos")
        for coord in self.coordinates:
            if len(coord) != 2:
                raise ValueError("Coordenadas [longitud, latitud] requeridas")
            number(coord[0], -180, 180)
            number(coord[1], -90, 90)

@dataclass
class MethodResult:
    method: str
    cost: float | None = None
    gap_percent: float | None = None
    valid: bool | None = None
    duration_seconds: float | None = None
    visit_order: list[str] = field(default_factory=list)
    geometry: Geometry | None = None
    messages: list[str] = field(default_factory=list)
    unit: str = ""
    status: str = "ok"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.method not in METHODS:
            raise ValueError("Método de resultado desconocido")
        for attr in ("cost", "gap_percent", "duration_seconds"):
            if getattr(self, attr) is not None:
                number(getattr(self, attr), -1e100 if attr != "duration_seconds" else 0, 1e100)
        if self.valid is not None and type(self.valid) is not bool:
            raise ValueError("valid debe ser booleano o null")

@dataclass
class JobSnapshot:
    job_id: str
    state: str
    results: list[MethodResult] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    progress_percent: float | None = None
    error: BackendError | None = None
    experiment_rows: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.state not in STATES:
            raise ValueError("Estado de cálculo desconocido")
        if self.progress_percent is not None:
            number(self.progress_percent, 0, 100)

def validate_for_run(s: Scenario, caps: Capabilities):
    if not caps.connected:
        return "Backend no conectado. Conecta un servicio para calcular recorridos."
    if not s.base:
        return "Coloca una base en el mapa."
    if not s.destinations:
        return "Agrega al menos un destino."
    if len(s.destinations)<caps.min_destinations:
        return f"El motor requiere al menos {caps.min_destinations} destinos."
    if sum(z.kind=='operation' for z in s.zones)>caps.max_operation_zones:
        return f"El motor admite {caps.max_operation_zones} zona de operación."
    if caps.fixed_reps is not None and s.config.reps!=caps.fixed_reps:
        return f"El motor utiliza reps={caps.fixed_reps} fijo."
    if caps.fixed_maxiter is not None and s.config.maxiter!=caps.fixed_maxiter:
        return f"El motor utiliza maxiter={caps.fixed_maxiter} fijo."
    if s.config.timeout_seconds>caps.timeout_max_seconds:
        return "El plazo excede el límite del motor."
    if len(s.destinations) > caps.max_destinations:
        return f"El backend admite hasta {caps.max_destinations} destinos."
    if not s.config.methods:
        return "Selecciona al menos un método."
    if any(m not in caps.methods for m in s.config.methods):
        return "Hay un método no disponible en el backend."
    if s.config.vehicles > caps.max_vehicles:
        return "Se excede el límite de vehículos del backend."
    if not caps.shots_min <= s.config.shots <= caps.shots_max or s.config.reps > caps.reps_max or s.config.maxiter > caps.maxiter_max:
        return "Los parámetros exceden los límites del backend."
    if "qaoa" in s.config.methods:
        if len(s.destinations) > caps.max_qaoa_destinations:
            return f"QAOA admite hasta {caps.max_qaoa_destinations} destinos."
        if caps.qubit_encoding == "position_n_squared" and len(s.destinations) ** 2 > caps.max_qubits:
            return "El escenario excede el límite de qubits."
    return ""
