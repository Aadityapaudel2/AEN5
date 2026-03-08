[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$ModelA = "",
    [string]$ModelB = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CompareUi = Join-Path $ProjectRoot "compare_models.py"

function Resolve-PythonExe {
    param([string]$ExplicitPath)
    if ($ExplicitPath -and (Test-Path -LiteralPath $ExplicitPath)) {
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }
    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "No Python runtime found. Activate/create a venv first."
}

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
if (-not (Test-Path -LiteralPath $CompareUi)) {
    throw "compare_models.py not found: $CompareUi"
}

Set-Location -LiteralPath $ProjectRoot

$CommandArgs = @($CompareUi)
if ($ModelA) {
    $CommandArgs += "--model-a"
    $CommandArgs += $ModelA
}
if ($ModelB) {
    $CommandArgs += "--model-b"
    $CommandArgs += $ModelB
}

Write-Host "Launching Athena model compare..."
& $ResolvedPython @CommandArgs
$ExitCode = $LASTEXITCODE

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
