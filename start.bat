@echo off
setlocal
cd /d "%~dp0"

rem Prefer the Python launcher, then fall back to python on PATH.
where py >nul 2>&1
if not errorlevel 1 set "APP_PY=py -3"
if not defined APP_PY (
    where python >nul 2>&1
    if not errorlevel 1 set "APP_PY=python"
)

if not defined APP_PY goto install_python
%APP_PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    if "%APP_PY%"=="py -3" goto check_python_command
    goto install_python
)
goto install_dependencies

:check_python_command
where python >nul 2>&1
if errorlevel 1 goto install_python
set "APP_PY=python"
%APP_PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto install_python
goto install_dependencies

:install_python
where winget >nul 2>&1
if errorlevel 1 goto python_help
echo Python 3.10 or newer was not found. Installing Python 3.12 for your Windows user account...
winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto python_help
set "APP_PY=py -3.12"
%APP_PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto python_help

:install_dependencies
if not exist requirements.txt goto run_app
%APP_PY% -m pip --version >nul 2>&1
if errorlevel 1 %APP_PY% -m ensurepip --upgrade
if errorlevel 1 goto dependency_error
%APP_PY% -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto dependency_error

:run_app
echo Starting Indaane Cylinder Store...
%APP_PY% app.py
if errorlevel 1 echo The application stopped with an error.
goto finish

:python_help
echo Python 3.10 or newer could not be installed or started.
echo Install Python 3.10 or newer from https://www.python.org/downloads/ and run this file again.
goto finish

:dependency_error
echo Could not install the packages listed in requirements.txt.
echo Check your internet connection and Python pip installation, then run start.bat again.

:finish
echo.
pause
endlocal
