[CmdletBinding()]
param(
    [switch]$Tools,
    [bool]$LoadModel = $true,
    [int]$Port = 8000,
    [string]$PathPrefix = "/AthenaV5",
    [string]$Hostname = "portal.neohmlabs.com",
    [switch]$QuickTunnel,
    [string]$PythonExe = "",
    [string]$CloudflaredExe = "",
    [string]$AuthEnvFile = ""
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
& (Join-Path $ProjectRoot "browser\run_browser.ps1") -Mode prod -Tools:$Tools -LoadModel:$LoadModel -Port $Port -PathPrefix $PathPrefix -Hostname $Hostname -QuickTunnel:$QuickTunnel -PythonExe $PythonExe -CloudflaredExe $CloudflaredExe -AuthEnvFile $AuthEnvFile
exit $LASTEXITCODE
