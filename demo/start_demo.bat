@echo off
cd /d %~dp0
echo Starting Hisense HR demo at http://127.0.0.1:8765/hr_workbench.html
echo.
python -m http.server 8765
pause
