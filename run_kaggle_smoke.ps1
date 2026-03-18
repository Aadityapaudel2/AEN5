[CmdletBinding()]
param(
    [string]$Problem = "",
    [string]$File = "",
    [string]$ModelDir = "",
    [ValidateSet("baseline", "loop")][string]$Strategy = "baseline",
    [int]$MaxRounds = 2,
    [switch]$NoTools,
    [int]$AnswerModulus = 100000,
    [int]$AnswerWidth = 0,
    [string]$FallbackAnswer = "0",
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

if (-not $Problem -and -not $File) {
    throw "Provide -Problem or -File."
}

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
Set-Location -LiteralPath $ProjectRoot

$Args = @(
    "-m", "desktop_engine.agentic.kaggle_smoke",
    "--strategy", $Strategy,
    "--max-rounds", "$MaxRounds",
    "--answer-modulus", "$AnswerModulus",
    "--answer-width", "$AnswerWidth",
    "--fallback-answer", $FallbackAnswer
)
if ($Problem) { $Args += @( "--problem", $Problem ) }
if ($File) { $Args += @( "--file", $File ) }
if ($ModelDir) { $Args += @( "--model-dir", $ModelDir ) }
if ($NoTools) { $Args += "--no-tools" }

Write-Host "Running Kaggle-style smoke..."
& $ResolvedPython @Args
$ExitCode = $LASTEXITCODE

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
