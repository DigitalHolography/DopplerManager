[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Push-Location $workspace
try {
    & uv sync
    if ($LASTEXITCODE -ne 0) {
        throw "DopplerManager dependency synchronization failed with exit code $LASTEXITCODE."
    }

    $managerPython = Join-Path $workspace ".venv\Scripts\python.exe"
    & $managerPython -m doppler_manager.sync_processing
    if ($LASTEXITCODE -ne 0) {
        throw "Isolated processing runtime synchronization failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
