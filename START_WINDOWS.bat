@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BARA-BLOCK 25 - Waterways, Peat, Fire
chcp 65001 >nul
set "PYTHON_CMD="
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
 python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
 if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
 echo Python 3.10 or later required. Visit https://www.python.org/downloads/
 pause
 exit /b 1
)
echo.
echo BARA-BLOCK 25 ^| Starting peat and waterways map...
%PYTHON_CMD% -c "import shapely, pyproj" >nul 2>&1
if errorlevel 1 (
 echo Installing map dependencies...
 %PYTHON_CMD% -m pip install --prefer-binary -r "%~dp0requirements-core.txt"
 if errorlevel 1 (echo Map dependencies failed & pause & exit /b 1)
)
echo Opening BARA-BLOCK in your browser...
%PYTHON_CMD% "%~dp0launch_app.py"
if errorlevel 1 pause
endlocal
