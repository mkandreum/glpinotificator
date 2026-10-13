# Desinstalador de GLPI Notificator (se ejecuta desde desinstalar.bat)
$ErrorActionPreference = 'SilentlyContinue'

$dest = Join-Path $env:LOCALAPPDATA 'Programs\GlpiNotificator'

Write-Host "Cerrando GLPI Notificator..."
Get-Process -Name GlpiNotificator -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Eliminando accesos directos..."
$lnks = @(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'GLPI Notificator.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\GLPI Notificator.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\GLPI Notificator.lnk')
)
foreach ($l in $lnks) { if (Test-Path -LiteralPath $l) { Remove-Item -LiteralPath $l -Force } }

Write-Host "Eliminando archivos..."
if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }

Write-Host ""
Write-Host "GLPI Notificator desinstalado."
Read-Host "Pulsa Enter para salir"
