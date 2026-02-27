[CmdletBinding()]
param(
    [switch]$LoadModel,
    [string]$PathPrefix = "/AthenaV5",
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvLocal = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvWorkspace = Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $VenvLocal) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvLocal).Path
} elseif (Test-Path -LiteralPath $VenvWorkspace) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvWorkspace).Path
} else {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$env:ATHENA_PORTAL_PATH_PREFIX = $PathPrefix
$env:ATHENA_PORTAL_PORT = [string]$Port
$env:ATHENA_WEB_LOAD_MODEL = if ($LoadModel) { "1" } else { "0" }

Write-Host "Starting Athena V5 portal..."
Write-Host "path_prefix=$($env:ATHENA_PORTAL_PATH_PREFIX) port=$($env:ATHENA_PORTAL_PORT) load_model=$($env:ATHENA_WEB_LOAD_MODEL)"

Set-Location -LiteralPath $ProjectRoot
& $PythonExe (Join-Path $ProjectRoot "portal_server.py")
