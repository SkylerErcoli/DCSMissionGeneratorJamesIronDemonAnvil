; Build with Inno Setup 6.3 or newer:
; ISCC.exe /DAppVersion=1.4.3 packaging\installer.iss
; SourcePath is the directory of this script, independent of the caller's CWD.
#ifndef AppVersion
  #error AppVersion must be supplied using /DAppVersion=major.minor.patch
#endif
#define SourceRoot AddBackslash(SourcePath) + ".."

[Setup]
; Keep this ID stable so future versions update the same installation.
AppId={{F698B14E-6D10-4A68-BB62-A75C5DCC04F2}
AppName=Iron Anvil Experimental
AppVersion={#AppVersion}
AppPublisher=Iron Anvil contributors
AppSupportURL=https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/issues
AppUpdatesURL=https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.4.3-experimental.9
DefaultDirName={localappdata}\Programs\IronAnvilExperimental
UsePreviousAppDir=yes
UsePreviousTasks=yes
DefaultGroupName=Iron Anvil Experimental
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile={#SourceRoot}\ironanvil\assets\ironanvil.ico
UninstallDisplayIcon={app}\IronAnvil.exe
UninstallDisplayName=Iron Anvil Experimental
WizardStyle=modern
DisableWelcomePage=no
Compression=lzma2
SolidCompression=yes
OutputDir={#SourceRoot}\dist
OutputBaseFilename=IronAnvil-Experimental-Setup-x64
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Iron Anvil Experimental Setup
VersionInfoProductName=Iron Anvil Experimental

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
; PyInstaller's _internal directory is required. Always install the entire build.
Source: "{#SourceRoot}\dist\IronAnvil\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Iron Anvil Experimental"; Filename: "{app}\IronAnvil.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Iron Anvil Experimental"; Filename: "{app}\IronAnvil.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\IronAnvil.exe"; Description: "Launch Iron Anvil Experimental"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
