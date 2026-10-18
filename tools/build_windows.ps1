[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipInstall
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($env:OS -ne "Windows_NT") {
    throw "Build on 64-bit Windows. PyInstaller cannot cross-compile a Windows program from Linux."
}
$Repository = Split-Path -Parent $PSScriptRoot
Push-Location $Repository
try {
    & $Python -c "import struct, sys; assert sys.version_info[:2] == (3, 12), 'Use Python 3.12'; assert struct.calcsize('P') == 8, 'Use 64-bit Python'"
    if ($LASTEXITCODE -ne 0) { throw "A 64-bit CPython 3.12 build environment is required." }
    if (-not $SkipInstall) {
        & $Python -m pip install --disable-pip-version-check -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    }
    & $Python -m PyInstaller --noconfirm --clean packaging/ironanvil.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    $ApplicationFolder = Join-Path $Repository "dist/IronAnvil"
    $Executable = Join-Path $ApplicationFolder "IronAnvil.exe"
    if (-not (Test-Path $Executable)) { throw "The Windows application was not created." }
    Copy-Item "docs/START-HERE.txt" (Join-Path $ApplicationFolder "START HERE.txt")
    # Do not put developer instructions or package installation commands in the ZIP.
    New-Item -ItemType Directory -Force "test-results" | Out-Null
    # Test outside the source tree with PATH/PYTHONPATH emptied. The program must
    # use its own Python/Tcl/PROJ/DLLs and must not find the checkout by accident.
    $OldPath = $env:PATH
    $OldPythonPath = $env:PYTHONPATH
    $OldPythonHome = $env:PYTHONHOME
    $ProbeDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("IronAnvil-clean-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory $ProbeDirectory | Out-Null
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $env:PYTHONPATH = ""
        $env:PYTHONHOME = ""
        foreach ($Mode in @("self-test", "smoke-gui")) {
            $Report = Join-Path $Repository ("test-results/frozen-" + $Mode + ".json")
            Remove-Item $Report -ErrorAction SilentlyContinue
            $ArgumentString = '--' + $Mode + ' --self-test-output "' + $Report + '"'
            $Process = Start-Process -FilePath $Executable -ArgumentList $ArgumentString -WorkingDirectory $ProbeDirectory -PassThru
            if (-not $Process.WaitForExit(240000)) {
                $Process.Kill()
                throw "Frozen $Mode timed out after four minutes."
            }
            $Process.Refresh()
            if ($Process.ExitCode -ne 0 -or -not (Test-Path $Report)) {
                if (Test-Path $Report) { Get-Content $Report }
                throw "Frozen $Mode failed (exit $($Process.ExitCode))."
            }
            $Results = Get-Content $Report -Raw | ConvertFrom-Json
            if (-not $Results.ok -or -not $Results.frozen -or $Results.platform -ne "win32") {
                Get-Content $Report
                throw "Frozen $Mode did not pass as a Windows executable."
            }
            if ($Mode -eq "self-test" -and $Results.mission_count -ne 43) {
                throw "The frozen mission matrix is incomplete."
            }
            if ($Mode -eq "smoke-gui" -and ($Results.maps.Count -ne 6 -or -not $Results.preferences_reloaded)) {
                throw "The frozen desktop/theme/preferences checks are incomplete."
            }
            Write-Host "PASS: frozen $Mode"
        }
    }
    finally {
        $env:PATH = $OldPath
        $env:PYTHONPATH = $OldPythonPath
        $env:PYTHONHOME = $OldPythonHome
        Remove-Item -Recurse -Force $ProbeDirectory
    }
    # Zip the entire application, including _internal. An exe by itself will not run.
    $Archive = Join-Path $Repository "dist/IronAnvil-Windows-x64.zip"
    Remove-Item $Archive -ErrorAction SilentlyContinue
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($ApplicationFolder, $Archive)
    # Compile a per-user installer from the same verified portable payload.
    $Compiler = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6/ISCC.exe"
    if (-not (Test-Path $Compiler)) {
        $Compiler = (Get-Command "ISCC.exe" -ErrorAction Stop).Source
    }
    $Version = (& $Python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])').Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not read the application version." }
    & $Compiler "/DAppVersion=$Version" "packaging/installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "Windows installer compilation failed." }
    $Installer = Join-Path $Repository "dist/IronAnvil-Setup-x64.exe"
    if (-not (Test-Path $Installer)) { throw "The Windows installer was not created." }
    # Upgrade an actual published 1.1 installation. The new installer deliberately
    # receives NO /DIR: Inno must discover the previous custom directory itself.
    # Do not run this destructive integration test over a developer's own app.
    $UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{2C791DDC-1A55-4FAE-BAB3-30819BF2869D}_is1"
    if (Test-Path $UninstallKey) { throw "An existing Iron Anvil installation is present. Run installer validation in a clean Windows account." }
    $UpgradeDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("IronAnvil-upgrade-" + [guid]::NewGuid().ToString("N"))
    $InstallDirectory = Join-Path $UpgradeDirectory "Custom Program Folder With Spaces"
    $UserMissionsDirectory = Join-Path $UpgradeDirectory "Existing User Missions"
    $Preferences = Join-Path $env:LOCALAPPDATA "IronAnvil/preferences.json"
    $HadPreferences = Test-Path $Preferences
    $PreferencesBackup = if ($HadPreferences) { [System.IO.File]::ReadAllBytes($Preferences) } else { $null }
    New-Item -ItemType Directory -Force $UpgradeDirectory, $UserMissionsDirectory | Out-Null
    $Uninstalled = $false
    try {
        $OldInstaller = Join-Path $UpgradeDirectory "IronAnvil-Setup-1.1.0-x64.exe"
        $OldChecksums = Join-Path $UpgradeDirectory "SHA256SUMS-1.1.0.txt"
        $OldRelease = "https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/download/v1.1.0"
        Invoke-WebRequest -Uri "$OldRelease/SHA256SUMS.txt" -OutFile $OldChecksums
        Invoke-WebRequest -Uri "$OldRelease/IronAnvil-Setup-x64.exe" -OutFile $OldInstaller
        $ChecksumLine = @(Get-Content $OldChecksums | Where-Object { $_ -match '^[a-fA-F0-9]{64}\s+IronAnvil-Setup-x64\.exe$' })
        if ($ChecksumLine.Count -ne 1) { throw "The published 1.1.0 installer checksum is missing or ambiguous." }
        $OldExpectedHash = ($ChecksumLine[0] -split '\s+')[0].ToLowerInvariant()
        $OldActualHash = (Get-FileHash $OldInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($OldActualHash -ne $OldExpectedHash) { throw "The published 1.1.0 installer failed SHA-256 verification." }
        $OldArguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $InstallDirectory + '"'
        $OldProcess = Start-Process -FilePath $OldInstaller -ArgumentList $OldArguments -PassThru
        if (-not $OldProcess.WaitForExit(120000)) { $OldProcess.Kill(); throw "Previous-version installer timed out." }
        $OldProcess.Refresh()
        if ($OldProcess.ExitCode -ne 0) { throw "Previous-version installer failed (exit $($OldProcess.ExitCode))." }
        $InstalledExecutable = Join-Path $InstallDirectory "IronAnvil.exe"
        if (-not (Test-Path $InstalledExecutable)) { throw "Previous-version installed application is missing." }
        $OldInstalledVersion = (Get-Item $InstalledExecutable).VersionInfo.FileVersion
        if ([version]$OldInstalledVersion -ne [version]"1.1.0.0") { throw "The upgrade baseline is not the published 1.1.0 application." }
        New-Item -ItemType Directory -Force (Split-Path -Parent $Preferences) | Out-Null
        $SampleMission = Join-Path $UserMissionsDirectory "My existing mission.miz"
        & $Python -m ironanvil generate --map caucasus --seed 42 --output $SampleMission
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $SampleMission)) { throw "Could not prepare a real user mission for the upgrade check." }
        @{ theme = "dark"; mission = @{ output = $UserMissionsDirectory; departure = "Damascus" }; user_note = "retain my preferences" } |
            ConvertTo-Json -Depth 4 | Set-Content $Preferences -Encoding utf8
        $PreferencesBefore = (Get-FileHash $Preferences -Algorithm SHA256).Hash
        $MissionBefore = (Get-FileHash $SampleMission -Algorithm SHA256).Hash
        $InstallArguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'
        $InstallProcess = Start-Process -FilePath $Installer -ArgumentList $InstallArguments -PassThru
        if (-not $InstallProcess.WaitForExit(120000)) { $InstallProcess.Kill(); throw "Upgrade installer timed out." }
        $InstallProcess.Refresh()
        if ($InstallProcess.ExitCode -ne 0) { throw "Upgrade installer failed (exit $($InstallProcess.ExitCode))." }
        $InstalledVersion = (Get-Item $InstalledExecutable).VersionInfo.FileVersion
        if ([version]$InstalledVersion -ne [version]"$Version.0") { throw "Upgrade did not replace the executable in the previous custom directory." }
        if ((Get-FileHash $Preferences -Algorithm SHA256).Hash -ne $PreferencesBefore -or
            (Get-FileHash $SampleMission -Algorithm SHA256).Hash -ne $MissionBefore) { throw "Upgrade modified saved preferences or an existing mission." }
        $OldPath = $env:PATH
        $OldPythonPath = $env:PYTHONPATH
        $OldPythonHome = $env:PYTHONHOME
        try {
            $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
            $env:PYTHONPATH = ""
            $env:PYTHONHOME = ""
            foreach ($Mode in @("self-test", "smoke-gui")) {
                $InstalledReport = Join-Path $Repository ("test-results/installed-" + $Mode + ".json")
                Remove-Item $InstalledReport -ErrorAction SilentlyContinue
                $InstalledArguments = '--' + $Mode + ' --self-test-output "' + $InstalledReport + '"'
                $InstalledProcess = Start-Process -FilePath $InstalledExecutable -ArgumentList $InstalledArguments -WorkingDirectory $InstallDirectory -PassThru
                if (-not $InstalledProcess.WaitForExit(240000)) { $InstalledProcess.Kill(); throw "Installed app $Mode timed out." }
                $InstalledProcess.Refresh()
                if ($InstalledProcess.ExitCode -ne 0 -or -not (Test-Path $InstalledReport)) { throw "Installed app $Mode failed." }
                $InstalledResults = Get-Content $InstalledReport -Raw | ConvertFrom-Json
                if (-not $InstalledResults.ok -or -not $InstalledResults.frozen) { throw "Installed app validation failed." }
                if ($Mode -eq "self-test" -and $InstalledResults.mission_count -ne 43) { throw "Installed app mission matrix is incomplete." }
                if ($Mode -eq "smoke-gui" -and ($InstalledResults.maps.Count -ne 6 -or -not $InstalledResults.preferences_reloaded)) { throw "Installed desktop validation is incomplete." }
            }
        }
        finally {
            $env:PATH = $OldPath
            $env:PYTHONPATH = $OldPythonPath
            $env:PYTHONHOME = $OldPythonHome
        }
        $Uninstaller = Join-Path $InstallDirectory "unins000.exe"
        $UninstallProcess = Start-Process -FilePath $Uninstaller -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -PassThru
        if (-not $UninstallProcess.WaitForExit(120000)) { $UninstallProcess.Kill(); throw "Uninstaller timed out." }
        $UninstallProcess.Refresh()
        if ($UninstallProcess.ExitCode -ne 0 -or (Test-Path $InstalledExecutable)) { throw "Uninstall did not remove the installed app." }
        $Uninstalled = $true
        if ((Get-FileHash $Preferences -Algorithm SHA256).Hash -ne $PreferencesBefore -or
            (Get-FileHash $SampleMission -Algorithm SHA256).Hash -ne $MissionBefore) { throw "Installed probes or uninstall modified user preferences/missions." }
        @{
            ok = $true; old_version = $OldInstalledVersion; new_version = $InstalledVersion
            old_installer_sha256_verified = $true; new_installer_without_dir = $true
            retained_custom_install_directory = $true; retained_preferences_bytes = $true
            retained_mission_bytes = $true; installed_self_test = $true; installed_gui = $true
            uninstalled = $true
        } | ConvertTo-Json | Set-Content "test-results/upgrade-validation.json" -Encoding utf8
        Write-Host "PASS: verified 1.1.0 installer, in-place upgrade, preserved custom directory/preferences/missions, installed app and desktop probes, uninstall"
    }
    finally {
        if (-not $Uninstalled -and (Test-Path (Join-Path $InstallDirectory "unins000.exe"))) {
            $CleanupProcess = Start-Process -FilePath (Join-Path $InstallDirectory "unins000.exe") -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -PassThru
            if (-not $CleanupProcess.WaitForExit(120000)) { $CleanupProcess.Kill() }
        }
        if ($HadPreferences) {
            [System.IO.File]::WriteAllBytes($Preferences, $PreferencesBackup)
        }
        elseif (Test-Path $Preferences) { Remove-Item $Preferences }
        if (Test-Path $UpgradeDirectory) { Remove-Item -Recurse -Force $UpgradeDirectory }
    }
    & $Python "tools/write_update_manifest.py" --installer $Installer --output "dist/update.json"
    if ($LASTEXITCODE -ne 0) { throw "Could not generate the update manifest." }
    $ChecksumLines = foreach ($Download in @($Archive, $Installer, (Join-Path $Repository "dist/update.json"))) {
        $Hash = (Get-FileHash $Download -Algorithm SHA256).Hash.ToLowerInvariant()
        "$Hash  $(Split-Path -Leaf $Download)"
    }
    $ChecksumLines | Set-Content "dist/SHA256SUMS.txt" -Encoding ascii
    Write-Host "Ready to share: $Installer"
    Write-Host "Portable alternative: $Archive"
}
finally {
    Pop-Location
}
