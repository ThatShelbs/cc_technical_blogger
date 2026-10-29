; Inno Setup script: turns packaging\dist\Proseferno into a per-user Windows installer (no admin rights needed).
; packaging\build_windows.bat runs it when Inno Setup 6 is installed (winget install JRSoftware.InnoSetup).

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6F1E0B7A-3C5D-4E2B-9A8F-5E1D0C2B7A41}
AppName=Proseferno
AppVersion={#AppVersion}
AppPublisher=Proseferno contributors
AppPublisherURL=https://github.com/ThatShelbs/cc_technical_blogger
DefaultDirName={localappdata}\Programs\Proseferno
DefaultGroupName=Proseferno
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=Proseferno-Setup-{#AppVersion}
SetupIconFile=..\frontend\public\favicon.ico
UninstallDisplayIcon={app}\Proseferno.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\Proseferno\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Proseferno"; Filename: "{app}\Proseferno.exe"
Name: "{group}\Proseferno (demo mode)"; Filename: "{app}\Proseferno.exe"; Parameters: "--demo"
Name: "{group}\Uninstall Proseferno"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Proseferno"; Filename: "{app}\Proseferno.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Proseferno.exe"; Description: "Start Proseferno"; Flags: nowait postinstall skipifsilent

; User data (%LOCALAPPDATA%\Proseferno) is kept on uninstall, so reinstalling keeps your personas and posts.
