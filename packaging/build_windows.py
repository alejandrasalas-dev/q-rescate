"""Run with the same interpreter used for the validated Windows environment."""
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
             '--name','Q-Rescate','--paths',str(root/'desktop'),
             '--add-data',f'{root / "desktop/qrescate_desktop/assets"};qrescate_desktop/assets',
             '--hidden-import','engine.ejecutor','--hidden-import','engine.motor','--hidden-import','engine.cobertura',
             '--hidden-import','routing','--hidden-import','osmnx','--hidden-import','pyproj',
             '--copy-metadata','osmnx','--copy-metadata','qiskit','--copy-metadata','qiskit-algorithms','--copy-metadata','qiskit-optimization',
             '--collect-all','qiskit','--collect-all','qiskit_algorithms','--collect-all','qiskit_optimization',
             '--exclude-module','pytest','--exclude-module','IPython',str(root/'run_qrescate.py')]
    subprocess.run(command,cwd=root,check=True)
