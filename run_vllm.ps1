[CmdletBinding()]
param(
    [string]$ModelDir = "",
    [string]$ServedModelName = "",
    [string]$BaseUrl = "",
    [string]$RuntimeName = "shared",
    [int]$Port = 8001,
    [int]$MaxModelLen = 8192,
    [double]$GpuMemoryUtilization = 0.9,
    [string]$BindHost = "0.0.0.0",
    [string]$ApiKey = "athena-local",
    [string]$PythonExe = "",
    [string]$LinuxPython = "python3",
    [string]$LinuxModelDir = "",
    [string]$WslDistro = "",
    [switch]$Status,
    [switch]$Stop,
    [switch]$Restart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $ProjectRoot ".local\runtime"
$ResolvedRuntimeName = ($RuntimeName -as [string])
if ($null -eq $ResolvedRuntimeName) { $ResolvedRuntimeName = "shared" }
$ResolvedRuntimeName = $ResolvedRuntimeName.Trim().ToLowerInvariant()
if (-not $ResolvedRuntimeName) { $ResolvedRuntimeName = "shared" }
if ($ResolvedRuntimeName -notmatch '^[a-z0-9_\\-]+$') {
    throw "RuntimeName '$RuntimeName' is invalid. Use only letters, numbers, underscore, or dash."
}
$RuntimeSuffix = if ($ResolvedRuntimeName -eq "shared") { "" } else { "_$ResolvedRuntimeName" }
$RuntimeEnvPath = Join-Path $RuntimeRoot ("vllm{0}_runtime.env" -f $RuntimeSuffix)
$RuntimeStatePath = Join-Path $RuntimeRoot ("vllm{0}_runtime.json" -f $RuntimeSuffix)
$StdoutLogPath = Join-Path $RuntimeRoot ("vllm{0}_stdout.log" -f $RuntimeSuffix)
$StderrLogPath = Join-Path $RuntimeRoot ("vllm{0}_stderr.log" -f $RuntimeSuffix)
$WslProbeStdoutLogPath = Join-Path $RuntimeRoot ("wsl_probe{0}_stdout.log" -f $RuntimeSuffix)
$WslProbeStderrLogPath = Join-Path $RuntimeRoot ("wsl_probe{0}_stderr.log" -f $RuntimeSuffix)
$WslProbeScriptPath = Join-Path $RuntimeRoot ("wsl_probe{0}.py" -f $RuntimeSuffix)
$IsWindowsHost = ($env:OS -eq "Windows_NT")

function Initialize-AthenaVllmRuntimeRoot {
    if (-not (Test-Path -LiteralPath $RuntimeRoot)) {
        New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    }
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

function Resolve-ModelDir {
    param([string]$ExplicitPath)
    $candidates = @()
    if ($ExplicitPath -and $ExplicitPath.Trim()) {
        $candidates += $ExplicitPath.Trim()
    }
    if ($env:ATHENA_VLLM_MODEL_DIR -and $env:ATHENA_VLLM_MODEL_DIR.Trim()) {
        $candidates += $env:ATHENA_VLLM_MODEL_DIR.Trim()
    }
    if ($env:ATHENA_CHAT_MODEL_DIR -and $env:ATHENA_CHAT_MODEL_DIR.Trim()) {
        $candidates += $env:ATHENA_CHAT_MODEL_DIR.Trim()
    }
    $candidates += @(
        (Join-Path $ProjectRoot "models\Qwen3.5-4B"),
        (Join-Path $ProjectRoot "models\Qwen3.5-8B"),
        (Join-Path $ProjectRoot "models\Qwen3.5-14B")
    )
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        $resolvedCandidate = if ([System.IO.Path]::IsPathRooted($candidate)) { $candidate } else { Join-Path $ProjectRoot $candidate }
        if (Test-Path -LiteralPath $resolvedCandidate) {
            return (Resolve-Path -LiteralPath $resolvedCandidate).Path
        }
    }
    throw "No local model directory was found. Pass -ModelDir or set ATHENA_VLLM_MODEL_DIR."
}

function Resolve-BaseUrl {
    param([string]$ExplicitBaseUrl, [int]$DefaultPort)
    if ($ExplicitBaseUrl -and $ExplicitBaseUrl.Trim()) {
        return ([string]$ExplicitBaseUrl).Trim().TrimEnd("/")
    }
    if ($env:ATHENA_VLLM_BASE_URL -and $env:ATHENA_VLLM_BASE_URL.Trim()) {
        return ([string]$env:ATHENA_VLLM_BASE_URL).Trim().TrimEnd("/")
    }
    return "http://127.0.0.1:$DefaultPort/v1"
}

function Get-ModelsUrl {
    param([string]$BaseUrl)
    return ($BaseUrl.TrimEnd("/") + "/models")
}

function Get-VllmAuthHeaders {
    param([string]$ResolvedApiKey)
    if ($ResolvedApiKey -and $ResolvedApiKey.Trim()) {
        return @{ Authorization = "Bearer $($ResolvedApiKey.Trim())" }
    }
    return @{}
}

function Test-VllmEndpoint {
    param(
        [string]$ModelsUrl,
        [string]$ResolvedApiKey = ""
    )
    try {
        $headers = Get-VllmAuthHeaders -ResolvedApiKey $ResolvedApiKey
        $payload = Invoke-RestMethod -Uri $ModelsUrl -Method Get -Headers $headers -TimeoutSec 5
        if ($payload -and $payload.data) {
            return $payload
        }
    } catch {
    }
    return $null
}

function Read-LogSnippet {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath)) { return "" }
    try {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        if (-not $bytes -or $bytes.Length -eq 0) { return "" }
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)
        if ($text.IndexOf([char]0) -ge 0) {
            $text = [System.Text.Encoding]::Unicode.GetString($bytes)
        }
        $lines = $text -split "(`r`n|`n|`r)" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
        if (-not $lines) { return "" }
        return (($lines | Select-Object -Last 12) -join " | ").Trim()
    } catch {
        return ""
    }
}

