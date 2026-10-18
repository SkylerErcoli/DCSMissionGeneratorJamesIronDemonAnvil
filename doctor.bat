@echo off
rem Checks the install and prints what is wrong (send me this output if the GUI will not start).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m ironanvil doctor) else (python -m ironanvil doctor)
pause
