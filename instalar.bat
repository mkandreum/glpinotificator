@echo off
REM Instalador de GLPI Notificator: doble clic y listo.
cd /d "%~dp0"
if exist "GLPI-Notificator-Setup.exe" (
    start "" "GLPI-Notificator-Setup.exe"
    exit /b 0
)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0instalar.ps1"
