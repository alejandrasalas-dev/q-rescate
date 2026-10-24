@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto create
.venv\Scripts\python.exe -c "import PySide6.QtWebEngineWidgets" >nul 2>nul
if not errorlevel 1 goto run
goto install
:create
where python >nul 2>nul
if errorlevel 1 (
  echo Instala Python de 64 bits, version 3.11 o posterior, y activa Add Python to PATH.
  pause
  exit /b 1
)
echo Preparando Q-Rescate. La primera ejecucion requiere Internet...
python -m venv .venv
if errorlevel 1 goto error
:install
.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
if errorlevel 1 goto error
:run
start "Q-Rescate" ".venv\Scripts\pythonw.exe" "run_desktop.py"
exit /b 0
:error
echo No se pudo preparar el entorno. Revisa la conexion y la instalacion de Python.
pause
exit /b 1
