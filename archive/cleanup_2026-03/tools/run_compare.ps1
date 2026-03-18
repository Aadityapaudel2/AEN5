[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$ModelA = "",
    [string]$ModelB = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppLauncher = Join-Path $ProjectRoot "apps\\two_model_dialogue_evaluator\\run.ps1"

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
if (-not (Test-Path -LiteralPath $AppLauncher)) {
    throw "Standalone evaluator launcher not found: $AppLauncher"
}

Set-Location -LiteralPath $ProjectRoot

Write-Host "Launching Two-Model Dialogue Evaluator..."
& $AppLauncher -PythonExe $ResolvedPython -ModelA $ModelA -ModelB $ModelB
$ExitCode = $LASTEXITCODE

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
