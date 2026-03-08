[CmdletBinding()]
param(
    [switch]$Tools,
    [bool]$LoadModel = $true,
    [int]$Port = 8000,
    [string]$PathPrefix = "/AthenaV5",
    [string]$PythonExe = ""
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
& (Join-Path $ProjectRoot "browser\run_browser.ps1") -Mode dev -Tools:$Tools -LoadModel:$LoadModel -Port $Port -PathPrefix $PathPrefix -PythonExe $PythonExe
exit $LASTEXITCODE
