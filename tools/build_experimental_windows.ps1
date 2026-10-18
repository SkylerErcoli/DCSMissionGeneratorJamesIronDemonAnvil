[CmdletBinding()]
param([string]$Python = "python", [switch]$SkipInstall)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($env:OS -ne "Windows_NT") { throw "Build with 64-bit Python 3.12 on Windows." }
$Repository = Split-Path -Parent $PSScriptRoot
Push-Location $Repository
function Run-CheckedProcess([string]$File, [string]$Arguments, [string]$Directory, [int]$Timeout = 240000) {
    $Process = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $Directory -PassThru
    if (-not $Process.WaitForExit($Timeout)) { $Process.Kill(); throw "Process timed out: $File" }
    $Process.Refresh()
    if ($Process.ExitCode -ne 0) { throw "Process failed ($($Process.ExitCode)): $File" }
}
function Probe-App([string]$Executable, [string]$Prefix, [string]$Directory) {
    $OldPath = $env:PATH; $OldPythonPath = $env:PYTHONPATH; $OldPythonHome = $env:PYTHONHOME
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"; $env:PYTHONPATH = ""; $env:PYTHONHOME = ""
        foreach ($Mode in @("self-test", "smoke-gui")) {
            $Report = Join-Path $Repository ("test-results/$Prefix-$Mode.json")
            Run-CheckedProcess $Executable ('--' + $Mode + ' --self-test-output "' + $Report + '"') $Directory
            $Result = Get-Content $Report -Raw | ConvertFrom-Json
            if (-not $Result.ok -or -not $Result.frozen -or $Result.platform -ne "win32") { throw "$Prefix $Mode failed." }
            if ($Mode -eq "self-test" -and ($Result.mission_count -ne 73 -or $Result.operation_checks -ne 30 -or
                $Result.intelligence_checks -ne 6 -or $Result.alternate_checks -ne 12 -or $Result.channel -ne "experimental")) {
                throw "Incomplete experimental mission probe."
            }
            if ($Mode -eq "smoke-gui" -and ($Result.maps.Count -ne 6 -or -not $Result.preferences_reloaded -or
                -not $Result.mission_preview_passed)) { throw "Incomplete desktop probe." }
        }
    } finally { $env:PATH = $OldPath; $env:PYTHONPATH = $OldPythonPath; $env:PYTHONHOME = $OldPythonHome }
}
function Get-VerifiedInstaller([string]$ReleaseTag, [string]$Asset, [string]$Destination, [string]$Directory) {
    $BaseURL = "https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/download/$ReleaseTag"
    $ChecksumFile = Join-Path $Directory "$ReleaseTag-checksums.txt"
    Invoke-WebRequest "$BaseURL/SHA256SUMS.txt" -OutFile $ChecksumFile
    Invoke-WebRequest "$BaseURL/$Asset" -OutFile $Destination
    $Pattern = '^[a-fA-F0-9]{64}\s+' + [regex]::Escape($Asset) + '$'
    $ChecksumLines = @(Get-Content $ChecksumFile | Where-Object { $_ -match $Pattern })
    if ($ChecksumLines.Count -ne 1) { throw "$ReleaseTag checksum missing or ambiguous." }
    $ExpectedHash = ($ChecksumLines[0] -split '\s+')[0]
    if ((Get-FileHash $Destination -Algorithm SHA256).Hash -ne $ExpectedHash) { throw "$ReleaseTag installer checksum mismatch." }
}
$StableKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{2C791DDC-1A55-4FAE-BAB3-30819BF2869D}_is1"
$ExperimentalKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{F698B14E-6D10-4A68-BB62-A75C5DCC04F2}_is1"
$StablePreferences = Join-Path $env:LOCALAPPDATA "IronAnvil/preferences.json"
$ExperimentalPreferences = Join-Path $env:LOCALAPPDATA "IronAnvilExperimental/preferences.json"
$Backups = @{}
$TestRoot = Join-Path ([IO.Path]::GetTempPath()) ("IronAnvil coexistence " + [guid]::NewGuid().ToString("N"))
$StableDirectory = Join-Path $TestRoot "Stable app"
$ExperimentalDirectory = Join-Path $TestRoot "Experimental app"
$InstalledStable = $false; $InstalledExperimental = $false
try {
    # Never run an installer/uninstaller over a developer's real installation.
    if ((Test-Path $StableKey) -or (Test-Path $ExperimentalKey)) { throw "Use a clean Windows build runner; an Iron Anvil installation already exists." }
    & $Python -c "import struct,sys; from ironanvil import EXPERIMENTAL; assert EXPERIMENTAL; assert sys.version_info[:2]==(3,12); assert struct.calcsize('P')==8"
    if ($LASTEXITCODE -ne 0) { throw "Use experimental source with 64-bit Python 3.12." }
    if (-not $SkipInstall) {
        & $Python -m pip install --disable-pip-version-check -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    }
    & $Python -m PyInstaller --noconfirm --clean packaging/ironanvil.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    $ApplicationFolder = Join-Path $Repository "dist/IronAnvil"
    $Executable = Join-Path $ApplicationFolder "IronAnvil.exe"
    Copy-Item "docs/experimental/START-HERE.txt" (Join-Path $ApplicationFolder "START HERE.txt")
    New-Item -ItemType Directory -Force "test-results", $TestRoot | Out-Null
    Probe-App $Executable "frozen" $TestRoot
    $Compiler = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6/ISCC.exe"
    if (-not (Test-Path $Compiler)) { $Compiler = (Get-Command "ISCC.exe" -ErrorAction Stop).Source }
    $Version = (& $Python -c 'from ironanvil import __version__; print(__version__)').Trim()
    & $Compiler "/DAppVersion=$Version" "packaging/installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed." }
    $Installer = Join-Path $Repository "dist/IronAnvil-Experimental-Setup-x64.exe"
    if (-not (Test-Path $Installer)) { throw "Experimental installer missing." }
    $Archive = Join-Path $Repository "dist/IronAnvil-Experimental-Windows-x64.zip"
    Remove-Item $Archive -ErrorAction SilentlyContinue
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($ApplicationFolder, $Archive)

    # Download the exact published stable version, verifying its published hash.
    $StableInstaller = Join-Path $TestRoot "Stable-1.2.0-Setup.exe"
    Get-VerifiedInstaller "v1.2.0" "IronAnvil-Setup-x64.exe" $StableInstaller $TestRoot
    $PreviousInstaller = Join-Path $TestRoot "Experimental-1.3.1-Setup.exe"
    Get-VerifiedInstaller "v1.3.1-experimental.2" "IronAnvil-Experimental-Setup-x64.exe" $PreviousInstaller $TestRoot
    foreach ($Path in @($StablePreferences, $ExperimentalPreferences)) {
        $Backups[$Path] = if (Test-Path $Path) { [IO.File]::ReadAllBytes($Path) } else { $null }
        New-Item -ItemType Directory -Force (Split-Path -Parent $Path) | Out-Null
    }
    Run-CheckedProcess $StableInstaller ('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $StableDirectory + '"') $TestRoot
    $InstalledStable = $true
    $StableExe = Join-Path $StableDirectory "IronAnvil.exe"
    $StableVersion = (Get-Item $StableExe).VersionInfo.FileVersion
    if ([version]$StableVersion -ne [version]"1.2.0.0") { throw "Wrong stable baseline." }
    Run-CheckedProcess $PreviousInstaller ('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $ExperimentalDirectory + '"') $TestRoot
    $InstalledExperimental = $true
    $ExperimentalExe = Join-Path $ExperimentalDirectory "IronAnvil.exe"
    $PreviousVersion = (Get-Item $ExperimentalExe).VersionInfo.FileVersion
    if ([version]$PreviousVersion -ne [version]"1.3.1.0") { throw "Wrong previous experimental baseline." }
    [IO.File]::WriteAllText($StablePreferences, '{"theme":"dark","user_note":"stable settings must stay exactly as written"}')
    [IO.File]::WriteAllText($ExperimentalPreferences, '{"theme":"light","user_note":"settings from previous experimental install"}')
    $StableExeHash = (Get-FileHash $StableExe -Algorithm SHA256).Hash
    $StablePreferencesHash = (Get-FileHash $StablePreferences -Algorithm SHA256).Hash
    $ExperimentalPreferencesHash = (Get-FileHash $ExperimentalPreferences -Algorithm SHA256).Hash
    $ExistingMission = Join-Path $TestRoot "Existing co-op mission.miz"
    & $Python -m ironanvil generate --seed 88 --output $ExistingMission
    if ($LASTEXITCODE -ne 0) { throw "Could not prepare preservation sample." }
    $MissionHash = (Get-FileHash $ExistingMission -Algorithm SHA256).Hash
    # Upgrade the actual published previous preview without /DIR. Inno must
    # discover its separate experimental identity and retain this custom path.
    Run-CheckedProcess $Installer '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' $TestRoot
    $ExperimentalVersion = (Get-Item $ExperimentalExe).VersionInfo.FileVersion
    if ([version]$ExperimentalVersion -ne [version]"$Version.0") { throw "Wrong experimental executable version." }
    if (-not (Test-Path $StableKey) -or -not (Test-Path $ExperimentalKey)) { throw "Installers share or lost an identity." }
    # Reinstall without /DIR must find only the experimental install.
    Run-CheckedProcess $Installer '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' $TestRoot
    Probe-App $ExperimentalExe "installed" $TestRoot
    if ((Get-FileHash $StableExe -Algorithm SHA256).Hash -ne $StableExeHash -or
        (Get-FileHash $StablePreferences -Algorithm SHA256).Hash -ne $StablePreferencesHash -or
        (Get-FileHash $ExperimentalPreferences -Algorithm SHA256).Hash -ne $ExperimentalPreferencesHash -or
        (Get-FileHash $ExistingMission -Algorithm SHA256).Hash -ne $MissionHash) { throw "Coexistence or reinstall changed user/stable files." }
    Run-CheckedProcess (Join-Path $ExperimentalDirectory "unins000.exe") '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' $TestRoot
    $InstalledExperimental = $false
    if (Test-Path $ExperimentalExe) { throw "Experimental uninstall failed." }
    if ((Get-FileHash $StableExe -Algorithm SHA256).Hash -ne $StableExeHash -or
        (Get-FileHash $StablePreferences -Algorithm SHA256).Hash -ne $StablePreferencesHash -or
        (Get-FileHash $ExistingMission -Algorithm SHA256).Hash -ne $MissionHash) { throw "Experimental uninstall changed stable/user files." }
    # Actually run the stable application after removing the experimental one.
    $StableReport = Join-Path $Repository "test-results/stable-after-experimental.json"
    $OldPath = $env:PATH; $OldPythonPath = $env:PYTHONPATH; $OldPythonHome = $env:PYTHONHOME
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"; $env:PYTHONPATH = ""; $env:PYTHONHOME = ""
        Run-CheckedProcess $StableExe ('--self-test --self-test-output "' + $StableReport + '"') $TestRoot
    } finally { $env:PATH = $OldPath; $env:PYTHONPATH = $OldPythonPath; $env:PYTHONHOME = $OldPythonHome }
    $StableResult = Get-Content $StableReport -Raw | ConvertFrom-Json
    if (-not $StableResult.ok -or -not $StableResult.frozen -or $StableResult.mission_count -ne 43) { throw "Stable app no longer works." }
    @{
        ok=$true; stable_version="1.2.0"; experimental_version=$Version; stable_installer_sha256_verified=$true
        previous_experimental_version="1.3.1"; previous_experimental_installer_sha256_verified=$true
        actual_experimental_upgrade_passed=$true; experimental_upgrade_without_dir=$true
        separate_installer_identities=$true; stable_executable_unchanged=$true; stable_preferences_unchanged=$true
        experimental_preferences_preserved=$true; existing_mission_unchanged=$true; experimental_reinstall_without_dir=$true
        experimental_uninstalled=$true; stable_after_experimental_passed=$true
    } | ConvertTo-Json | Set-Content "test-results/coexistence-validation.json" -Encoding utf8
    $Lines = foreach ($Download in @($Installer, $Archive)) {
        "$((Get-FileHash $Download -Algorithm SHA256).Hash.ToLowerInvariant())  $(Split-Path -Leaf $Download)"
    }
    [IO.File]::WriteAllText((Join-Path $Repository "dist/SHA256SUMS.txt"), (($Lines -join "`n") + "`n"), [Text.Encoding]::ASCII)
    Write-Host "PASS: experimental app, installed app, coexistence/reinstall/uninstall, and stable 1.2 still working."
} finally {
    if ($InstalledExperimental -and (Test-Path (Join-Path $ExperimentalDirectory "unins000.exe"))) {
        try { Run-CheckedProcess (Join-Path $ExperimentalDirectory "unins000.exe") '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' $TestRoot }
        catch { Write-Warning "Experimental test uninstall cleanup failed: $_" }
    }
    if ($InstalledStable -and (Test-Path (Join-Path $StableDirectory "unins000.exe"))) {
        try { Run-CheckedProcess (Join-Path $StableDirectory "unins000.exe") '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' $TestRoot }
        catch { Write-Warning "Stable test uninstall cleanup failed: $_" }
    }
    foreach ($Path in $Backups.Keys) {
        if ($null -ne $Backups[$Path]) { [IO.File]::WriteAllBytes($Path, $Backups[$Path]) }
        else { Remove-Item $Path -ErrorAction SilentlyContinue }
    }
    if (Test-Path $TestRoot) { Remove-Item -Recurse -Force $TestRoot }
    Pop-Location
}
