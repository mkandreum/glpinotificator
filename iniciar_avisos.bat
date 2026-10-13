@echo off
REM Lanzador de GLPI Notificator
cd /d "%~dp0"
title GLPI Notificator
python avisa_glpi.py
echo.
echo El programa se ha detenido. Pulsa una tecla para cerrar.
pause >nul