function Wait-VllmEndpoint {
    param(
        [string]$ModelsUrl,
        [string]$ResolvedApiKey = "",
        [int]$TimeoutSeconds,
        [System.Diagnostics.Process]$OwnedProcess
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 900
        if ($OwnedProcess -and $OwnedProcess.HasExited) {
            $stdoutSnippet = Read-LogSnippet -FilePath $StdoutLogPath
            $stderrSnippet = Read-LogSnippet -FilePath $StderrLogPath
            $detail = if ($stderrSnippet) { $stderrSnippet } elseif ($stdoutSnippet) { $stdoutSnippet } else { "No launcher output was captured." }
            throw "vLLM launcher exited early with code $($OwnedProcess.ExitCode). $detail Review $StdoutLogPath and $StderrLogPath."
        }
        $payload = Test-VllmEndpoint -ModelsUrl $ModelsUrl -ResolvedApiKey $ResolvedApiKey
        if ($payload) { return $payload }
    }
    throw "Timed out waiting for vLLM endpoint: $ModelsUrl"
}

function Invoke-VllmWarmup {
    param(
        [string]$BaseUrl,
        [string]$ResolvedApiKey,
        [string]$ResolvedServedModelName,
        [int]$TimeoutSeconds = 60
    )
    $headers = Get-VllmAuthHeaders -ResolvedApiKey $ResolvedApiKey
    $headers['Accept'] = 'application/json'
    $body = @{
        model = $ResolvedServedModelName
        messages = @(
            @{ role = 'system'; content = 'Reply with OK only.' },
            @{ role = 'user'; content = 'warmup' }
        )
        stream = $false
        max_tokens = 8
        temperature = 0.0
        chat_template_kwargs = @{ enable_thinking = $false }
    } | ConvertTo-Json -Depth 6
    try {
        $null = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd('/') + '/chat/completions') -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec $TimeoutSeconds
        return $true
    } catch {
        Write-Warning ("vLLM warmup request failed: " + $_.Exception.Message)
        return $false
    }
}

function Convert-ToWslPath {
    param([string]$WindowsPath)
    $full = [System.IO.Path]::GetFullPath($WindowsPath)
    $normalized = $full -replace '\\', '/'
    if ($normalized -match '^([A-Za-z]):/(.*)$') {
        return "/mnt/$($matches[1].ToLowerInvariant())/$($matches[2])"
    }
    throw "Could not convert Windows path to WSL path: $WindowsPath"
}

