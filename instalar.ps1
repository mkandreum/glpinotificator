# Instalador amigable de GLPI Notificator
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$setupExe = Join-Path $src 'GLPI-Notificator-Setup.exe'
if (Test-Path -LiteralPath $setupExe) {
    Start-Process -FilePath $setupExe
    exit 0
}

$exeSrc = Join-Path $src 'GlpiNotificator.exe'
$dest = Join-Path $env:LOCALAPPDATA 'Programs\GlpiNotificator'
$exeDest = Join-Path $dest 'GlpiNotificator.exe'

if (-not (Test-Path -LiteralPath $exeSrc)) {
    [System.Windows.Forms.MessageBox]::Show(
        "No se encontro 'GlpiNotificator.exe' en esta carpeta.`nPor favor, descomprime todo el contenido antes de instalar.",
        "GLPI Notificator - Error",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

# Cerrar versiones previas si estan abiertas
try {
    Get-Process -Name GlpiNotificator -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
} catch {}

# Copiar archivos sin borrar configuraciones o credenciales existentes
try {
    if (-not (Test-Path -LiteralPath $dest)) {
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
    }
    Copy-Item -Path (Join-Path $src '*') -Destination $dest -Recurse -Force
} catch {
    [System.Windows.Forms.MessageBox]::Show(
        "No se pudieron copiar los archivos a:`n$dest`n`nDetalle: $_",
        "GLPI Notificator - Error",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

# Crear accesos directos
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

$inicio = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
Nuevo-Acceso (Join-Path $inicio 'GLPI Notificator.lnk')

# Iniciar la aplicacion inmediatamente
Start-Process -FilePath $exeDest -WorkingDirectory $dest

[System.Windows.Forms.MessageBox]::Show(
    "GLPI Notificator se ha instalado correctamente.`n`n- Acceso directo creado en el Escritorio.`n- Inicio automatico con Windows activado.`n- La aplicacion ya esta ejecutandose en segundo plano.",
    "GLPI Notificator",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null
