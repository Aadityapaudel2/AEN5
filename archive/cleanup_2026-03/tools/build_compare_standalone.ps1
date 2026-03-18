[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppBuildScript = Join-Path $ProjectRoot "apps\\two_model_dialogue_evaluator\\build_standalone.ps1"

if (-not (Test-Path -LiteralPath $AppBuildScript)) {
    throw "Standalone evaluator build script not found: $AppBuildScript"
}

& $AppBuildScript -PythonExe $PythonExe -Clean:$Clean
exit $LASTEXITCODE
