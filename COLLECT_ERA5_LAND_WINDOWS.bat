@echo off
cd /d "%~dp0"
set "PY=py -3"
py -3 --version >nul 2>&1
if errorlevel 1 set "PY=python"
%PY% -m pip install -r requirements-data.txt
%PY% era5_land.py --date 2024-01-01
if errorlevel 1 (echo ERA5-Land requires your CDS API access & pause & exit /b 1)
%PY% export_structured.py
pause
