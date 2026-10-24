"""
Tarea 7: ejecuta el motor en un PROCESO separado (multiprocessing, spawn).

Motivo: Qiskit dio segfault dentro de hilos de la interfaz; un proceso aparte
aísla el fallo, permite cancelar y no congela la ventana.

Uso desde PySide6 (sin bloquear):

    from engine.ejecutor import Calculo
    self.calculo = Calculo(solicitud_dict)        # arranca solo
    self.timer = QTimer(self); self.timer.timeout.connect(self.revisar); self.timer.start(200)

    def revisar(self):
        res = self.calculo.consultar()            # None mientras calcula
        self.etiqueta.setText(self.calculo.etapa) # "Calculando… / Ejecutando método qaoa…"
        if res is not None:
            self.timer.stop(); self.dibujar(res)  # dict con el formato de Resultado

    # botón Cancelar:
    self.calculo.cancelar()

En el main de la app (obligatorio en Windows y con PyInstaller):

    if __name__ == "__main__":
        import multiprocessing; multiprocessing.freeze_support()
"""
from __future__ import annotations

import multiprocessing as mp
import queue
import time
from typing import Optional

from engine.contrato import Resultado


def _trabajador(solicitud: dict, opciones: dict, cola) -> None:
    """Corre en el proceso hijo. Envía ('etapa', texto) y al final ('fin', dict)."""
    try:
        from engine.motor import calcular_recorridos
        res = calcular_recorridos(solicitud, progreso=lambda m: cola.put(("etapa", m)), **opciones)
        cola.put(("fin", res.a_dict()))
    except BaseException as e:  # noqa: BLE001 — cualquier fallo vuelve como mensaje legible
        cola.put(("fin", Resultado(estado="error", mensaje=f"{type(e).__name__}: {e}").a_dict()))


class Calculo:
    """Un cálculo en curso. No bloquea: consulte con `consultar()`."""

    def __init__(self, solicitud: dict, timeout_s: Optional[float] = None,
                 iniciar: bool = True, **opciones):
        self.solicitud = solicitud
        self.timeout_s = float(timeout_s if timeout_s is not None else solicitud.get("timeout_s", 180))
        self.opciones = opciones          # p. ej. fuente="sintetica"
        self.etapa = "En espera"
        self._ctx = mp.get_context("spawn")
        self._cola = self._ctx.Queue()
        self._proc: Optional[mp.Process] = None
        self._inicio = 0.0
        self._resultado: Optional[dict] = None
        if iniciar:
            self.iniciar()

    def iniciar(self) -> None:
        self._proc = self._ctx.Process(target=_trabajador,
                                       args=(self.solicitud, self.opciones, self._cola), daemon=True)
        self._inicio = time.monotonic()
        self.etapa = "Calculando…"
        self._proc.start()

    @property
    def transcurrido_s(self) -> float:
        return time.monotonic() - self._inicio if self._inicio else 0.0

    def _terminar(self, estado: str, mensaje: str) -> dict:
        if self._proc is not None and self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(2)
            if self._proc.is_alive():
                self._proc.kill()
        self.etapa = mensaje
        self._resultado = Resultado(estado=estado, mensaje=mensaje).a_dict()
        return self._resultado

    def consultar(self) -> Optional[dict]:
        """None mientras calcula; dict (formato Resultado) cuando termina."""
        if self._resultado is not None:
            return self._resultado
        while True:
            try:
                tipo, dato = self._cola.get_nowait()
            except queue.Empty:
                break
            if tipo == "etapa":
                self.etapa = dato
            elif tipo == "fin":
                self._resultado = dato
                self.etapa = dato.get("mensaje", "Terminado")
                if self._proc is not None:
                    self._proc.join(2)
                return dato
        if self._proc is not None and not self._proc.is_alive():
            # Murió sin mensaje final (p. ej. segfault de Qiskit)
            return self._terminar("error", f"El proceso de cálculo terminó inesperadamente "
                                           f"(código {self._proc.exitcode}).")
        if self.transcurrido_s > self.timeout_s:
            return self._terminar("tiempo_agotado",
                                  f"Se superó el tiempo límite de {self.timeout_s:.0f} s.")
        return None

    def cancelar(self) -> dict:
        if self._resultado is not None:
            return self._resultado
        return self._terminar("cancelado", "Cálculo cancelado por el usuario.")

    def esperar(self, intervalo_s: float = 0.1) -> dict:
        """Versión bloqueante (scripts y tests; no usar en la interfaz)."""
        while (res := self.consultar()) is None:
            time.sleep(intervalo_s)
        return res


def ejecutar(solicitud: dict, timeout_s: Optional[float] = None, **opciones) -> dict:
    """Atajo bloqueante: calcula en un proceso aparte y devuelve el dict."""
    return Calculo(solicitud, timeout_s=timeout_s, **opciones).esperar()