function Get-WslHomeDirectory {
    param(
        [string]$WslExe,
        [string]$Distro
    )
    $homeOutput = & $WslExe -d $Distro -- bash -lc 'printf "%s" "$HOME"' 2>&1
    if ($LASTEXITCODE -ne 0) {
        $detail = (($homeOutput | ForEach-Object { [string]$_ }) -join " ").Trim()
        if (-not $detail) { $detail = "Could not determine WSL home directory." }
        throw "Failed to resolve the WSL home directory for '$Distro'. $detail"
    }
    $homeDir = (($homeOutput | ForEach-Object { [string]$_ }) -join "").Trim()
    if (-not $homeDir) {
        throw "WSL home directory for '$Distro' was empty."
    }
    return $homeDir
}

function Test-WslExecutablePath {
    param(
        [string]$WslExe,
        [string]$Distro,
        [string]$LinuxPath
    )
    if (-not $LinuxPath -or -not $LinuxPath.Trim()) { return $false }
    & $WslExe -d $Distro --exec test -x $LinuxPath
    return ($LASTEXITCODE -eq 0)
}

function Resolve-LinuxPython {
    param(
        [string]$ExplicitPath,
        [string]$WslExe,
        [string]$Distro
    )
    if ($ExplicitPath -and $ExplicitPath.Trim() -and $ExplicitPath.Trim() -ne "python3") {
        return $ExplicitPath.Trim()
    }
    if ($WslExe -and $Distro) {
        $homeDir = Get-WslHomeDirectory -WslExe $WslExe -Distro $Distro
        $linuxCandidates = @(
            "$homeDir/.athena_vllm/bin/python",
            "$homeDir/.venvs/athena-vllm/bin/python",
            "$homeDir/.venvs/athena-v5-vllm/bin/python"
        )
        foreach ($candidate in $linuxCandidates) {
            if (Test-WslExecutablePath -WslExe $WslExe -Distro $Distro -LinuxPath $candidate) {
                return $candidate
            }
        }
    }
    $candidates = @(
        (Join-Path $ProjectRoot ".wsl_venv\bin\python"),
        (Join-Path $ProjectRoot ".venv-wsl\bin\python"),
        (Join-Path $ProjectRoot ".venv_linux\bin\python")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Convert-ToWslPath -WindowsPath $candidate)
        }
    }
    if ($env:ATHENA_WSL_PYTHON -and $env:ATHENA_WSL_PYTHON.Trim()) {
        return $env:ATHENA_WSL_PYTHON.Trim()
    }
    if ($ExplicitPath -and $ExplicitPath.Trim()) {
        return $ExplicitPath.Trim()
    }
    return "python3"
}

function Resolve-WslDistro {
    param([string]$ExplicitDistro)
    if ($ExplicitDistro -and $ExplicitDistro.Trim()) {
        return $ExplicitDistro.Trim()
    }
    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wsl) {
        throw "wsl.exe was not found. Install WSL or start a Linux vLLM endpoint manually."
    }
    $raw = & $wsl.Source -l -q 2>&1
    $exitCode = $LASTEXITCODE
    $rawText = (($raw | ForEach-Object { [string]$_ }) -join " ").Trim()
    if ($exitCode -ne 0) {
        $cleaned = ($rawText -replace "\x00", "").Trim()
        if (-not $cleaned) { $cleaned = "wsl.exe -l -q failed." }
        throw "WSL is installed but could not be queried from this shell. $cleaned"
    }
    $distros = @()
    foreach ($line in $raw) {
        $name = [string]$line
        if (-not $name) { continue }
        $trimmed = ($name -replace "\x00", "").Trim()
        if (-not $trimmed) { continue }
        if ($trimmed -match 'access is denied|error code:') { continue }
        if ($trimmed -match '^docker-desktop(?:-data)?$') { continue }
        $distros += $trimmed
    }
    if ($distros.Count -gt 0) {
        return $distros[0]
    }
    throw "No regular WSL Linux distro was found. Only Docker-managed WSL distributions are installed. Install a distro such as Ubuntu (`wsl --install -d Ubuntu`) or start vLLM on another Linux host and set ATHENA_VLLM_BASE_URL."
}

