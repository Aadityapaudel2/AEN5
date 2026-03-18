[CmdletBinding()]
param(
    [ValidateSet("dev", "prod", "local")]
    [string]$Mode = "dev",
    [switch]$Tools,
    [bool]$LoadModel = $true,
    [int]$Port = 8000,
    [string]$PathPrefix = "/AEN5",
    [string]$Hostname = "portal.neohmlabs.com",
    [string]$TunnelName = "",
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
$BrowserConfigRoot = Join-Path $PSScriptRoot "config"
$SharedRuntimeEnvFile = Join-Path $ProjectRoot ".local\runtime\vllm_runtime.env"
$SharedVllmLauncher = Join-Path $ProjectRoot "run_vllm.ps1"
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

$null = Import-EnvFile -FilePath $SharedRuntimeEnvFile

function Resolve-VllmModelDir {
    $candidates = @(
        $env:ATHENA_VLLM_MODEL_DIR,
        $env:ATHENA_CHAT_MODEL_DIR,
        (Join-Path $ProjectRoot "models\Qwen3.5-4B")
    )
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "No local model directory was found for the public vLLM runtime. Set ATHENA_VLLM_MODEL_DIR or ATHENA_CHAT_MODEL_DIR."
}

function Resolve-VllmEndpoint {
    $baseUrl = ($env:ATHENA_VLLM_BASE_URL -as [string])
    if (-not $baseUrl -or -not $baseUrl.Trim()) {
        $baseUrl = "http://127.0.0.1:8001/v1"
        $env:ATHENA_VLLM_BASE_URL = $baseUrl
    }
    $uri = [Uri]$baseUrl
    return @{
        BaseUrl = $uri.GetLeftPart([System.UriPartial]::Authority) + $uri.AbsolutePath.TrimEnd("/")
        Host = $uri.Host
        Port = $uri.Port
        ModelsUrl = ($uri.GetLeftPart([System.UriPartial]::Authority) + $uri.AbsolutePath.TrimEnd("/") + "/models")
    }
}

function Get-VllmAuthHeaders {
    if ($env:ATHENA_VLLM_API_KEY -and $env:ATHENA_VLLM_API_KEY.Trim()) {
        return @{ Authorization = "Bearer $($env:ATHENA_VLLM_API_KEY.Trim())" }
    }
    return @{}
}

function Wait-HttpJson {
    param(
        [string]$Url,
        [hashtable]$Headers = @{},
        [int]$TimeoutSeconds = 120,
        [System.Diagnostics.Process]$OwnedProcess
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 900
        if ($OwnedProcess -and $OwnedProcess.HasExited) {
            throw "Process exited early with code $($OwnedProcess.ExitCode): $Url"
        }
        try {
            return Invoke-RestMethod -Uri $Url -Method Get -Headers $Headers -TimeoutSec 5
        } catch {
        }
    }
    throw "Timed out waiting for $Url"
}

function Invoke-SharedVllmBootstrap {
    param(
        [string]$ResolvedModelDir,
        [string]$ResolvedPython
    )
    if (-not (Test-Path -LiteralPath $SharedVllmLauncher)) {
        throw "Shared vLLM launcher not found: $SharedVllmLauncher"
    }
    $launcherArgs = @{}
    if ($ResolvedModelDir -and $ResolvedModelDir.Trim()) {
        $launcherArgs.ModelDir = $ResolvedModelDir
    }
    if ($env:ATHENA_VLLM_MODEL -and $env:ATHENA_VLLM_MODEL.Trim()) {
        $launcherArgs.ServedModelName = $env:ATHENA_VLLM_MODEL.Trim()
    }
    if ($env:ATHENA_VLLM_BASE_URL -and $env:ATHENA_VLLM_BASE_URL.Trim()) {
        $launcherArgs.BaseUrl = $env:ATHENA_VLLM_BASE_URL.Trim()
    }
    if ($ResolvedPython -and $ResolvedPython.Trim()) {
        $launcherArgs.PythonExe = $ResolvedPython
    }
    & $SharedVllmLauncher @launcherArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Shared vLLM bootstrap failed with code $LASTEXITCODE."
    }
    $null = Import-EnvFile -FilePath $SharedRuntimeEnvFile
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
$env:ATHENA_RUNTIME_BACKEND = "vllm_openai"
$env:ATHENA_PUBLIC_VLLM_ONLY = "1"
if (-not $env:ATHENA_VLLM_API_KEY -or -not $env:ATHENA_VLLM_API_KEY.Trim()) {
    $env:ATHENA_VLLM_API_KEY = "athena-local"
}

if ($ResolvedMode -eq "prod" -and -not $LoadModel) {
    throw "Public prod launch requires -LoadModel:`$true because Athena V5 now runs on the vLLM sidecar."
}

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
        (Join-Path $BrowserConfigRoot "portal_auth.env"),
        (Join-Path $ProjectRoot "portal_auth.env"),
        (Join-Path $PSScriptRoot "portal_auth.env"),
        (Join-Path $BrowserConfigRoot ".env.portal"),
        (Join-Path $ProjectRoot ".env.portal"),
        (Join-Path $PSScriptRoot ".env.portal"),
        (Join-Path $ProjectRoot ".env")
    )
    foreach ($file in $authFiles) {
        if (Import-EnvFile -FilePath $file) { break }
    }
}

$ResolvedTunnelName = ""
if ($TunnelName -and $TunnelName.Trim()) {
    $ResolvedTunnelName = $TunnelName.Trim()
} elseif ($env:ATHENA_CLOUDFLARE_TUNNEL_NAME -and $env:ATHENA_CLOUDFLARE_TUNNEL_NAME.Trim()) {
    $ResolvedTunnelName = $env:ATHENA_CLOUDFLARE_TUNNEL_NAME.Trim()
}

