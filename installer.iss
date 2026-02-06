#define MyAppName "APApp"
#define MyAppVersion "1.0.0"
#define MyAppExeName "APApp.exe"

[Setup]
AppId={{4BC6C5C8-2D6A-4E2E-8F3B-3B4A14A8A1C4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Your Company
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Files]
; Application files
Source: "dist\APApp\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

; Shared data files (all users) - ProgramData
Source: "output\Jednostki.csv"; DestDir: "{commonappdata}\{#MyAppName}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "output\NazwyKlienci.csv"; DestDir: "{commonappdata}\{#MyAppName}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Utwórz ikonę na pulpicie"; GroupDescription: "Skróty:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Uruchom {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard();
begin
  WizardForm.LicenseAcceptedRadio.Checked := True;
end;
