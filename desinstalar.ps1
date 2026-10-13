# Desinstalador amigable de GLPI Notificator
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms

$confirm = [System.Windows.Forms.MessageBox]::Show(
    "¿Estas seguro de que deseas desinstalar GLPI Notificator de este equipo?",
    "GLPI Notificator - Desinstalacion",
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Question
)
if ($confirm -ne [System.Windows.Forms.DialogResult]::Yes) {
    exit 0
}

$dest = Join-Path $env:LOCALAPPDATA 'Programs\GlpiNotificator'

Get-Process -Name GlpiNotificator -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 300

$lnks = @(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'GLPI Notificator.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\GLPI Notificator.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\GLPI Notificator.lnk')
)
foreach ($l in $lnks) { if (Test-Path -LiteralPath $l) { Remove-Item -LiteralPath $l -Force } }

if (Test-Path -LiteralPath $dest) {
    Remove-Item -LiteralPath $dest -Recurse -Force
}

[System.Windows.Forms.MessageBox]::Show(
    "GLPI Notificator ha sido desinstalado correctamente.",
    "GLPI Notificator",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null
