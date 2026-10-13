@echo off
REM Compila la app con PyInstaller en modo CARPETA (--onedir): arranca al instante.
cd /d "%~dp0"
if not exist icon.ico (
  echo Generando icono...
  python -m pip install --upgrade pillow
  python make_icon.py
)
echo Instalando/actualizando PyInstaller...
python -m pip install --upgrade pyinstaller
echo.
echo Compilando...
python -m PyInstaller --noconfirm --onedir --noconsole --name GlpiNotificator --icon icon.ico --add-data "icon.ico;." avisa_glpi.py
echo.
echo Listo. Ejecutable en: dist\GlpiNotificator\GlpiNotificator.exe
echo (Para un unico archivo portable cambia --onedir por --onefile; arranca mas lento.)
pause
