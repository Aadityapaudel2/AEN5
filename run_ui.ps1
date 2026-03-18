[CmdletBinding()]
param(
    [switch]$Tools,
    [switch]$NoAutoInstallDeps,
    [int]$Port = 8000,
    [string]$PathPrefix = "/AthenaV5",
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Desktop UI is private-only. Forwarding to the exclusive Athena desktop."
Write-Host "For public-facing model work, use browser dev: .\run_dev.ps1"
& (Join-Path $ProjectRoot 'run_ui_private.ps1') -Tools:$Tools -NoAutoInstallDeps:$NoAutoInstallDeps -Port $Port -PathPrefix $PathPrefix -PythonExe $PythonExe
$ExitCode = $LASTEXITCODE
if ($MyInvocation.InvocationName -eq '.') {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
