; Inno Setup script: turns packaging\dist\Inferno Ghostwriter into a per-user Windows installer (no admin rights needed).
; packaging\build_windows.bat runs it when Inno Setup 6 is installed (winget install JRSoftware.InnoSetup).

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6F1E0B7A-3C5D-4E2B-9A8F-5E1D0C2B7A41}
AppName=Inferno Ghostwriter
AppVersion={#AppVersion}
AppPublisher=Inferno Ghostwriter contributors
AppPublisherURL=https://github.com/ThatShelbs/inferno-ghostwriter
DefaultDirName={localappdata}\Programs\Inferno Ghostwriter
DefaultGroupName=Inferno Ghostwriter
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=InfernoGhostwriter-Setup-{#AppVersion}
SetupIconFile=..\frontend\public\favicon.ico
UninstallDisplayIcon={app}\InfernoGhostwriter.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\Inferno Ghostwriter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Inferno Ghostwriter"; Filename: "{app}\InfernoGhostwriter.exe"
Name: "{group}\Inferno Ghostwriter (demo mode)"; Filename: "{app}\InfernoGhostwriter.exe"; Parameters: "--demo"
Name: "{group}\Uninstall Inferno Ghostwriter"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Inferno Ghostwriter"; Filename: "{app}\InfernoGhostwriter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\InfernoGhostwriter.exe"; Description: "Start Inferno Ghostwriter"; Flags: nowait postinstall skipifsilent

; User data (%LOCALAPPDATA%\Inferno Ghostwriter) is kept on uninstall, so reinstalling keeps your personas and posts.
