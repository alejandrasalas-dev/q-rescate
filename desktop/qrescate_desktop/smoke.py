"""Opt-in executable verification: real Qt/WebEngine and a spawned engine job."""
import json
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .local_backend import from_example

def install_smoke(window,path,synthetic,startup_error=None):
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    timer=QTimer(window);timer.setInterval(200);start=time.monotonic();started=False
    def finish(error=None):
        timer.stop()
        raw={'map_ready':window.map_ready,'backend_connected':window.caps.connected,
             'source_requested':'sintetica' if synthetic else 'osm','state':window.job_state,
             'startup_error':startup_error,'error':error,'history':window.controller.history}
        target.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
        window.grab().save(str(target.with_suffix('.png')))
        window.dirty=False;window.controller.busy=False;window.controller.shutdown();window.close();QApplication.instance().quit()
    def tick():
        nonlocal started
        if startup_error:finish(startup_error);return
        if time.monotonic()-start>150:finish('Smoke test deadline');return
        if not started and window.map_ready and window.caps.connected:
            scenario=from_example();scenario.config.methods=['exact','greedy'];scenario.config.timeout_seconds=120
            window.replace(scenario);window.calculate_job();started=True
        elif started and window.job_state in ('completed','cancelled','error') and not window.controller.busy:finish()
    timer.timeout.connect(tick);timer.start();window._smoke_timer=timer
