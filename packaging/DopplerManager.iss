#define MyAppName "Doppler Manager"
#define MyAppInstallDirName "DopplerManager"
#define MyAppPublisher "Doppler Manager"
#define MyAppExeName "DopplerManager.exe"
#define MyAppVersion GetEnv("DM_VERSION")
#define MyAppIcon "..\packaging\DopplerManager.ico"

#if MyAppVersion == ""
  #define MyAppVersion "0.4.0"
#endif

[Setup]
AppId={{9E92E34C-995E-42D1-9DF8-84B6842DF9CF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppInstallDirName}\{#MyAppVersion}
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
UsePreviousAppDir=no
OutputDir=..\dist\installer
OutputBaseFilename=DopplerManager-{#MyAppVersion}-setup
SetupIconFile={#MyAppIcon}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\build\installer-payload\DopplerManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{autodesktop}\Doppler Manager Scan.lnk"
Type: files; Name: "{autoprograms}\Doppler Manager Scan *.lnk"
Type: files; Name: "{autoprograms}\Doppler Manager Scan {#MyAppVersion}.lnk"
Type: files; Name: "{autoprograms}\Stop Doppler Manager Scan.lnk"
Type: files; Name: "{autoprograms}\Doppler Manager Scan diagnostic log.lnk"

[Icons]
Name: "{autoprograms}\{#MyAppName} {#MyAppVersion}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Stop {#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--stop"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName} diagnostic log"; Filename: "{sys}\notepad.exe"; Parameters: """{localappdata}\DopplerManager\logs\DopplerManager.log"""
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM DopplerManager.exe /T /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
