; Script Inno Setup per PC Cleaner
; Compilare con build_installer.bat (prima crea dist\PCCleaner\ con PyInstaller)

#define AppName "PC Cleaner"
#define AppVersion "1.2.0"
#define AppExe "PCCleaner.exe"

; Versione a 32 bit: ISCC /DX86=1 installer.iss (sorgente dist_x86\PCCleaner)
#ifdef X86
  #define DistDir "dist_x86"
  #define OutName "PCCleaner-Setup-" + AppVersion + "-32bit"
#else
  #define DistDir "dist"
  #define OutName "PCCleaner-Setup-" + AppVersion
#endif

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
#ifndef X86
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif
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
Source: "{#DistDir}\PCCleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
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
Type: filesandordirs; Name: "{app}"
