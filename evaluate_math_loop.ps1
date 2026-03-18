[CmdletBinding()]
param(
    [string]$Manifest = "",
    [int]$Limit = 25,
    [string]$ModelDir = "",
    [int]$MaxRounds = 2,
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $ProjectRoot "evaluation\scripts\evaluate_math_loop.ps1"
if (-not (Test-Path -LiteralPath $Target)) {
    throw "Evaluation launcher not found: $Target"
}
& $Target -Manifest $Manifest -Limit $Limit -ModelDir $ModelDir -MaxRounds $MaxRounds -PythonExe $PythonExe
$ExitCode = $LASTEXITCODE
if ($MyInvocation.InvocationName -eq '.') {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
