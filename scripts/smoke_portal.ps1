[CmdletBinding()]
param(
    [string]$PathPrefix = "/AthenaV5",
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = "d:\AthenaPlayground\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python not found at $PythonExe"
}

$env:ATHENA_WEB_LOAD_MODEL = "0"
$env:ATHENA_PORTAL_PATH_PREFIX = $PathPrefix
$env:ATHENA_PORTAL_PORT = [string]$Port

$proc = Start-Process -FilePath $PythonExe -ArgumentList "portal_server.py" -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 3
    if ($proc.HasExited) {
        throw "portal_server.py exited early. Port $Port may already be in use."
    }

    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/healthz"
    $indexCode = & curl.exe -s -o NUL -w "%{http_code}" "http://127.0.0.1:$Port$PathPrefix"
    $chat = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port$PathPrefix/api/chat" -ContentType "application/json" -Body '{"prompt":"smoke test","history":[],"enable_thinking":false,"show_thoughts":false}'

    if (-not $health.ok) { throw "healthz not ok" }
    if ($indexCode -ne "200") { throw "index status was $indexCode" }
    if (-not $chat.smoke_mode) { throw "chat endpoint was not in smoke mode" }
    if ([string]::IsNullOrWhiteSpace($chat.assistant)) { throw "chat assistant response empty" }

    Write-Host "smoke_portal: PASS"
    Write-Host ("healthz=" + ($health | ConvertTo-Json -Compress))
    Write-Host ("index_status=" + $indexCode)
    Write-Host ("chat_preview=" + $chat.assistant.Substring(0, [Math]::Min(90, $chat.assistant.Length)))
} finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
}
