[CmdletBinding()]
param(
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $ProjectRoot "evaluation\scripts\run_math_loop_observer.ps1"
if (-not (Test-Path -LiteralPath $Target)) {
    throw "Evaluation launcher not found: $Target"
}
& $Target -PythonExe $PythonExe
$ExitCode = $LASTEXITCODE
if ($MyInvocation.InvocationName -eq '.') {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
