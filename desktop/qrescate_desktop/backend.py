"""Replace only this port/adapter to connect the engine. No UI imports here."""
from typing import Protocol
from .models import Capabilities, Scenario, JobSnapshot

class BackendPort(Protocol):
    def capabilities(self) -> Capabilities: ...
    def submit(self, scenario: Scenario) -> str: ...
    def status(self, job_id: str) -> JobSnapshot: ...
    def cancel(self, job_id: str) -> None: ...
    def submit_experiments(self, scenario: Scenario, seeds: list[int]) -> str: ...

class DisconnectedBackend:
    def capabilities(self):
        return Capabilities()

    def _unavailable(self, *args):
        raise ConnectionError("Backend no conectado")

    submit = status = cancel = submit_experiments = _unavailable
