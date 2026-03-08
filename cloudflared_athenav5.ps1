[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$PathPrefix = "/AthenaV5",
    [string]$Hostname = "",
    [string]$TunnelName = "",
    [switch]$QuickTunnel,
    [string]$CloudflaredExe = ""
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ProjectRoot "browser\cloudflared_athenav5.ps1") -Port $Port -PathPrefix $PathPrefix -Hostname $Hostname -TunnelName $TunnelName -QuickTunnel:$QuickTunnel -CloudflaredExe $CloudflaredExe
exit $LASTEXITCODE