function ConvertTo-BashLiteral {
    param([string]$Value)
    if ($null -eq $Value) { return "''" }
    $replacement = "'" + '"' + "'" + '"' + "'"
    return "'" + ($Value -replace "'", $replacement) + "'"
}

function Stop-UnmanagedLocalWslVllm {
    param(
        [string]$WslExe,
        [string]$Distro,
        [int]$TargetPort
    )
    if (-not $WslExe -or -not $Distro -or $TargetPort -le 0) {
        return $false
    }
    $killCommand = "if command -v fuser >/dev/null 2>&1; then fuser -k ${TargetPort}/tcp; else pkill -f 'vllm.entrypoints.openai.api_server.*--port ${TargetPort}'; fi"
    & $WslExe -d $Distro --exec bash -lc $killCommand 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Assert-WslRuntimeReady {
    param(
        [string]$WslExe,
        [string]$Distro,
        [string]$LinuxPython
    )
    Initialize-AthenaVllmRuntimeRoot
    @'
import importlib.util
import sys

ready = importlib.util.find_spec("vllm") is not None
print("ATHENA_WSL_READY" if ready else "ATHENA_VLLM_MISSING")
sys.exit(0 if ready else 7)
'@ | Set-Content -LiteralPath $WslProbeScriptPath -Encoding utf8
    $linuxProbeScriptPath = Convert-ToWslPath -WindowsPath $WslProbeScriptPath
    Remove-Item -LiteralPath $WslProbeStdoutLogPath, $WslProbeStderrLogPath -Force -ErrorAction SilentlyContinue
    $probeArgs = @("-d", $Distro, "--exec", "timeout", "20s", $LinuxPython, $linuxProbeScriptPath)
    $probeProc = Start-Process -FilePath $WslExe -ArgumentList $probeArgs -WorkingDirectory $ProjectRoot -RedirectStandardOutput $WslProbeStdoutLogPath -RedirectStandardError $WslProbeStderrLogPath -WindowStyle Hidden -PassThru
    if (-not $probeProc.WaitForExit(25000)) {
        Stop-Process -Id $probeProc.Id -Force -ErrorAction SilentlyContinue
        throw "WSL distro '$Distro' did not become ready in time. If this is the first Ubuntu launch, run `wsl -d $Distro` once in a normal terminal, complete the initial setup, then rerun .\run_portal.ps1."
    }
    $stdoutSnippet = Read-LogSnippet -FilePath $WslProbeStdoutLogPath
    $stderrSnippet = Read-LogSnippet -FilePath $WslProbeStderrLogPath
    if ($stdoutSnippet -match 'ATHENA_WSL_READY') {
        return
    }
    if ($probeProc.ExitCode -eq 124) {
        throw "WSL distro '$Distro' did not become ready in time. If this is the first Ubuntu launch, run `wsl -d $Distro` once in a normal terminal, complete the initial setup, then rerun .\run_portal.ps1."
    }
    if ($probeProc.ExitCode -ne 0) {
        $detail = if ($stderrSnippet) { $stderrSnippet } elseif ($stdoutSnippet) { $stdoutSnippet } else { "No WSL probe output was captured." }
        throw "WSL distro '$Distro' is reachable, but the Python/vLLM probe failed. $detail Open Ubuntu and ensure Python plus vLLM are installed, then rerun .\run_portal.ps1."
    }
    if ($stdoutSnippet -notmatch 'ATHENA_WSL_READY') {
        $detail = if ($stdoutSnippet) { $stdoutSnippet } elseif ($stderrSnippet) { $stderrSnippet } else { "No WSL probe output was captured." }
        throw "WSL distro '$Distro' returned unexpected probe output. $detail"
    }
}

function Read-RuntimeState {
    if (-not (Test-Path -LiteralPath $RuntimeStatePath)) { return $null }
    try {
        return Get-Content -LiteralPath $RuntimeStatePath -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Write-RuntimeState {
    param([hashtable]$State)
    Initialize-AthenaVllmRuntimeRoot
    ($State | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $RuntimeStatePath -Encoding utf8
}

function Write-RuntimeEnv {
    param(
        [string]$BaseUrl,
        [string]$ResolvedModelDir,
        [string]$ResolvedServedModelName,
        [string]$ResolvedApiKey,
        [int]$ResolvedMaxModelLen,
        [bool]$EnableThinking = $false
    )
    Initialize-AthenaVllmRuntimeRoot
    $lines = @(
        "ATHENA_RUNTIME_BACKEND=vllm_openai"
        "ATHENA_VLLM_BASE_URL=$BaseUrl"
        "ATHENA_VLLM_MODEL_DIR=$ResolvedModelDir"
        "ATHENA_VLLM_MODEL=$ResolvedServedModelName"
        "ATHENA_VLLM_API_KEY=$ResolvedApiKey"
        "ATHENA_VLLM_MAX_CONTEXT_TOKENS=$ResolvedMaxModelLen"
        "ATHENA_VLLM_ENABLE_THINKING=$([int]$EnableThinking)"
    )
    $lines | Set-Content -LiteralPath $RuntimeEnvPath -Encoding utf8
    $env:ATHENA_RUNTIME_BACKEND = "vllm_openai"
    $env:ATHENA_VLLM_BASE_URL = $BaseUrl
    $env:ATHENA_VLLM_MODEL_DIR = $ResolvedModelDir
    $env:ATHENA_VLLM_MODEL = $ResolvedServedModelName
    $env:ATHENA_VLLM_API_KEY = $ResolvedApiKey
    $env:ATHENA_VLLM_MAX_CONTEXT_TOKENS = [string]$ResolvedMaxModelLen
    $env:ATHENA_VLLM_ENABLE_THINKING = [string]([int]$EnableThinking)
}

function Stop-ManagedVllm {
    $state = Read-RuntimeState
    if ($null -eq $state) {
        Write-Host "No managed vLLM state file found."
        if (Test-Path -LiteralPath $RuntimeEnvPath) {
            Remove-Item -LiteralPath $RuntimeEnvPath -Force -ErrorAction SilentlyContinue
        }
        return $false
    }
    $stopped = $false
    $pidValue = 0
    try { $pidValue = [int]$state.pid } catch { $pidValue = 0 }
    if ($pidValue -gt 0) {
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped managed vLLM launcher pid=$pidValue"
            $stopped = $true
        }
    }
    Remove-Item -LiteralPath $RuntimeStatePath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $RuntimeEnvPath -Force -ErrorAction SilentlyContinue
    return $stopped
}

function Show-Status {
    param(
        [string]$BaseUrl,
        [string]$ResolvedApiKey = ""
    )
    $modelsUrl = Get-ModelsUrl -BaseUrl $BaseUrl
    $state = Read-RuntimeState
    $payload = Test-VllmEndpoint -ModelsUrl $modelsUrl -ResolvedApiKey $ResolvedApiKey
    Write-Host "vLLM status"
    Write-Host "base_url=$BaseUrl"
    Write-Host "models_url=$modelsUrl"
    Write-Host "healthy=$([bool]($null -ne $payload))"
    if ($payload -and $payload.data -and $payload.data.Count -gt 0) {
        Write-Host "served_model=$($payload.data[0].id)"
    }
    if ($state) {
        Write-Host "managed_pid=$($state.pid)"
        Write-Host "launcher=$($state.launcher)"
        Write-Host "model_dir=$($state.model_dir)"
        Write-Host "stdout_log=$($state.stdout_log)"
        Write-Host "stderr_log=$($state.stderr_log)"
    }
}

$null = Import-EnvFile -FilePath $RuntimeEnvPath

$ResolvedBaseUrl = Resolve-BaseUrl -ExplicitBaseUrl $BaseUrl -DefaultPort $Port
$ResolvedBaseUri = [Uri]$ResolvedBaseUrl
$ResolvedPort = if ($ResolvedBaseUri.Port -gt 0) { [int]$ResolvedBaseUri.Port } else { $Port }
$ModelsUrl = Get-ModelsUrl -BaseUrl $ResolvedBaseUrl
$ResolvedApiKey = if ($ApiKey -and $ApiKey.Trim()) { $ApiKey.Trim() } elseif ($env:ATHENA_VLLM_API_KEY -and $env:ATHENA_VLLM_API_KEY.Trim()) { $env:ATHENA_VLLM_API_KEY.Trim() } else { "athena-local" }

if ($Status) {
    Show-Status -BaseUrl $ResolvedBaseUrl -ResolvedApiKey $ResolvedApiKey
    exit 0
}

if ($Stop) {
    $null = Stop-ManagedVllm
    exit 0
}

if ($Restart) {
    $null = Stop-ManagedVllm
}

$ResolvedModelDir = Resolve-ModelDir -ExplicitPath $ModelDir
$ResolvedServedModelName = if ($ServedModelName -and $ServedModelName.Trim()) { $ServedModelName.Trim() } else { Split-Path -Leaf $ResolvedModelDir }
$ResolvedMaxModelLen = if ($env:ATHENA_VLLM_MAX_MODEL_LEN -and $env:ATHENA_VLLM_MAX_MODEL_LEN.Trim()) { [int]$env:ATHENA_VLLM_MAX_MODEL_LEN } else { $MaxModelLen }
$ResolvedGpuMemoryUtilization = if ($env:ATHENA_VLLM_GPU_MEMORY_UTILIZATION -and $env:ATHENA_VLLM_GPU_MEMORY_UTILIZATION.Trim()) { [double]$env:ATHENA_VLLM_GPU_MEMORY_UTILIZATION } else { $GpuMemoryUtilization }
$ResolvedBootTimeoutSeconds = if ($env:ATHENA_VLLM_BOOT_TIMEOUT_SECONDS -and $env:ATHENA_VLLM_BOOT_TIMEOUT_SECONDS.Trim()) {
    [int]$env:ATHENA_VLLM_BOOT_TIMEOUT_SECONDS
} elseif ($ResolvedRuntimeName -eq "private") {
    900
} else {
    240
}

$stateBeforeHealthyCheck = Read-RuntimeState
$healthyPayload = Test-VllmEndpoint -ModelsUrl $ModelsUrl -ResolvedApiKey $ResolvedApiKey
if ($healthyPayload) {
    $activeServedModelName = ""
    $activeModelRoot = ""
    if ($healthyPayload.data -and $healthyPayload.data.Count -gt 0 -and $healthyPayload.data[0].id) {
        $activeServedModelName = [string]$healthyPayload.data[0].id
    }
    if ($healthyPayload.data -and $healthyPayload.data.Count -gt 0 -and $healthyPayload.data[0].root) {
        $activeModelRoot = [string]$healthyPayload.data[0].root
    }
    $managedModelDirMatches = $false
    $canTrustManagedModelDir = $false
    if ($stateBeforeHealthyCheck -and $stateBeforeHealthyCheck.model_dir) {
        try {
            $managedModelDirMatches = ([System.IO.Path]::GetFullPath([string]$stateBeforeHealthyCheck.model_dir) -ieq [System.IO.Path]::GetFullPath($ResolvedModelDir))
            $canTrustManagedModelDir = $true
        } catch {
            $managedModelDirMatches = $false
            $canTrustManagedModelDir = $false
        }
    }
    if (-not $canTrustManagedModelDir -and $activeModelRoot) {
        try {
            $activeModelRootWindows = if ($activeModelRoot -match '^/mnt/([a-z])/(.+)$') {
                $driveLetter = $matches[1].ToUpperInvariant()
                ($driveLetter + ":\\" + ($matches[2] -replace '/', '\'))
            } else {
                $activeModelRoot
            }
            $managedModelDirMatches = ([System.IO.Path]::GetFullPath($activeModelRootWindows) -ieq [System.IO.Path]::GetFullPath($ResolvedModelDir))
            $canTrustManagedModelDir = $true
        } catch {
            $managedModelDirMatches = $false
            $canTrustManagedModelDir = $false
        }
    }
    $servedModelMatches = ($activeServedModelName -and ($activeServedModelName -eq $ResolvedServedModelName))
    $shouldRestartManagedEndpoint = $false
    if ($canTrustManagedModelDir) {
        $shouldRestartManagedEndpoint = (-not $managedModelDirMatches) -or (-not $servedModelMatches)
    } elseif (-not $servedModelMatches) {
        $shouldRestartManagedEndpoint = $true
    }
    if ($shouldRestartManagedEndpoint) {
        if ($stateBeforeHealthyCheck) {
            Write-Host "Managed vLLM endpoint is serving '$activeServedModelName' from '$($stateBeforeHealthyCheck.model_dir)'. Restarting for '$ResolvedServedModelName' from '$ResolvedModelDir'."
            $null = Stop-ManagedVllm
            $healthyPayload = $null
        } else {
            $handledLocalRestart = $false
            if ($Restart -and $IsWindowsHost -and $ResolvedBaseUri.Host -in @("127.0.0.1", "localhost")) {
                try {
                    $wsl = Get-Command wsl.exe -ErrorAction Stop
                    $ResolvedWslDistro = Resolve-WslDistro -ExplicitDistro $WslDistro
                    $handledLocalRestart = Stop-UnmanagedLocalWslVllm -WslExe $wsl.Source -Distro $ResolvedWslDistro -TargetPort $ResolvedPort
                } catch {
                    $handledLocalRestart = $false
                }
            }
            if ($handledLocalRestart) {
                Write-Host "Stopped unmanaged local vLLM listener on port $ResolvedPort before restart."
                Start-Sleep -Seconds 2
                $healthyPayload = $null
            } else {
                $reportedRoot = if ($activeModelRoot) { $activeModelRoot } else { "<unknown>" }
                throw "A healthy external vLLM endpoint already exists at $ModelsUrl, but it is serving '$activeServedModelName' from '$reportedRoot' instead of the requested '$ResolvedServedModelName' from '$ResolvedModelDir'. Stop that external endpoint or point ATHENA_VLLM_BASE_URL to another port."
            }
        }
    }
}
if ($healthyPayload) {
    if ($healthyPayload.data -and $healthyPayload.data.Count -gt 0 -and $healthyPayload.data[0].id) {
        $ResolvedServedModelName = [string]$healthyPayload.data[0].id
    }
    $null = Invoke-VllmWarmup -BaseUrl $ResolvedBaseUrl -ResolvedApiKey $ResolvedApiKey -ResolvedServedModelName $ResolvedServedModelName
    Write-RuntimeEnv -BaseUrl $ResolvedBaseUrl -ResolvedModelDir $ResolvedModelDir -ResolvedServedModelName $ResolvedServedModelName -ResolvedApiKey $ResolvedApiKey -ResolvedMaxModelLen $ResolvedMaxModelLen -EnableThinking $false
    Write-Host "Reusing healthy vLLM endpoint: $ModelsUrl"
    Write-Host "served_model=$ResolvedServedModelName"
    Write-Host "runtime_env=$RuntimeEnvPath"
    exit 0
}

$stateBeforeStart = Read-RuntimeState
if ($stateBeforeStart) {
    Write-Host "Removing stale managed vLLM state before restart..."
    $null = Stop-ManagedVllm
}

Initialize-AthenaVllmRuntimeRoot
Remove-Item -LiteralPath $StdoutLogPath, $StderrLogPath, $WslProbeStdoutLogPath, $WslProbeStderrLogPath -Force -ErrorAction SilentlyContinue

$launcherProc = $null
if ($IsWindowsHost) {
    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wsl) {
        throw "wsl.exe was not found. Install WSL or start a Linux vLLM endpoint manually."
    }
    $ResolvedWslDistro = Resolve-WslDistro -ExplicitDistro $WslDistro
    $ResolvedLinuxModelDir = if ($LinuxModelDir -and $LinuxModelDir.Trim()) { $LinuxModelDir.Trim() } else { Convert-ToWslPath -WindowsPath $ResolvedModelDir }
    $ResolvedLinuxPython = Resolve-LinuxPython -ExplicitPath $LinuxPython -WslExe $wsl.Source -Distro $ResolvedWslDistro
    Assert-WslRuntimeReady -WslExe $wsl.Source -Distro $ResolvedWslDistro -LinuxPython $ResolvedLinuxPython
    $ArgumentList = @()
    $ArgumentList += @("-d", $ResolvedWslDistro)
    $ArgumentList += @("--exec", $ResolvedLinuxPython, "-m", "vllm.entrypoints.openai.api_server")
    $ArgumentList += @("--host", $BindHost)
    $ArgumentList += @("--port", [string]$ResolvedPort)
    $ArgumentList += @("--model", $ResolvedLinuxModelDir)
    $ArgumentList += @("--served-model-name", $ResolvedServedModelName)
    $ArgumentList += @("--api-key", $ResolvedApiKey)
    $ArgumentList += @("--max-model-len", [string]$ResolvedMaxModelLen)
    $ArgumentList += @("--gpu-memory-utilization", [string]$ResolvedGpuMemoryUtilization)
    $ArgumentList += @("--enforce-eager")
    $ArgumentList += @("--trust-remote-code")
    $launcherProc = Start-Process -FilePath $wsl.Source -ArgumentList $ArgumentList -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdoutLogPath -RedirectStandardError $StderrLogPath -WindowStyle Hidden -PassThru
    Write-Host "Started WSL vLLM launcher pid=$($launcherProc.Id)"
    Write-Host "wsl_distro=$ResolvedWslDistro"
    Write-Host "linux_python=$ResolvedLinuxPython"
    Write-Host "linux_model_dir=$ResolvedLinuxModelDir"
    $launcherLabel = "wsl"
} else {
    $ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
    $ArgumentList = @(
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--host", $BindHost,
        "--port", [string]$ResolvedPort,
        "--model", $ResolvedModelDir,
        "--served-model-name", $ResolvedServedModelName,
        "--api-key", $ResolvedApiKey,
        "--max-model-len", [string]$ResolvedMaxModelLen,
        "--gpu-memory-utilization", [string]$ResolvedGpuMemoryUtilization,
        "--enforce-eager",
        "--trust-remote-code"
    )
    $launcherProc = Start-Process -FilePath $ResolvedPython -ArgumentList $ArgumentList -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdoutLogPath -RedirectStandardError $StderrLogPath -PassThru
    Write-Host "Started local vLLM launcher pid=$($launcherProc.Id)"
    $launcherLabel = "native"
}

$payload = Wait-VllmEndpoint -ModelsUrl $ModelsUrl -ResolvedApiKey $ResolvedApiKey -TimeoutSeconds $ResolvedBootTimeoutSeconds -OwnedProcess $launcherProc
if ($payload -and $payload.data -and $payload.data.Count -gt 0 -and $payload.data[0].id) {
    $ResolvedServedModelName = [string]$payload.data[0].id
}
$null = Invoke-VllmWarmup -BaseUrl $ResolvedBaseUrl -ResolvedApiKey $ResolvedApiKey -ResolvedServedModelName $ResolvedServedModelName

Write-RuntimeEnv -BaseUrl $ResolvedBaseUrl -ResolvedModelDir $ResolvedModelDir -ResolvedServedModelName $ResolvedServedModelName -ResolvedApiKey $ResolvedApiKey -ResolvedMaxModelLen $ResolvedMaxModelLen -EnableThinking $false
Write-RuntimeState @{
    pid = $launcherProc.Id
    launcher = $launcherLabel
    model_dir = $ResolvedModelDir
    served_model = $ResolvedServedModelName
    base_url = $ResolvedBaseUrl
    models_url = $ModelsUrl
    api_key = $ResolvedApiKey
    stdout_log = $StdoutLogPath
    stderr_log = $StderrLogPath
    started_at = (Get-Date).ToString("o")
}

Write-Host "vLLM is ready."
Write-Host "base_url=$ResolvedBaseUrl"
Write-Host "served_model=$ResolvedServedModelName"
Write-Host "runtime_env=$RuntimeEnvPath"
Write-Host ""
Write-Host "Next:"
Write-Host "  Public portal:  .\\run_portal.ps1"
Write-Host "  Private desktop: .\\run_ui_private.ps1"
