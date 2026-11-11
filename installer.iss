; Script Inno Setup per PC Cleaner
; Compilare con build_installer.bat (crea dist\PCCleaner e dist_x86\PCCleaner con PyInstaller)

#define AppName "PC Cleaner"
#define AppVersion "1.2.2"
#define AppExe "PCCleaner.exe"

; Installer UNICO: contiene dist\PCCleaner (64 bit) e dist_x86\PCCleaner (32 bit)
; e all'installazione sceglie quella giusta (Is64BitInstallMode).
#define OutName "PCCleaner-Setup-" + AppVersion

[Setup]
AppId={{24d674f5-6171-4a62-a544-f82cb9558c62}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Cesa028
AppCopyright=Copyright (c) 2026 Cesa028 - Licenza MIT
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=installer\license-page.txt
OutputDir=installer
OutputBaseFilename={#OutName}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; nessun ArchitecturesAllowed: parte anche su Windows a 32 bit
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; installa per tutti (amministratore) oppure solo per l'utente corrente, a scelta
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\PCCleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: Is64BitInstallMode
Source: "dist_x86\PCCleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: not Is64BitInstallMode
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Licenza"; Filename: "{app}\LICENSE.txt"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}"
