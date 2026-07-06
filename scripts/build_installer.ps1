param(
    [string]$Version = "",
    [string]$InnoCompiler = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $Root

if (-not $Version) {
    $PyProject = Get-Content (Join-Path $Root "pyproject.toml") -Raw
    if ($PyProject -notmatch '(?m)^version\s*=\s*"([^"]+)"') {
        throw "Unable to read project version from pyproject.toml."
    }
    $Version = $Matches[1]
}

Write-Host "Building Doppler Manager Scan $Version"

$ReleaseVenv = Join-Path $Root ".venv-release"
$env:UV_PROJECT_ENVIRONMENT = $ReleaseVenv
Write-Host "Using isolated release environment: $ReleaseVenv"

uv sync --no-dev --extra processing --group release
uv run python -m doppler_manager.release_defaults

$DistApp = Join-Path $Root "dist\DopplerManager"
$BuildApp = Join-Path $Root "build\DopplerManager"
$InstallerOut = Join-Path $Root "dist\installer"

foreach ($Path in @($DistApp, $BuildApp, $InstallerOut)) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

uv run pyinstaller `
    --noconfirm `
    --clean `
    --onedir `
    --noconsole `
    --specpath build `
    --name DopplerManager `
    --collect-all streamlit `
    --collect-data imageio_ffmpeg `
    --hidden-import streamlit.web.cli `
    --hidden-import watchdog.observers.winapi `
    --hidden-import doppler_manager.app_scan `
    src\doppler_manager\launcher_scan.py

if (-not (Test-Path (Join-Path $DistApp "DopplerManager.exe"))) {
    throw "PyInstaller did not produce dist\DopplerManager\DopplerManager.exe."
}

if (-not $InnoCompiler) {
    $Candidates = @(
        $env:ISCC_PATH,
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path $Candidate)) {
            $InnoCompiler = $Candidate
            break
        }
    }
}

if (-not $InnoCompiler -or -not (Test-Path $InnoCompiler)) {
    throw "Inno Setup compiler not found. Install Inno Setup 6 or pass -InnoCompiler C:\Path\To\ISCC.exe."
}

$env:DM_VERSION = $Version
New-Item -ItemType Directory -Force -Path $InstallerOut | Out-Null
& $InnoCompiler (Join-Path $Root "packaging\DopplerManager.iss")

$Installer = Join-Path $InstallerOut "DopplerManager-$Version-setup.exe"
if (-not (Test-Path $Installer)) {
    throw "Inno Setup did not produce $Installer."
}

Write-Host "Installer ready: $Installer"
