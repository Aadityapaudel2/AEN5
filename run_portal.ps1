[CmdletBinding()]
param(
    [switch]$Tools,
    [bool]$LoadModel = $true,
    [int]$Port = 8000,
    [string]$PathPrefix = "/AEN5",
    [string]$Hostname = "portal.neohmlabs.com",
    [string]$TunnelName = "",
    [switch]$QuickTunnel,
    [string]$PythonExe = "",
    [string]$CloudflaredExe = "",
    [string]$AuthEnvFile = "",
    [switch]$PreflightOnly
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
if ($PreflightOnly) {
    $ResolvedPython = $PythonExe
    if (-not $ResolvedPython) {
        $Candidates = @(
            (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
            (Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe")
        )
        foreach ($Candidate in $Candidates) {
            if (Test-Path -LiteralPath $Candidate) {
                $ResolvedPython = $Candidate
                break
            }
        }
    }
    if (-not $ResolvedPython) {
        $Cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($Cmd) { $ResolvedPython = $Cmd.Source }
    }
    if (-not $ResolvedPython) {
        throw "python executable not found."
    }
    & $ResolvedPython (Join-Path $ProjectRoot "browser\public_runtime_preflight.py")
    exit $LASTEXITCODE
}
& (Join-Path $ProjectRoot "browser\run_browser.ps1") -Mode prod -Tools:$Tools -LoadModel:$LoadModel -Port $Port -PathPrefix $PathPrefix -Hostname $Hostname -TunnelName $TunnelName -QuickTunnel:$QuickTunnel -PythonExe $PythonExe -CloudflaredExe $CloudflaredExe -AuthEnvFile $AuthEnvFile
exit $LASTEXITCODE
