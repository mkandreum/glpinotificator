@echo off
REM Compila la app y genera el instalador oficial y el paquete ZIP
cd /d "%~dp0"

if not exist icon.ico (
  echo Generando icono...
  python -m pip install --upgrade pillow
  python make_icon.py
)

echo Instalando/actualizando PyInstaller...
python -m pip install --upgrade pyinstaller
echo.
echo Compilando aplicacion con PyInstaller...
python -m PyInstaller --noconfirm --onedir --noconsole --name GlpiNotificator --icon icon.ico --add-data "icon.ico;." avisa_glpi.py
if errorlevel 1 ( echo ERROR al compilar con PyInstaller & pause & exit /b 1 )

echo.
echo Buscando compilador Inno Setup...
set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    where iscc >nul 2>&1 && set "ISCC=iscc"
)

if defined ISCC (
    echo Compilando instalador Setup unico con Inno Setup...
    "%ISCC%" installer.iss
    if errorlevel 1 (
        echo Advertencia: No se pudo generar el Setup.exe
    ) else (
        echo Instalador generado con exito: dist\GLPI-Notificator-Setup.exe
    )
) else (
    echo AVISO: Inno Setup 6 no encontrado. Puedes instalarlo con: winget install JRSoftware.InnoSetup
)

echo.
echo Empaquetando ZIP de distribucion (portable)...
if exist build\release rmdir /s /q build\release
mkdir build\release
xcopy /E /I /Y "dist\GlpiNotificator\*" "build\release\" >nul
if exist "dist\GLPI-Notificator-Setup.exe" copy /Y "dist\GLPI-Notificator-Setup.exe" build\release\ >nul
copy /Y instalar.bat    build\release\ >nul
copy /Y instalar.ps1    build\release\ >nul
copy /Y desinstalar.bat build\release\ >nul
copy /Y desinstalar.ps1 build\release\ >nul
copy /Y LEEME.txt       build\release\ >nul
if exist dist\GLPI-Notificator.zip del /q dist\GLPI-Notificator.zip
powershell -NoProfile -Command "Compress-Archive -Path 'build\release\*' -DestinationPath 'dist\GLPI-Notificator.zip'"

echo.
echo ==============================================================
echo  Listo para publicar!
if exist dist\GLPI-Notificator-Setup.exe echo  - Instalador ejecutable: dist\GLPI-Notificator-Setup.exe
echo  - Paquete ZIP:           dist\GLPI-Notificator.zip
echo ==============================================================
pause
