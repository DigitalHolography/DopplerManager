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

# Every build has its own environments, payload and diagnostics.
$RunRoot = Join-Path $Root ("build\release-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$ReleaseVenv = Join-Path $RunRoot "orchestrator"
$env:UV_PROJECT_ENVIRONMENT = $ReleaseVenv
uv sync --locked --no-dev --group release
if ($LASTEXITCODE -ne 0) { throw "Release orchestrator synchronization failed." }
$ReleasePython = Join-Path $ReleaseVenv "Scripts\python.exe"
$RuntimeBuildRoot = Join-Path $RunRoot "runtimes"
$ProcessingDefaults = Join-Path $RunRoot "defaults"
$PayloadRoot = Join-Path $RunRoot "payload"
$DistApp = Join-Path $PayloadRoot "DopplerManager"
$BuildApp = Join-Path $RunRoot "pyinstaller-work"
$InstallerOut = Join-Path $Root "dist\installer"
$MappedPayloadDrive = $null

try {
    & $ReleasePython -m doppler_manager.tooling.sync --locked `
        --environment-root $RuntimeBuildRoot --defaults-output $ProcessingDefaults `
        --validation-output (Join-Path $RunRoot "validation\runtimes")
    if ($LASTEXITCODE -ne 0) { throw "Locked processing synchronization failed." }
    & $ReleasePython -m doppler_manager.tooling.release `
        --runtime-root $RuntimeBuildRoot --defaults $ProcessingDefaults `
        --output (Join-Path $RunRoot "spec") --dist $PayloadRoot --work $BuildApp
    if ($LASTEXITCODE -ne 0) { throw "Release build or relocated-runtime validation failed." }
    if (-not (Test-Path (Join-Path $DistApp "DopplerManager.exe"))) {
        throw "PyInstaller did not produce the staged DopplerManager.exe."
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
    # Keep compiler source paths short enough for deeply nested runtime headers.
    foreach ($DriveCode in 90..71) {
        $CandidateDrive = "$([char]$DriveCode):"
        if (Get-PSDrive -Name ([string][char]$DriveCode) -ErrorAction SilentlyContinue) {
            continue
        }
        & subst.exe $CandidateDrive $DistApp
        if ($LASTEXITCODE -eq 0) {
            $MappedPayloadDrive = $CandidateDrive
            break
        }
    }
    if (-not $MappedPayloadDrive) {
        throw "No free drive letter was available for the installer payload."
    }
    & $InnoCompiler "/DMyAppSourceDir=$MappedPayloadDrive" (Join-Path $Root "packaging\DopplerManager.iss")
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
    if ($MappedPayloadDrive) {
        & subst.exe $MappedPayloadDrive /D
    }
    Write-Host "Build evidence retained at: $RunRoot"
}
