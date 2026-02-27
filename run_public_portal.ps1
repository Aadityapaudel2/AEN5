[CmdletBinding()]
param(
    [switch]$LoadModel,
    [string]$PathPrefix = "/AthenaV5",
    [int]$Port = 8787,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-PythonExe {
    param([string]$Root)
    $local = Join-Path $Root ".venv\Scripts\python.exe"
    $workspace = Join-Path (Split-Path -Parent $Root) ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $local) { return (Resolve-Path -LiteralPath $local).Path }
    if (Test-Path -LiteralPath $workspace) { return (Resolve-Path -LiteralPath $workspace).Path }
    return (Get-Command python -ErrorAction Stop).Source
}

function Resolve-CloudflaredExe {
    param([string]$Root)
    $candidates = @(
        (Join-Path $Root "cloudflared.exe"),
        "d:\AthenaPlayground\cloudflared.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
    }
    throw "cloudflared.exe not found. Place it in $Root or d:\AthenaPlayground."
}

$PythonExe = Resolve-PythonExe -Root $ProjectRoot
$CloudflaredExe = Resolve-CloudflaredExe -Root $ProjectRoot

$env:ATHENA_PORTAL_PATH_PREFIX = $PathPrefix
$env:ATHENA_PORTAL_PORT = [string]$Port
$env:ATHENA_WEB_LOAD_MODEL = if ($LoadModel) { "1" } else { "0" }

$HealthUrl = "http://127.0.0.1:$Port/healthz"
$LocalUrl = "http://127.0.0.1:$Port$PathPrefix"

Write-Host "Starting Athena V5 public quick-tunnel stack..."
Write-Host "python=$PythonExe"
Write-Host "cloudflared=$CloudflaredExe"
Write-Host "path_prefix=$PathPrefix port=$Port load_model=$($env:ATHENA_WEB_LOAD_MODEL)"

$serverProc = $null
try {
    $serverProc = Start-Process -FilePath $PythonExe -ArgumentList "portal_server.py" -WorkingDirectory $ProjectRoot -PassThru
    Write-Host "Started portal_server.py (pid=$($serverProc.Id)). Waiting for health check..."
    Start-Sleep -Milliseconds 300
    if ($serverProc.HasExited) {
        throw "portal_server.py exited immediately. Port $Port may already be in use."
    }

    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($serverProc.HasExited) {
            throw "portal_server.py exited before health check completed. Port $Port may already be in use."
        }
        try {
            $h = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
            if ($h.ok -eq $true) {
                $healthy = $true
                Write-Host ("healthz ok: " + ($h | ConvertTo-Json -Compress))
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $healthy) {
        throw "Portal server failed health check at $HealthUrl"
    }

    if (-not $NoBrowser) {
        Start-Process $LocalUrl | Out-Null
    }

    Write-Host ""
    Write-Host "Quick tunnel is starting. Wait for the line:"
    Write-Host "  Your quick Tunnel has been created! Visit it at ..."
    Write-Host "Then open that URL + $PathPrefix"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop both tunnel and portal server."
    # cloudflared writes normal logs to stderr; in newer PowerShell this can be
    # treated as terminating when ErrorActionPreference=Stop. Disable that behavior
    # for this native command so tunnel logs do not kill the launcher.
    $hadNativeErrPref = $false
    $prevNativeErrPref = $null
    try {
        if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
            $hadNativeErrPref = $true
            $prevNativeErrPref = $PSNativeCommandUseErrorActionPreference
            $PSNativeCommandUseErrorActionPreference = $false
        }
        & $CloudflaredExe tunnel --url "http://127.0.0.1:$Port"
        $tunnelExit = $LASTEXITCODE
        Write-Host "cloudflared exited with code $tunnelExit"
    }
    finally {
        if ($hadNativeErrPref) {
            $PSNativeCommandUseErrorActionPreference = $prevNativeErrPref
        }
    }
}
finally {
    if ($serverProc -and -not $serverProc.HasExited) {
        Stop-Process -Id $serverProc.Id -Force
        Write-Host "Stopped portal_server.py (pid=$($serverProc.Id))."
    }
}
