[CmdletBinding()]
param(
    [string]$Problem = "",
    [string]$File = "",
    [string]$ModelDir = "",
    [int]$MaxRounds = 2,
    [switch]$NoTools,
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

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
Set-Location -LiteralPath $ProjectRoot

$Args = @("-m", "desktop_engine.agentic", "solve", "--max-rounds", "$MaxRounds")
if ($Problem) { $Args += @("--problem", $Problem) }
if ($File) { $Args += @("--file", $File) }
if ($ModelDir) { $Args += @("--model-dir", $ModelDir) }
if ($NoTools) { $Args += "--no-tools" }

Write-Host "Running 2-body math loop..."
& $ResolvedPython @Args
$ExitCode = $LASTEXITCODE

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