if ($ResolvedMode -eq "prod" -and -not $QuickTunnel -and $Hostname -and -not $ResolvedTunnelName) {
    throw "Prod portal launch requires a named Cloudflare tunnel. Set ATHENA_CLOUDFLARE_TUNNEL_NAME in browser\config\portal_auth.env or pass -TunnelName."
}

$vllmProc = $null
$portalProc = $null
$ownsVllm = $false
$IsWindowsHost = ($env:OS -eq "Windows_NT")

try {
    Set-Location $ProjectRoot

    if ($LoadModel) {
        $modelDir = Resolve-VllmModelDir
        $env:ATHENA_CHAT_MODEL_DIR = $modelDir
        if (-not $env:ATHENA_VLLM_MODEL -or -not $env:ATHENA_VLLM_MODEL.Trim()) {
            $env:ATHENA_VLLM_MODEL = Split-Path -Leaf $modelDir
        }

        if ($IsWindowsHost) {
            Invoke-SharedVllmBootstrap -ResolvedModelDir $modelDir -ResolvedPython $ResolvedPython
        }

        $endpoint = Resolve-VllmEndpoint
        $modelsUrl = $endpoint.ModelsUrl
        $vllmHeaders = Get-VllmAuthHeaders
        $vllmHealthy = $false
        $modelsPayload = $null
        try {
            $modelsPayload = Invoke-RestMethod -Uri $modelsUrl -Method Get -Headers $vllmHeaders -TimeoutSec 5
            if ($modelsPayload) { $vllmHealthy = $true }
        } catch {
        }

        if (-not $vllmHealthy) {
            if ($IsWindowsHost) {
                throw "No healthy vLLM endpoint was found at $modelsUrl after shared bootstrap. Review .local\\runtime\\vllm_stdout.log and .local\\runtime\\vllm_stderr.log."
            }
            Write-Host "Starting public vLLM sidecar..."
            $vllmArgs = @(
                "-m",
                "vllm.entrypoints.openai.api_server",
                "--host", $endpoint.Host,
                "--port", [string]$endpoint.Port,
                "--model", $modelDir,
                "--served-model-name", $env:ATHENA_VLLM_MODEL,
                "--api-key", $env:ATHENA_VLLM_API_KEY,
                "--trust-remote-code"
            )
            $vllmProc = Start-Process -FilePath $ResolvedPython -ArgumentList $vllmArgs -WorkingDirectory $ProjectRoot -PassThru
            $ownsVllm = $true
            Write-Host "Started vLLM (pid=$($vllmProc.Id)). Waiting for $modelsUrl ..."
            $modelsPayload = Wait-HttpJson -Url $modelsUrl -Headers $vllmHeaders -TimeoutSeconds 240 -OwnedProcess $vllmProc
        } else {
            Write-Host "Reusing healthy vLLM server at $modelsUrl"
        }

        if ($modelsPayload -and $modelsPayload.data -and $modelsPayload.data.Count -gt 0 -and $modelsPayload.data[0].id) {
            $env:ATHENA_VLLM_MODEL = [string]$modelsPayload.data[0].id
        }
    }

    Write-Host "Starting Athena V5 browser adapter..."
    Write-Host "mode=$ResolvedMode host=$($env:ATHENA_PORTAL_HOST) port=$Port path_prefix=$PathPrefix load_model=$($env:ATHENA_WEB_LOAD_MODEL) tools=$($env:ATHENA_TOOLS_ENABLED) auth=$($env:ATHENA_AUTH_REQUIRED) runtime=$($env:ATHENA_RUNTIME_BACKEND) tunnel=$ResolvedTunnelName"

    $portalProc = Start-Process -FilePath $ResolvedPython -ArgumentList @($PortalScript) -WorkingDirectory $ProjectRoot -PassThru
    Write-Host "Started portal_server.py (pid=$($portalProc.Id)). Waiting for health check..."

    $healthUrl = "http://127.0.0.1:$Port/healthz"
    $resp = Wait-HttpJson -Url $healthUrl -TimeoutSeconds 120 -OwnedProcess $portalProc
    if (-not $resp.ok) {
        throw "Portal health check failed: $healthUrl"
    }

    if ($ResolvedMode -eq "dev") {
        Write-Host "Open: http://127.0.0.1:$Port$PathPrefix"
        Wait-Process -Id $portalProc.Id
        exit $portalProc.ExitCode
    }

    if (-not (Test-Path -LiteralPath $CloudflaredScript)) {
        throw "cloudflared_athenav5.ps1 not found: $CloudflaredScript"
    }

    $tunnelArgs = @{ Port = $Port; PathPrefix = $PathPrefix; Hostname = $Hostname }
    if ($ResolvedTunnelName) { $tunnelArgs.TunnelName = $ResolvedTunnelName }
    if ($QuickTunnel) { $tunnelArgs.QuickTunnel = $true }
    if ($CloudflaredExe -and $CloudflaredExe.Trim()) { $tunnelArgs.CloudflaredExe = $CloudflaredExe.Trim() }
    & $CloudflaredScript @tunnelArgs
    if ($LASTEXITCODE -ne 0) {
        throw "cloudflared exited with code $LASTEXITCODE"
    }
}
finally {
    if ($portalProc -and -not $portalProc.HasExited) {
        Stop-Process -Id $portalProc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped portal_server.py (pid=$($portalProc.Id))."
    }
    if ($ownsVllm -and $vllmProc -and -not $vllmProc.HasExited) {
        Stop-Process -Id $vllmProc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped vLLM sidecar (pid=$($vllmProc.Id))."
    }
}
