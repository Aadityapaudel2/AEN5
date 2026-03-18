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
$Target = Join-Path $ProjectRoot "evaluation\scripts\run_math_loop.ps1"
if (-not (Test-Path -LiteralPath $Target)) {
    throw "Evaluation launcher not found: $Target"
}
& $Target -Problem $Problem -File $File -ModelDir $ModelDir -MaxRounds $MaxRounds -NoTools:$NoTools -PythonExe $PythonExe
$ExitCode = $LASTEXITCODE
if ($MyInvocation.InvocationName -eq '.') {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
