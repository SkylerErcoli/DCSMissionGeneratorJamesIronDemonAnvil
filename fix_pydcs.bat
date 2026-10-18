@echo off
rem The generator needs pydcs from GitHub. The PyPI release has the same version number (0.15.0), so pip
rem thinks it is already installed - it must be uninstalled first.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% -m pip uninstall -y pydcs
%PY% -m pip install -r requirements.txt
echo.
echo Now run doctor.bat to confirm everything is OK.
pause
