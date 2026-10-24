@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where python >nul 2>nul
if errorlevel 1 (
  echo Instala Python 3.13 de 64 bits y activa Add Python to PATH.
  pause
  exit /b 1
)
python -m venv .venv
if errorlevel 1 goto error
:install
.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
if errorlevel 1 goto error
start "Q-Rescate" ".venv\Scripts\pythonw.exe" "run_qrescate.py" %*
exit /b 0
:error
echo Instalacion incompleta. Revisa Internet y las dependencias. No se usara red sintetica.
pause
exit /b 1
