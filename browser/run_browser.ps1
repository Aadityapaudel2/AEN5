[CmdletBinding()]
param(
    [ValidateSet("dev", "prod", "local")]
    [string]$Mode = "dev",
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

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PortalScript = Join-Path $PSScriptRoot "portal_server.py"
$CloudflaredScript = Join-Path $PSScriptRoot "cloudflared_athenav5.ps1"
$ResolvedMode = if ($Mode -eq "local") { "dev" } else { $Mode }

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
    throw "python executable not found."
}

function Import-EnvFile {
    param([string]$FilePath)
    if (-not $FilePath) { return $false }
    if (-not (Test-Path -LiteralPath $FilePath)) { return $false }
    foreach ($rawLine in Get-Content -LiteralPath $FilePath) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { continue }
        $name = $matches[1]
        $value = $matches[2].Trim()
        if ((($value.StartsWith('"')) -and $value.EndsWith('"')) -or (($value.StartsWith("'")) -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "env:$name" -Value $value
    }
    return $true
}

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
$env:ATHENA_PORTAL_MODE = $ResolvedMode
$env:ATHENA_PORTAL_PORT = [string]$Port
$env:ATHENA_PORTAL_PATH_PREFIX = $PathPrefix
$env:ATHENA_WEB_LOAD_MODEL = if ($LoadModel) { "1" } else { "0" }
$env:ATHENA_TOOLS_ENABLED = if ($Tools) { "1" } else { "0" }
$env:ATHENA_PORTAL_HOST = if ($ResolvedMode -eq "prod") { "0.0.0.0" } else { "127.0.0.1" }
$env:ATHENA_AUTH_REQUIRED = if ($ResolvedMode -eq "prod") { "1" } else { "0" }
$env:ATHENA_PORTAL_COOKIE_SECURE = if ($ResolvedMode -eq "prod") { "1" } else { "0" }
$env:ATHENA_LOG_ROOT = (Join-Path $ProjectRoot "data\users")

if ($ResolvedMode -eq "prod") {
    $authFiles = @()
    if ($AuthEnvFile -and $AuthEnvFile.Trim()) {
        $candidate = $AuthEnvFile.Trim()
        if (-not [System.IO.Path]::IsPathRooted($candidate)) {
            $candidate = Join-Path $ProjectRoot $candidate
        }
        $authFiles += $candidate
    }
    $authFiles += @(
        (Join-Path $ProjectRoot "portal_auth.env"),
        (Join-Path $PSScriptRoot "portal_auth.env"),
        (Join-Path $ProjectRoot ".env.portal"),
        (Join-Path $PSScriptRoot ".env.portal"),
        (Join-Path $ProjectRoot ".env")
    )
    foreach ($file in $authFiles) {
        if (Import-EnvFile -FilePath $file) { break }
    }
}

Write-Host "Starting Athena V5 browser adapter..."
Write-Host "mode=$ResolvedMode host=$($env:ATHENA_PORTAL_HOST) port=$Port path_prefix=$PathPrefix load_model=$($env:ATHENA_WEB_LOAD_MODEL) tools=$($env:ATHENA_TOOLS_ENABLED) auth=$($env:ATHENA_AUTH_REQUIRED)"

Set-Location $ProjectRoot

if ($ResolvedMode -eq "dev") {
    Write-Host "Open: http://127.0.0.1:$Port$PathPrefix"
    & $ResolvedPython $PortalScript
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $CloudflaredScript)) {
    throw "cloudflared_athenav5.ps1 not found: $CloudflaredScript"
}

$portalProc = Start-Process -FilePath $ResolvedPython -ArgumentList @($PortalScript) -WorkingDirectory $ProjectRoot -PassThru
Write-Host "Started portal_server.py (pid=$($portalProc.Id)). Waiting for health check..."

$healthUrl = "http://127.0.0.1:$Port/healthz"
$deadline = (Get-Date).AddSeconds(90)
$ok = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 800
    if ($portalProc.HasExited) {
        throw "portal_server.py exited early with code $($portalProc.ExitCode)."
    }
    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 3
        if ($resp.ok -eq $true) {
            $ok = $true
            break
        }
    } catch {
    }
}
if (-not $ok) {
    Stop-Process -Id $portalProc.Id -Force -ErrorAction SilentlyContinue
    throw "Health check timed out: $healthUrl"
}

try {
    $tunnelArgs = @{ Port = $Port; PathPrefix = $PathPrefix; Hostname = $Hostname }
    if ($QuickTunnel) { $tunnelArgs.QuickTunnel = $true }
    if ($CloudflaredExe -and $CloudflaredExe.Trim()) { $tunnelArgs.CloudflaredExe = $CloudflaredExe.Trim() }
    & $CloudflaredScript @tunnelArgs
    if ($LASTEXITCODE -ne 0) {
        throw "cloudflared exited with code $LASTEXITCODE"
    }
} finally {
    if (-not $portalProc.HasExited) {
        Stop-Process -Id $portalProc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped portal_server.py (pid=$($portalProc.Id))."
    }
}
