@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto existing
if defined LISA2_PYTHON goto custompython
py -3.12 -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>&1
if not errorlevel 1 goto pylauncher
call python -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>&1
if not errorlevel 1 goto pythonlauncher
echo Lisa2 requires Python 3.12 with Tcl/Tk support.
echo Install Python 3.12 from python.org, then run Lisa2.bat again.
echo Python packages will be installed automatically in this folder's .venv.
if not defined CI pause
exit /b 1

:existing
".venv\Scripts\python.exe" "scripts\run_source.py" %*
exit /b %errorlevel%

:pylauncher
py -3.12 "scripts\run_source.py" %*
exit /b %errorlevel%

:pythonlauncher
call python "scripts\run_source.py" %*
exit /b %errorlevel%

:custompython
"%LISA2_PYTHON%" "scripts\run_source.py" %*
exit /b %errorlevel%
