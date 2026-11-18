@echo off
setlocal
cd /d "%~dp0"
set "PY=py -3"
py -3 --version >nul 2>&1
if errorlevel 1 set "PY=python"
%PY% -m pip install -r requirements-data.txt
if errorlevel 1 (echo Data dependencies unavailable & pause & exit /b 1)
%PY% COLLECT_ALL_DATA_ONCE.py
%PY% era5_open_meteo.py --date 2024-01-01
if errorlevel 1 echo ERA5-Land pending: Open-Meteo archive unavailable; official CDS alternative is available.
%PY% export_structured.py
pause
endlocal
