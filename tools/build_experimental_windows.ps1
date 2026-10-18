[CmdletBinding()]
param([string]$Python = "python", [switch]$SkipInstall)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($env:OS -ne "Windows_NT") { throw "Build with 64-bit Python 3.12 on Windows." }
$Repository = Split-Path -Parent $PSScriptRoot
Push-Location $Repository
function Run-Probe([string]$Executable, [string]$Mode, [string]$Report, [string]$Directory) {
    $Process = Start-Process -FilePath $Executable -ArgumentList ('--' + $Mode + ' --self-test-output "' + $Report + '"') -WorkingDirectory $Directory -PassThru
    if (-not $Process.WaitForExit(180000)) { $Process.Kill(); throw "$Mode timed out." }
    $Process.Refresh()
    if ($Process.ExitCode -ne 0) { throw "$Mode exited with $($Process.ExitCode)." }
    $Result = Get-Content $Report -Raw | ConvertFrom-Json
    if (-not $Result.ok -or -not $Result.frozen -or $Result.platform -ne 'win32') { throw "$Mode did not run the native executable." }
    return $Result
}
$TestRoot = Join-Path ([IO.Path]::GetTempPath()) ("Iron Anvil portable " + [guid]::NewGuid().ToString('N'))
$ProgramDirectory = Join-Path $TestRoot 'Read only app folder'
$DataDirectory = Join-Path $TestRoot 'Existing user data'
$OldVariables = @{}
$Acl = $null
try {
    & $Python -c "import struct,sys; from ironanvil import EXPERIMENTAL; assert EXPERIMENTAL; assert sys.version_info[:2]==(3,12); assert struct.calcsize('P')==8"
    if ($LASTEXITCODE -ne 0) { throw 'Use experimental source with 64-bit Python 3.12.' }
    if (-not $SkipInstall) {
        & $Python -m pip install --disable-pip-version-check -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    }
    & $Python -m PyInstaller --noconfirm --clean packaging/ironanvil.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    $BuiltExecutable = Join-Path $Repository 'dist/IronAnvil-Experimental.exe'
    if (-not (Test-Path $BuiltExecutable -PathType Leaf)) { throw 'Standalone executable is missing.' }
    New-Item -ItemType Directory -Force 'test-results', $ProgramDirectory, $DataDirectory | Out-Null
    $Preferences = Join-Path $DataDirectory 'preferences.json'
    [IO.File]::WriteAllText($Preferences, '{"theme":"dark","mission":{"start":"hot","seed":"917"},"portable_probe":"preserve"}')
    $ExistingMission = Join-Path $DataDirectory 'Keep my old co-op mission.miz'
    & $Python -m ironanvil generate --seed 88 --output $ExistingMission
    if ($LASTEXITCODE -ne 0) { throw 'Preservation sample generation failed.' }
    $MissionHash = (Get-FileHash $ExistingMission -Algorithm SHA256).Hash
    $Executable = Join-Path $ProgramDirectory 'IronAnvil-Experimental.exe'
    Copy-Item $BuiltExecutable $Executable
    $BeforeHash = (Get-FileHash $Executable -Algorithm SHA256).Hash
    foreach ($Name in @('PATH','PYTHONPATH','PYTHONHOME','IRONANVIL_DATA_DIR','IRONANVIL_CACHE_DIR')) {
        $OldVariables[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process')
    }
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"; $env:PYTHONPATH = ''; $env:PYTHONHOME = ''
    $env:IRONANVIL_DATA_DIR = $DataDirectory; $env:IRONANVIL_CACHE_DIR = Join-Path $TestRoot 'Cache'
    # A real deny-write ACL proves that one-file extraction and user data work
    # outside the program directory. A Windows folder read-only flag does not.
    $Acl = Get-Acl $ProgramDirectory
    $ReadOnlyAcl = Get-Acl $ProgramDirectory
    $Rule = [Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.WindowsIdentity]::GetCurrent().User,
        'Write', 'ContainerInherit,ObjectInherit', 'None', 'Deny')
    $ReadOnlyAcl.AddAccessRule($Rule); Set-Acl -Path $ProgramDirectory -AclObject $ReadOnlyAcl
    $WriteDenied = $false
    try { [IO.File]::WriteAllText((Join-Path $ProgramDirectory 'should-not-write.txt'), 'probe') }
    catch [UnauthorizedAccessException] { $WriteDenied = $true }
    if (-not $WriteDenied) { throw 'The application folder was not actually read-only.' }
    $Self = Run-Probe $Executable 'self-test' (Join-Path $Repository 'test-results/portable-self-test.json') $TestRoot
    if ($Self.mission_count -ne 25 -or $Self.navigation_checks -ne 25 -or $Self.geography_checks -ne 25 -or $Self.quick_setup_checks -ne 3 -or
        $Self.intelligence_checks -ne 3 -or $Self.channel -ne 'experimental') { throw 'Incomplete portable mission probe.' }
    $Gui = Run-Probe $Executable 'smoke-gui' (Join-Path $Repository 'test-results/portable-smoke-gui.json') $TestRoot
    if ($Gui.maps.Count -ne 6 -or -not $Gui.preferences_reloaded -or -not $Gui.mission_preview_passed -or
        -not $Gui.quick_setup_passed -or -not $Gui.small_window_passed -or -not $Gui.custom_settings_preserved -or
        -not $Gui.offline_relief_passed) { throw 'Incomplete desktop probe.' }
    Set-Acl -Path $ProgramDirectory -AclObject $Acl; $Acl = $null
    # Replace only the EXE, without installer, registry or old-release downloads.
    Copy-Item -Force $BuiltExecutable $Executable
    if ((Get-FileHash $Executable -Algorithm SHA256).Hash -ne $BeforeHash) { throw 'Portable replacement changed executable bytes.' }
    $State = Run-Probe $Executable 'portable-state' (Join-Path $Repository 'test-results/portable-state.json') $TestRoot
    if (-not $State.preferences_restored -or $State.saved_start -ne 'hot' -or $State.seed -ne 917) { throw 'Preferences did not survive replacement.' }
    if ((Get-FileHash $ExistingMission -Algorithm SHA256).Hash -ne $MissionHash) { throw 'Portable execution/replacement changed an existing mission.' }
    @{
        ok=$true; one_file=$true; no_python_on_path=$true; read_only_app_folder=$true; path_with_spaces=$true
        executable_replacement_passed=$true; preferences_restored=$true; existing_mission_unchanged=$true
        application_folder_entry_count=@(Get-ChildItem $ProgramDirectory -Force).Count; installer_used=$false
    } | ConvertTo-Json | Set-Content 'test-results/portable-validation.json' -Encoding utf8
    if (@(Get-ChildItem $ProgramDirectory -Force).Count -ne 1) { throw 'The portable app wrote files beside itself.' }
    $Hash = (Get-FileHash $BuiltExecutable -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText((Join-Path $Repository 'dist/SHA256SUMS.txt'), "$Hash  IronAnvil-Experimental.exe`n", [Text.Encoding]::ASCII)
    Write-Host 'PASS: single-file portable app, native missions/GUI, read-only folder and replace-in-place settings preservation.'
} finally {
    if ($null -ne $Acl) { Set-Acl -Path $ProgramDirectory -AclObject $Acl }
    foreach ($Name in $OldVariables.Keys) { [Environment]::SetEnvironmentVariable($Name, $OldVariables[$Name], 'Process') }
    if (Test-Path $TestRoot) { Remove-Item -Recurse -Force $TestRoot }
    Pop-Location
}
