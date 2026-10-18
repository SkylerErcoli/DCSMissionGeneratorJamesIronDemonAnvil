; Build with Inno Setup 6.3 or newer:
; ISCC.exe /DAppVersion=1.1.0 packaging\installer.iss
; SourcePath is the directory of this script, independent of the caller's CWD.
#ifndef AppVersion
  #error AppVersion must be supplied using /DAppVersion=major.minor.patch
#endif
#define SourceRoot AddBackslash(SourcePath) + ".."

[Setup]
; Keep this ID stable so future versions update the same installation.
AppId={{2C791DDC-1A55-4FAE-BAB3-30819BF2869D}
AppName=Iron Anvil
AppVersion={#AppVersion}
AppPublisher=Iron Anvil contributors
AppSupportURL=https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/issues
AppUpdatesURL=https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/latest
DefaultDirName={localappdata}\Programs\IronAnvil
UsePreviousAppDir=yes
UsePreviousTasks=yes
DefaultGroupName=Iron Anvil
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile={#SourceRoot}\ironanvil\assets\ironanvil.ico
UninstallDisplayIcon={app}\IronAnvil.exe
UninstallDisplayName=Iron Anvil
WizardStyle=modern
DisableWelcomePage=no
Compression=lzma2
SolidCompression=yes
OutputDir={#SourceRoot}\dist
OutputBaseFilename=IronAnvil-Setup-x64
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Iron Anvil Setup
VersionInfoProductName=Iron Anvil

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
; PyInstaller's _internal directory is required. Always install the entire build.
Source: "{#SourceRoot}\dist\IronAnvil\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Iron Anvil"; Filename: "{app}\IronAnvil.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Iron Anvil"; Filename: "{app}\IronAnvil.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\IronAnvil.exe"; Description: "Launch Iron Anvil"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
