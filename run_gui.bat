@echo off
rem Starts the GUI from a console so any error message stays visible.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m ironanvil gui) else (python -m ironanvil gui)
if errorlevel 1 pause
