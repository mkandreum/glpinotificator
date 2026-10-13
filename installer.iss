; Script de instalador profesional Inno Setup para GLPI Notificator
#define MyAppName "GLPI Notificator"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "GLPI Notificator"
#define MyAppURL "https://github.com/mkandreum/glpinotificator"
#define MyAppExeName "GlpiNotificator.exe"

[Setup]
; Identificador unico de la aplicacion
AppId={{D37F2C5A-8E4B-4D2A-914F-83C14F2E7D9A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\GlpiNotificator
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Instalacion sin privilegios de administrador (ideal para usuarios corporativos)
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=GLPI-Notificator-Setup
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
; Cerrar automaticamente la aplicacion si esta en ejecucion antes de actualizar
CloseApplications=force
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Iniciar automaticamente al encender el ordenador"; GroupDescription: "Opciones de inicio:"

[Files]
Source: "dist\GlpiNotificator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpiar logs temporales pero no borrar config salvo que se desee
Type: files; Name: "{app}\debug.log"
Type: files; Name: "{app}\estado.json"
