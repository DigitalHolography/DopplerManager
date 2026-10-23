[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$SyncArguments)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Push-Location $workspace
try {
    $managerPython = Join-Path $workspace ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $managerPython)) {
        & uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "DopplerManager dependency synchronization failed." }
    }
    & $managerPython -m doppler_manager.tooling.sync @SyncArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Processing runtime and default settings synchronization failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
