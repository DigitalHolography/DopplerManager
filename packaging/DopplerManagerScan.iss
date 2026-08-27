#define MyAppName "Doppler Manager Scan"
#define MyAppInstallDirName "DopplerManager"
#define MyAppPublisher "Doppler Manager"
#define MyAppExeName "DopplerManagerScan.exe"
#define MyAppVersion GetEnv("DM_VERSION")

#if MyAppVersion == ""
  #define MyAppVersion "1.7.0"
#endif

[Setup]
AppId={{9E92E34C-995E-42D1-9DF8-84B6842DF9CF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppInstallDirName}\{#MyAppVersion}
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
UsePreviousAppDir=no
OutputDir=..\dist\installer
OutputBaseFilename=DopplerManager-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\DopplerManagerScan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName} {#MyAppVersion}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\Stop {#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--stop"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppName} diagnostic log"; Filename: "{sys}\notepad.exe"; Parameters: """{localappdata}\DopplerManager\logs\DopplerManagerScan.log"""
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM DopplerManagerScan.exe /T /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
