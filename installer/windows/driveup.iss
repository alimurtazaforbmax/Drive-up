# DriveUp Windows installer (Inno Setup 6+)
# Compile with: ISCC.exe installer\windows\driveup.iss
# Or run: powershell -File scripts\build_windows.ps1 -MakeInstaller

#define MyAppName "DriveUp"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "GoogleDriveProject"
#define MyAppExeName "DriveUp.exe"
#define MyAppURL "https://github.com/"

[Setup]
AppId={{A7F3C2E1-9B4D-4F8A-9E2C-1D6B5A0F3E8C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installers
OutputBaseFilename=DriveUp-Setup-{#MyAppVersion}-Windows
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\DriveUp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
