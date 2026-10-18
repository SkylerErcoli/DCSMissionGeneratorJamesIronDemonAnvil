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
            if ($Mode -eq "self-test" -and $Results.mission_count -ne 30) {
                throw "The frozen mission matrix is incomplete."
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
    # An actual silent install and uninstall catch missing payloads, bad paths,
    # unwanted elevation, and an installer that works only from the checkout.
    $InstallDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("Iron Anvil Installed " + [guid]::NewGuid().ToString("N"))
    try {
        $InstallArguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $InstallDirectory + '"'
        $InstallProcess = Start-Process -FilePath $Installer -ArgumentList $InstallArguments -PassThru
        if (-not $InstallProcess.WaitForExit(120000)) { $InstallProcess.Kill(); throw "Installer timed out." }
        $InstallProcess.Refresh()
        if ($InstallProcess.ExitCode -ne 0) { throw "Installer failed (exit $($InstallProcess.ExitCode))." }
        $InstalledExecutable = Join-Path $InstallDirectory "IronAnvil.exe"
        if (-not (Test-Path $InstalledExecutable)) { throw "Installed application is missing." }
        $InstalledReport = Join-Path $Repository "test-results/installed-self-test.json"
        Remove-Item $InstalledReport -ErrorAction SilentlyContinue
        $OldPath = $env:PATH
        $OldPythonPath = $env:PYTHONPATH
        $OldPythonHome = $env:PYTHONHOME
        try {
            $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
            $env:PYTHONPATH = ""
            $env:PYTHONHOME = ""
            $InstalledArguments = '--self-test --self-test-output "' + $InstalledReport + '"'
            $InstalledProcess = Start-Process -FilePath $InstalledExecutable -ArgumentList $InstalledArguments -WorkingDirectory $InstallDirectory -PassThru
            if (-not $InstalledProcess.WaitForExit(240000)) { $InstalledProcess.Kill(); throw "Installed app self-test timed out." }
            $InstalledProcess.Refresh()
            if ($InstalledProcess.ExitCode -ne 0 -or -not (Test-Path $InstalledReport)) { throw "Installed app self-test failed." }
            $InstalledResults = Get-Content $InstalledReport -Raw | ConvertFrom-Json
            if (-not $InstalledResults.ok -or -not $InstalledResults.frozen -or $InstalledResults.mission_count -ne 30) { throw "Installed app validation failed." }
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
        Write-Host "PASS: installer, installed app self-test, uninstaller"
    }
    finally {
        if (Test-Path $InstallDirectory) { Remove-Item -Recurse -Force $InstallDirectory }
    }
    $ChecksumLines = foreach ($Download in @($Archive, $Installer)) {
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
