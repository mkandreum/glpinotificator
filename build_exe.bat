@echo off
REM Compila un ejecutable unico (dist\GlpiNotificator.exe) con PyInstaller.
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
python -m PyInstaller --noconfirm --onefile --noconsole --name GlpiNotificator --icon icon.ico --add-data "icon.ico;." avisa_glpi.py
echo.
echo Listo. El ejecutable esta en: dist\GlpiNotificator.exe
pause
