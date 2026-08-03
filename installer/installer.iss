; Inno Setup script for the AI Content Library desktop installer.
; See docs/features/14-desktop-packaging.md for the full packaging design.
;
; Build with:  ISCC installer.iss
; (requires the PyInstaller onedir output to already exist at
; ..\backend\dist\AIContentLibrary\ -- build_installer.ps1 does the frontend
; build + PyInstaller build first, then calls this.)

#define MyAppName "AI Content Library"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AI Content Library"
#define MyAppExeName "AIContentLibrary.exe"
#define SourceDir "..\backend\dist\AIContentLibrary"

[Setup]
AppId={{7C5E7E7A-6E1B-4B7A-9C7D-1B2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; No admin prompt: installs into the current user's own folder, not
; Program Files -- the user's explicit choice (see project plan).
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=AIContentLibrarySetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
; App's own data lives under %LOCALAPPDATA%\AIContentLibrary (see
; app/core/config.py), a different folder from the install location above --
; uninstalling removes only the installed program, never the user's videos/
; database, matching normal Windows app conventions.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
