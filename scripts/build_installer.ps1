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

Write-Host "Building Doppler Manager $Version"

$ReleaseVenv = Join-Path $Root ".venv-release"
$env:UV_PROJECT_ENVIRONMENT = $ReleaseVenv
Write-Host "Using isolated release environment: $ReleaseVenv"

uv sync --no-dev --group release

$RuntimeBuildRoot = Join-Path $Root ".venv-release-runtimes"
if (Test-Path $RuntimeBuildRoot) {
    Remove-Item -LiteralPath $RuntimeBuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $RuntimeBuildRoot | Out-Null

$ReleasePython = Join-Path $ReleaseVenv "Scripts\python.exe"
& $ReleasePython -m doppler_manager.sync_processing `
    --environment-root $RuntimeBuildRoot
if ($LASTEXITCODE -ne 0) {
    throw "Isolated processing runtime synchronization failed with exit code $LASTEXITCODE."
}

$env:UV_PROJECT_ENVIRONMENT = $ReleaseVenv
uv run python -m doppler_manager.release_defaults

$PayloadRoot = Join-Path $Root "build\installer-payload"
$DistApp = Join-Path $PayloadRoot "DopplerManager"
$BuildApp = Join-Path $Root "build\DopplerManager"
$LegacyDistApp = Join-Path $Root "dist\DopplerManager"
$InstallerOut = Join-Path $Root "dist\installer"
$IconPath = Join-Path $Root "packaging\DopplerManager.ico"
$ProcessingDefaults = Join-Path $Root "processing_defaults"
$RuntimeBridge = Join-Path $Root "src\doppler_manager\processing\runtime_bridge.py"

foreach ($Path in @($PayloadRoot, $BuildApp, $LegacyDistApp, $InstallerOut)) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

try {
    uv run pyinstaller `
        --noconfirm `
        --clean `
        --onedir `
        --noconsole `
        --specpath build `
        --distpath $PayloadRoot `
        --workpath $BuildApp `
        --icon $IconPath `
        --name DopplerManager `
        --collect-all streamlit `
        --collect-data imageio_ffmpeg `
        --add-data "$ProcessingDefaults;processing_defaults" `
        --add-data "$RuntimeBridge;doppler_manager\processing" `
        --hidden-import streamlit.web.cli `
        --hidden-import watchdog.observers.winapi `
        --hidden-import doppler_manager.app `
        --hidden-import doppler_manager.processing.runtime_bridge `
        src\doppler_manager\launcher.py

    if (-not (Test-Path (Join-Path $DistApp "DopplerManager.exe"))) {
        throw "PyInstaller did not produce the staged DopplerManager.exe."
    }

    foreach ($Runtime in @("holodoppler", "dopplerview", "eyeflow", "angioeye")) {
        $SourceRuntime = Join-Path $RuntimeBuildRoot $Runtime
        $TargetRuntime = Join-Path $DistApp (Join-Path "processing_runtimes" $Runtime)
        $TargetEnvironment = Join-Path $TargetRuntime ".venv"
        New-Item -ItemType Directory -Force -Path $TargetRuntime | Out-Null
        Copy-Item -Path (Join-Path $SourceRuntime ".venv") -Destination $TargetEnvironment -Recurse -Force
        if ($Runtime -eq "eyeflow") {
            Copy-Item -LiteralPath (Join-Path $SourceRuntime "runtime_limits.py") -Destination $TargetRuntime -Force
        }
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
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE."
    }

    $Installer = Join-Path $InstallerOut "DopplerManager-$Version-setup.exe"
    if (-not (Test-Path $Installer)) {
        throw "Inno Setup did not produce $Installer."
    }

    Write-Host "Installer ready: $Installer"
}
finally {
    foreach ($Path in @($PayloadRoot, $BuildApp)) {
        if (Test-Path $Path) {
            Remove-Item -LiteralPath $Path -Recurse -Force
        }
    }
    if (Test-Path $RuntimeBuildRoot) {
        Remove-Item -LiteralPath $RuntimeBuildRoot -Recurse -Force
    }
}
