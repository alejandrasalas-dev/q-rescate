"""All backend I/O runs outside the GUI thread; polling never overlaps."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from PySide6.QtCore import QObject, Signal, QTimer
from .models import JobSnapshot, BackendError, validate_for_run

class Controller(QObject):
    updated = Signal(object)
    capabilities_ready = Signal(object)
    _done = Signal(str, object, object)

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qrescate-service")
        self.job_id = None
        self.busy = False
        self.pending = False
        self.history = []
        self.scenario = None
        self.kind = "calculation"
        self.timer = QTimer(self)
        self.timer.setInterval(750)
        self.timer.timeout.connect(self.poll)
        self._done.connect(self.receive)

    def call(self, op, fn, *args):
        future = self.executor.submit(fn, *args)
        def finished(f):
            try:
                result, error = f.result(), None
            except Exception as exc:
                result, error = None, BackendError(type(exc).__name__, str(exc))
            self._done.emit(op, result, error)
        future.add_done_callback(finished)

    def connect_backend(self):
        self.call("capabilities", self.backend.capabilities)

    def start(self, scenario, caps, seeds=None):
        if self.busy:
            return False
        error = validate_for_run(scenario, caps)
        if error or (seeds is not None and not caps.experiments):
            self.updated.emit(JobSnapshot("", "error", error=BackendError("VALIDATION", error or "Servicio de experimentos no disponible")))
            return False
        self.scenario = scenario.clone()
        self.kind = "experiments" if seeds is not None else "calculation"
        self.busy = True
        self.job_id = None
        self.updated.emit(JobSnapshot("", "running", messages=["Enviando solicitud al backend…"]))
        if seeds is not None:
            self.call("submit", self.backend.submit_experiments, self.scenario.clone(), seeds)
        else:
            self.call("submit", self.backend.submit, self.scenario.clone())
        return True

    def poll(self):
        if self.job_id and self.busy and not self.pending:
            self.pending = True
            self.call("status", self.backend.status, self.job_id)

    def cancel(self):
        if self.job_id and self.busy:
            self.call("cancel", self.backend.cancel, self.job_id)

    def receive(self, op, result, error):
        if op == "capabilities":
            if error:
                self.updated.emit(JobSnapshot("", "error", error=error))
            else:
                self.capabilities_ready.emit(result)
            return
        if op == "cancel":
            if not self.busy:return
            # Cancellation is a request; backend remains authority on final state.
            self.updated.emit(JobSnapshot(self.job_id or "", "running", messages=[error.message if error else "Cancelación solicitada; esperando confirmación."]))
            return
        self.pending = False
        if error:
            result = JobSnapshot(self.job_id or "", "error", error=error)
        elif op == "submit":
            if not isinstance(result, str) or not result:
                result = JobSnapshot("", "error", error=BackendError("PROTOCOL", "El backend no devolvió un job_id válido"))
            else:
                self.job_id = result
                self.timer.start()
                self.poll()
                return
        if not isinstance(result, JobSnapshot):
            result = JobSnapshot(self.job_id or "", "error", error=BackendError("PROTOCOL", "Estado de backend inválido"))
        if self.job_id and result.job_id != self.job_id:
            result = JobSnapshot(self.job_id, "error", error=BackendError("PROTOCOL", "job_id de respuesta no coincide"))
        if result.state in ("completed", "cancelled", "error"):
            self.busy = False
            self.timer.stop()
            self.history.append({"received_at": datetime.now(timezone.utc).isoformat(), "kind": self.kind,
                                 "scenario": self.scenario.to_dict() if self.scenario else None, "snapshot": asdict(result)})
        self.updated.emit(result)

    def shutdown(self):
        self.timer.stop()
        cleanup=getattr(self.backend,'shutdown',None)
        if cleanup:cleanup()
        self.executor.shutdown(wait=True, cancel_futures=True)
