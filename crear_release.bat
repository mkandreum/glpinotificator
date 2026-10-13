@echo off
REM Compila la app y genera el ZIP de distribucion (listo para publicar).
cd /d "%~dp0"
if not exist icon.ico (
  echo Generando icono...
  python -m pip install --upgrade pillow
  python make_icon.py
)
echo Instalando/actualizando PyInstaller...
python -m pip install --upgrade pyinstaller
echo.
echo Compilando (modo carpeta)...
python -m PyInstaller --noconfirm --onedir --noconsole --name GlpiNotificator --icon icon.ico --add-data "icon.ico;." avisa_glpi.py
if errorlevel 1 ( echo ERROR al compilar & pause & exit /b 1 )

echo.
echo Empaquetando ZIP de distribucion...
if exist build\release rmdir /s /q build\release
mkdir build\release
xcopy /E /I /Y "dist\GlpiNotificator\*" "build\release\" >nul
copy /Y instalar.bat    build\release\ >nul
copy /Y instalar.ps1    build\release\ >nul
copy /Y desinstalar.bat build\release\ >nul
copy /Y desinstalar.ps1 build\release\ >nul
copy /Y LEEME.txt       build\release\ >nul
if exist dist\GLPI-Notificator.zip del /q dist\GLPI-Notificator.zip
powershell -NoProfile -Command "Compress-Archive -Path 'build\release\*' -DestinationPath 'dist\GLPI-Notificator.zip'"

echo.
echo Listo. ZIP para distribuir: dist\GLPI-Notificator.zip
pause
