param(
  [string]$Hostname   = "portal.neohmlabs.com",
  [string]$LocalUrl   = "http://localhost:8000",
  [string]$TunnelName = "athena-v5-portal",
  [string]$PathPrefix = "/AthenaV5"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CFDLocal = Join-Path $ScriptDir "cloudflared.exe"
$CFDParent = "d:\AthenaPlayground\cloudflared.exe"
$CF = Join-Path $env:USERPROFILE ".cloudflared"
New-Item -ItemType Directory -Force -Path $CF | Out-Null

if (Test-Path -LiteralPath $CFDLocal) {
  $CFD = $CFDLocal
} elseif (Test-Path -LiteralPath $CFDParent) {
  $CFD = $CFDParent
} else {
  throw "cloudflared.exe not found. Place it in $ScriptDir or d:\AthenaPlayground."
}

& $CFD --version | Out-Host

Write-Host "`nMake sure the portal server is running first:"
Write-Host "  .\run_portal.ps1 -PathPrefix $PathPrefix -Port 8000"
Write-Host "Then open: https://$Hostname$PathPrefix"
Write-Host "Press Enter to continue..."
$null = Read-Host

if (-not (Test-Path (Join-Path $CF "cert.pem"))) {
  Write-Host "`nOpening browser for Cloudflare login..."
  & $CFD tunnel login
  Write-Host "After approving in the browser, press Enter..."
  $null = Read-Host
}

$tunnels = (& $CFD tunnel list) 2>$null
if (-not ($tunnels | Select-String -Pattern "^\s*$TunnelName\s" -SimpleMatch)) {
  Write-Host "`nCreating tunnel $TunnelName ..."
  & $CFD tunnel create $TunnelName
} else {
  Write-Host "Tunnel $TunnelName already exists."
}

$configPath = Join-Path $CF "config.yml"
@"
tunnel: $TunnelName
ingress:
  - hostname: $Hostname
    service: $LocalUrl
  - service: http_status:404
"@ | Set-Content -Encoding UTF8 $configPath
Write-Host "Wrote $configPath"

Write-Host "Routing DNS for $Hostname ..."
& $CFD tunnel route dns $TunnelName $Hostname

Write-Host "`nRunning tunnel. Open: https://$Hostname$PathPrefix"
& $CFD tunnel --config $configPath run $TunnelName
