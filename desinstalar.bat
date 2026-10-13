@echo off
REM Desinstalador de GLPI Notificator
cd /d "%~dp0"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0desinstalar.ps1"
