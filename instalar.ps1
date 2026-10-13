# Instalador de GLPI Notificator (se ejecuta desde instalar.bat)
$ErrorActionPreference = 'Stop'

$src  = Split-Path -Parent $MyInvocation.MyCommand.Path
$exeSrc = Join-Path $src 'GlpiNotificator.exe'
$dest = Join-Path $env:LOCALAPPDATA 'Programs\GlpiNotificator'
$exeDest = Join-Path $dest 'GlpiNotificator.exe'

Write-Host "============================================"
Write-Host "  GLPI Notificator - Instalacion automatica"
Write-Host "============================================"
Write-Host ""

if (-not (Test-Path -LiteralPath $exeSrc)) {
    Write-Host "[ERROR] No encuentro GlpiNotificator.exe junto a este instalador."
    Write-Host "        Descomprime TODA la carpeta del ZIP y vuelve a ejecutar instalar.bat."
    Read-Host "Pulsa Enter para salir"
    exit 1
}

try { Get-Process -Name GlpiNotificator -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}

Write-Host "Instalando en: $dest"
if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -Path (Join-Path $src '*') -Destination $dest -Recurse -Force

$ws = New-Object -ComObject WScript.Shell

function Nuevo-Acceso($rutaLnk) {
    $lnk = $ws.CreateShortcut($rutaLnk)
    $lnk.TargetPath = $exeDest
    $lnk.WorkingDirectory = $dest
    $lnk.IconLocation = "$exeDest,0"
    $lnk.Description = 'GLPI Notificator'
    $lnk.Save()
}

$escritorio = [Environment]::GetFolderPath('Desktop')
Nuevo-Acceso (Join-Path $escritorio 'GLPI Notificator.lnk')
$menuInicio = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
Nuevo-Acceso (Join-Path $menuInicio 'GLPI Notificator.lnk')
Write-Host "Accesos directos creados (Escritorio y Menu Inicio)."

$resp = Read-Host "Quieres que se inicie solo al encender el PC? (S/N)"
if ($resp -match '^[SsYy]') {
    $inicio = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
    Nuevo-Acceso (Join-Path $inicio 'GLPI Notificator.lnk')
    Write-Host "Inicio automatico ACTIVADO."
} else {
    $inicio = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
    $lnkAuto = Join-Path $inicio 'GLPI Notificator.lnk'
    if (Test-Path -LiteralPath $lnkAuto) { Remove-Item -LiteralPath $lnkAuto -Force }
    Write-Host "Inicio automatico desactivado."
}

Write-Host ""
Write-Host "Instalado. Iniciando GLPI Notificator..."
Start-Process -FilePath $exeDest
Write-Host ""
Write-Host "Listo. La primera vez te pedira tu URL de GLPI, usuario y contrasena."
Write-Host "Ya puedes cerrar esta ventana (o pulsa Enter)."
Read-Host
