[CmdletBinding()]
param(
    [string]$ModelDir = "",
    [string]$ServedModelName = "",
    [string]$BaseUrl = "",
    [string]$RuntimeName = "shared",
    [int]$Port = 8001,
    [int]$MaxModelLen = 128000,
    [int]$MaxInputTokensPerTurn = 0,
    [double]$GpuMemoryUtilization = 0.85,
    [string]$BindHost = "0.0.0.0",
    [string]$ApiKey = "athena-local",
    [string]$PythonExe = "",
    [string]$LinuxPython = "python3",
    [string]$LinuxModelDir = "",
    [string]$WslDistro = "",
    [string]$ReasoningParser = "",
    [string]$KvCacheDtype = "",
    [string]$CpuOffloadGb = "",
    [string]$AttentionBackend = "",
    [string]$LimitMmPerPrompt = "",
    [switch]$LanguageModelOnly,
    [switch]$Status,
    [switch]$Stop,
    [switch]$Restart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AthenaPathsScript = Join-Path $ProjectRoot "athena_paths.py"
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
$WslLaunchScriptPath = Join-Path $RuntimeRoot ("wsl_launch{0}.sh" -f $RuntimeSuffix)
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

function Resolve-AthenaPathQuery {
    param(
        [string]$ResolvedPython,
        [string]$QueryName
    )
    if (-not $ResolvedPython -or -not $QueryName -or -not (Test-Path -LiteralPath $AthenaPathsScript)) {
        return $null
    }
    $result = & $ResolvedPython $AthenaPathsScript --query $QueryName 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    $value = (($result | ForEach-Object { [string]$_ }) -join "").Trim()
    return $value
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
    $pathQueryNames = if ($ResolvedRuntimeName -eq "private") {
        @("authoritative_private_model_dir", "private_vllm_source_model_dir", "private_chat_model_dir")
    } else {
        @("authoritative_public_model_dir", "public_vllm_model_dir", "public_chat_model_dir")
    }
    $pathQueryPython = Resolve-PythonExe -ExplicitPath $PythonExe
    foreach ($queryName in $pathQueryNames) {
        $queryResult = Resolve-AthenaPathQuery -ResolvedPython $pathQueryPython -QueryName $queryName
        if ($queryResult) {
            $candidates += $queryResult
        }
    }
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        $resolvedCandidate = if ([System.IO.Path]::IsPathRooted($candidate)) { $candidate } else { Join-Path $ProjectRoot $candidate }
        if (Test-Path -LiteralPath $resolvedCandidate) {
            return (Resolve-Path -LiteralPath $resolvedCandidate).Path
        }
    }
    throw "No local model directory was found. Pass -ModelDir, set ATHENA_VLLM_MODEL_DIR, or update athena_paths.py model routes."
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

function Get-VllmProbeCandidates {
    param(
        [string]$PrimaryBaseUrl,
        [string]$AlternativeBaseUrl = ""
    )
    $candidates = @()
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($candidateBaseUrl in @($PrimaryBaseUrl, $AlternativeBaseUrl)) {
        $trimmed = ([string]$candidateBaseUrl).Trim()
        if (-not $trimmed) { continue }
        if (-not $seen.Add($trimmed)) { continue }
        $candidates += [pscustomobject]@{
            base_url = $trimmed
            models_url = Get-ModelsUrl -BaseUrl $trimmed
        }
    }
    return $candidates
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

function Test-VllmEndpointCandidates {
    param(
        [object[]]$ProbeCandidates,
        [string]$ResolvedApiKey = ""
    )
    foreach ($candidate in @($ProbeCandidates)) {
        if ($null -eq $candidate) { continue }
        $modelsUrl = [string]$candidate.models_url
        if (-not $modelsUrl) { continue }
        $payload = Test-VllmEndpoint -ModelsUrl $modelsUrl -ResolvedApiKey $ResolvedApiKey
        if ($payload) {
            return [pscustomobject]@{
                base_url = [string]$candidate.base_url
                models_url = $modelsUrl
                payload = $payload
            }
        }
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
        [object[]]$ProbeCandidates,
        [string]$ResolvedApiKey = "",
        [int]$TimeoutSeconds,
        [System.Diagnostics.Process]$OwnedProcess,
        [string]$BootLabel = "vLLM"
    )
    $startTime = Get-Date
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $statusIntervalSeconds = 15
    if ($env:ATHENA_VLLM_BOOT_STATUS_INTERVAL_SECONDS -and $env:ATHENA_VLLM_BOOT_STATUS_INTERVAL_SECONDS.Trim()) {
        try {
            $statusIntervalSeconds = [Math]::Max(0, [int]$env:ATHENA_VLLM_BOOT_STATUS_INTERVAL_SECONDS)
        } catch {
            $statusIntervalSeconds = 15
        }
    }
    $nextStatusAt = $startTime.AddSeconds($statusIntervalSeconds)
    $lastStatusMessage = ""
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 900
        if ($OwnedProcess -and $OwnedProcess.HasExited) {
            try {
                $OwnedProcess.Refresh()
                $null = $OwnedProcess.WaitForExit(1500)
            } catch {
            }
            $stdoutSnippet = Read-LogSnippet -FilePath $StdoutLogPath
            $stderrSnippet = Read-LogSnippet -FilePath $StderrLogPath
            $detail = if ($stderrSnippet) { $stderrSnippet } elseif ($stdoutSnippet) { $stdoutSnippet } else { "No launcher output was captured." }
            $hint = ""
            if ($detail -match 'less than desired GPU memory utilization|decrease GPU memory utilization|reduce GPU memory used by other processes') {
                $hint = " Lower ATHENA_VLLM_GPU_MEMORY_UTILIZATION (for example 0.85 or 0.80) or free VRAM before relaunch."
            }
            throw "vLLM launcher exited early with code $($OwnedProcess.ExitCode). $detail$hint Review $StdoutLogPath and $StderrLogPath."
        }
        $probeResult = Test-VllmEndpointCandidates -ProbeCandidates $ProbeCandidates -ResolvedApiKey $ResolvedApiKey
        if ($probeResult) { return $probeResult }
        if ($statusIntervalSeconds -gt 0 -and (Get-Date) -ge $nextStatusAt) {
            $elapsedSeconds = [int][Math]::Floor(((Get-Date) - $startTime).TotalSeconds)
            $remainingSeconds = [int][Math]::Max(0, [Math]::Ceiling(($deadline - (Get-Date)).TotalSeconds))
            $stdoutSnippet = Read-LogSnippet -FilePath $StdoutLogPath
            $stderrSnippet = Read-LogSnippet -FilePath $StderrLogPath
            $detail = if ($stderrSnippet) { $stderrSnippet } elseif ($stdoutSnippet) { $stdoutSnippet } else { "No launcher output yet." }
            $statusMessage = "Waiting for $BootLabel after ${elapsedSeconds}s (about ${remainingSeconds}s remaining). Last log: $detail"
            if ($statusMessage -ne $lastStatusMessage) {
                Write-Host $statusMessage
                $lastStatusMessage = $statusMessage
            } else {
                Write-Host "Waiting for $BootLabel after ${elapsedSeconds}s (about ${remainingSeconds}s remaining). No new log lines yet."
            }
            $nextStatusAt = (Get-Date).AddSeconds($statusIntervalSeconds)
        }
    }
    $urlList = @($ProbeCandidates | ForEach-Object { [string]$_.models_url } | Where-Object { $_ -and $_.Trim().Length -gt 0 })
    $reportedUrls = if ($urlList.Count -gt 0) { ($urlList -join ", ") } else { "<none>" }
    throw "Timed out waiting for vLLM endpoint: $reportedUrls"
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

function Resolve-SafetensorsLoadStrategy {
    param(
        [string]$LinuxModelPath = ""
    )
    $explicit = ""
    if ($env:ATHENA_VLLM_SAFETENSORS_LOAD_STRATEGY -and $env:ATHENA_VLLM_SAFETENSORS_LOAD_STRATEGY.Trim()) {
        $explicit = $env:ATHENA_VLLM_SAFETENSORS_LOAD_STRATEGY.Trim().ToLowerInvariant()
    }
    if ($explicit) {
        if ($explicit -notin @("lazy", "eager", "torchao")) {
            throw "ATHENA_VLLM_SAFETENSORS_LOAD_STRATEGY must be one of: lazy, eager, torchao."
        }
        return $explicit
    }
    if ($LinuxModelPath -and $LinuxModelPath.Trim() -match '^/mnt/[a-z]/') {
        return "eager"
    }
    return ""
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

function Resolve-WslGuestIpAddress {
    param(
        [string]$WslExe,
        [string]$Distro
    )
    if (-not $WslExe -or -not $Distro) {
        return ""
    }
    $command = "hostname -I | awk '{print `$1}'"
    $raw = & $WslExe -d $Distro --exec bash -lc $command 2>$null
    if ($LASTEXITCODE -eq 0) {
        $parts = (($raw | ForEach-Object { [string]$_ }) -join " ").Trim() -split '\s+'
        foreach ($part in $parts) {
            $ip = ([string]$part).Trim()
            if ($ip -match '^(?:\d{1,3}\.){3}\d{1,3}$' -and $ip -ne "127.0.0.1") {
                return $ip
            }
        }
    }
    return ""
}

function Resolve-WslAlternativeBaseUrl {
    param(
        [Uri]$BaseUri,
        [string]$WslGuestIp
    )
    if ($null -eq $BaseUri -or -not $WslGuestIp) {
        return ""
    }
    $baseHost = ($BaseUri.Host -as [string])
    if ($baseHost -notin @("127.0.0.1", "localhost")) {
        return ""
    }
    $port = if ($BaseUri.Port -gt 0) { $BaseUri.Port } else { 80 }
    $path = $BaseUri.AbsolutePath
    if (-not $path -or $path -eq "/") {
        return "http://${WslGuestIp}:$port"
    }
    return ("http://${WslGuestIp}:$port" + $path.TrimEnd('/'))
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

function Resolve-OptionalSetting {
    param(
        [string]$ExplicitValue,
        [string]$EnvVarName
    )
    $explicit = [string]$ExplicitValue
    if ($explicit -and $explicit.Trim()) {
        return $explicit.Trim()
    }
    if ($EnvVarName -and $EnvVarName.Trim()) {
        $raw = [Environment]::GetEnvironmentVariable($EnvVarName.Trim())
        if ($raw -and ([string]$raw).Trim()) {
            return ([string]$raw).Trim()
        }
    }
    return ""
}

function Resolve-OptionalSwitchSetting {
    param(
        [switch]$ExplicitSwitch,
        [string]$EnvVarName
    )
    if ($ExplicitSwitch.IsPresent) {
        return $true
    }
    if ($EnvVarName -and $EnvVarName.Trim()) {
        $raw = [Environment]::GetEnvironmentVariable($EnvVarName.Trim())
        if ($raw -and ([string]$raw).Trim()) {
            $probe = ([string]$raw).Trim().ToLowerInvariant()
            if ($probe -in @("1", "true", "yes", "on")) { return $true }
            if ($probe -in @("0", "false", "no", "off")) { return $false }
        }
    }
    return $false
}

function Read-IntStateValue {
    param(
        [object]$State,
        [string]$Name
    )
    if ($null -eq $State) { return $null }
    try {
        $raw = $State.$Name
    } catch {
        return $null
    }
    if ($null -eq $raw) { return $null }
    try {
        return [int]$raw
    } catch {
        return $null
    }
}

function Write-RuntimeEnv {
    param(
        [string]$BaseUrl,
        [string]$ResolvedModelDir,
        [string]$ResolvedServedModelName,
        [string]$ResolvedApiKey,
        [double]$ResolvedGpuMemoryUtilization,
        [int]$ResolvedMaxModelLen,
        [int]$ResolvedMaxInputTokensPerTurn = 0,
        [bool]$EnableThinking = $false,
        [string]$ResolvedLimitMmPerPrompt = ""
    )
    Initialize-AthenaVllmRuntimeRoot
    $lines = @(
        "ATHENA_RUNTIME_BACKEND=vllm_openai"
        "ATHENA_VLLM_BASE_URL=$BaseUrl"
        "ATHENA_VLLM_MODEL_DIR=$ResolvedModelDir"
        "ATHENA_VLLM_MODEL=$ResolvedServedModelName"
        "ATHENA_VLLM_API_KEY=$ResolvedApiKey"
        "ATHENA_VLLM_GPU_MEMORY_UTILIZATION=$ResolvedGpuMemoryUtilization"
        "ATHENA_VLLM_MAX_MODEL_LEN=$ResolvedMaxModelLen"
        "ATHENA_VLLM_MAX_CONTEXT_TOKENS=$ResolvedMaxModelLen"
        "ATHENA_VLLM_MAX_INPUT_TOKENS=$ResolvedMaxInputTokensPerTurn"
        "ATHENA_VLLM_ENABLE_THINKING=$([int]$EnableThinking)"
    )
    if ($ResolvedLimitMmPerPrompt -and $ResolvedLimitMmPerPrompt.Trim()) {
        $lines += "ATHENA_VLLM_LIMIT_MM_PER_PROMPT=$($ResolvedLimitMmPerPrompt.Trim())"
    }
    $lines | Set-Content -LiteralPath $RuntimeEnvPath -Encoding utf8
    $env:ATHENA_RUNTIME_BACKEND = "vllm_openai"
    $env:ATHENA_VLLM_BASE_URL = $BaseUrl
    $env:ATHENA_VLLM_MODEL_DIR = $ResolvedModelDir
    $env:ATHENA_VLLM_MODEL = $ResolvedServedModelName
    $env:ATHENA_VLLM_API_KEY = $ResolvedApiKey
    $env:ATHENA_VLLM_GPU_MEMORY_UTILIZATION = [string]$ResolvedGpuMemoryUtilization
    $env:ATHENA_VLLM_MAX_MODEL_LEN = [string]$ResolvedMaxModelLen
    $env:ATHENA_VLLM_MAX_CONTEXT_TOKENS = [string]$ResolvedMaxModelLen
    $env:ATHENA_VLLM_MAX_INPUT_TOKENS = [string]$ResolvedMaxInputTokensPerTurn
    $env:ATHENA_VLLM_ENABLE_THINKING = [string]([int]$EnableThinking)
    if ($ResolvedLimitMmPerPrompt -and $ResolvedLimitMmPerPrompt.Trim()) {
        $env:ATHENA_VLLM_LIMIT_MM_PER_PROMPT = $ResolvedLimitMmPerPrompt.Trim()
    } else {
        Remove-Item -Path "Env:ATHENA_VLLM_LIMIT_MM_PER_PROMPT" -ErrorAction SilentlyContinue
    }
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
        [string]$ResolvedApiKey = "",
        [object[]]$ProbeCandidates = @()
    )
    $candidates = if ($ProbeCandidates -and $ProbeCandidates.Count -gt 0) {
        @($ProbeCandidates)
    } else {
        @(Get-VllmProbeCandidates -PrimaryBaseUrl $BaseUrl)
    }
    $probeResult = Test-VllmEndpointCandidates -ProbeCandidates $candidates -ResolvedApiKey $ResolvedApiKey
    $modelsUrl = if ($probeResult) { [string]$probeResult.models_url } else { Get-ModelsUrl -BaseUrl $BaseUrl }
    $state = Read-RuntimeState
    Write-Host "vLLM status"
    Write-Host "base_url=$BaseUrl"
    if ($probeResult -and $probeResult.base_url -and $probeResult.base_url -ne $BaseUrl) {
        Write-Host "reachable_base_url=$($probeResult.base_url)"
    }
    Write-Host "models_url=$modelsUrl"
    Write-Host "healthy=$([bool]($null -ne $probeResult))"
    if ($probeResult -and $probeResult.payload -and $probeResult.payload.data -and $probeResult.payload.data.Count -gt 0) {
        Write-Host "served_model=$($probeResult.payload.data[0].id)"
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
$ResolvedApiKey = if ($ApiKey -and $ApiKey.Trim()) { $ApiKey.Trim() } elseif ($env:ATHENA_VLLM_API_KEY -and $env:ATHENA_VLLM_API_KEY.Trim()) { $env:ATHENA_VLLM_API_KEY.Trim() } else { "athena-local" }
$ResolvedWslExe = $null
$ResolvedWslDistro = ""
$ResolvedWslGuestIp = ""
$AlternativeBaseUrl = ""
if ($IsWindowsHost) {
    $ResolvedWslExe = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if ($ResolvedWslExe -and $ResolvedBaseUri.Host -in @("127.0.0.1", "localhost")) {
        try {
            $ResolvedWslDistro = Resolve-WslDistro -ExplicitDistro $WslDistro
            $ResolvedWslGuestIp = Resolve-WslGuestIpAddress -WslExe $ResolvedWslExe.Source -Distro $ResolvedWslDistro
            $AlternativeBaseUrl = Resolve-WslAlternativeBaseUrl -BaseUri $ResolvedBaseUri -WslGuestIp $ResolvedWslGuestIp
        } catch {
            $ResolvedWslGuestIp = ""
            $AlternativeBaseUrl = ""
        }
    }
}
$ProbeCandidates = @(Get-VllmProbeCandidates -PrimaryBaseUrl $ResolvedBaseUrl -AlternativeBaseUrl $AlternativeBaseUrl)
$ModelsUrl = Get-ModelsUrl -BaseUrl $ResolvedBaseUrl

if ($Status) {
    Show-Status -BaseUrl $ResolvedBaseUrl -ResolvedApiKey $ResolvedApiKey -ProbeCandidates $ProbeCandidates
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
$ResolvedMaxInputTokensPerTurn = if ($env:ATHENA_VLLM_MAX_INPUT_TOKENS -and $env:ATHENA_VLLM_MAX_INPUT_TOKENS.Trim()) { [int]$env:ATHENA_VLLM_MAX_INPUT_TOKENS } else { $MaxInputTokensPerTurn }
$ResolvedGpuMemoryUtilization = if ($env:ATHENA_VLLM_GPU_MEMORY_UTILIZATION -and $env:ATHENA_VLLM_GPU_MEMORY_UTILIZATION.Trim()) { [double]$env:ATHENA_VLLM_GPU_MEMORY_UTILIZATION } else { $GpuMemoryUtilization }
$ResolvedReasoningParser = Resolve-OptionalSetting -ExplicitValue $ReasoningParser -EnvVarName "ATHENA_VLLM_REASONING_PARSER"
$ResolvedKvCacheDtype = Resolve-OptionalSetting -ExplicitValue $KvCacheDtype -EnvVarName "ATHENA_VLLM_KV_CACHE_DTYPE"
$ResolvedCpuOffloadGb = Resolve-OptionalSetting -ExplicitValue $CpuOffloadGb -EnvVarName "ATHENA_VLLM_CPU_OFFLOAD_GB"
$ResolvedAttentionBackend = Resolve-OptionalSetting -ExplicitValue $AttentionBackend -EnvVarName "ATHENA_VLLM_ATTENTION_BACKEND"
$ResolvedLimitMmPerPrompt = Resolve-OptionalSetting -ExplicitValue $LimitMmPerPrompt -EnvVarName "ATHENA_VLLM_LIMIT_MM_PER_PROMPT"
$ResolvedLanguageModelOnly = Resolve-OptionalSwitchSetting -ExplicitSwitch $LanguageModelOnly -EnvVarName "ATHENA_VLLM_LANGUAGE_MODEL_ONLY"
$LanguageModelOnlyExplicitlyRequested = $PSBoundParameters.ContainsKey("LanguageModelOnly")
if ($ResolvedRuntimeName -eq "private" -and (-not $LanguageModelOnlyExplicitlyRequested)) {
    # Private desktop must stay multimodal by default; ignore leaked env flags.
    $ResolvedLanguageModelOnly = $false
}
if (($ResolvedRuntimeName -eq "private") -and (-not $ResolvedLanguageModelOnly) -and (-not ($ResolvedLimitMmPerPrompt -and $ResolvedLimitMmPerPrompt.Trim()))) {
    $ResolvedLimitMmPerPrompt = '{"image":6}'
}
$ResolvedBootTimeoutSeconds = if ($env:ATHENA_VLLM_BOOT_TIMEOUT_SECONDS -and $env:ATHENA_VLLM_BOOT_TIMEOUT_SECONDS.Trim()) {
    [int]$env:ATHENA_VLLM_BOOT_TIMEOUT_SECONDS
} elseif ($ResolvedRuntimeName -eq "private") {
    900
} else {
    240
}

$stateBeforeHealthyCheck = Read-RuntimeState
$healthyProbeResult = Test-VllmEndpointCandidates -ProbeCandidates $ProbeCandidates -ResolvedApiKey $ResolvedApiKey
$healthyPayload = if ($healthyProbeResult) { $healthyProbeResult.payload } else { $null }
if ($healthyProbeResult) {
    $ResolvedBaseUrl = [string]$healthyProbeResult.base_url
    $ModelsUrl = [string]$healthyProbeResult.models_url
}
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
    $managedMaxModelLen = Read-IntStateValue -State $stateBeforeHealthyCheck -Name "max_model_len"
    $managedMaxInputTokensPerTurn = Read-IntStateValue -State $stateBeforeHealthyCheck -Name "max_input_tokens_per_turn"
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
    $maxModelLenMatches = ($managedMaxModelLen -eq $ResolvedMaxModelLen)
    $maxInputTokensMatches = ($managedMaxInputTokensPerTurn -eq $ResolvedMaxInputTokensPerTurn)
    $managedLimitMmPerPrompt = ""
    if ($stateBeforeHealthyCheck -and $null -ne $stateBeforeHealthyCheck.limit_mm_per_prompt_request) {
        try {
            $managedLimitMmPerPrompt = ([string]$stateBeforeHealthyCheck.limit_mm_per_prompt_request).Trim()
        } catch {
            $managedLimitMmPerPrompt = ""
        }
    }
    $limitMmPerPromptMatches = ($managedLimitMmPerPrompt -eq (($ResolvedLimitMmPerPrompt -as [string]).Trim()))
    $managedLanguageModelOnly = $null
    if ($stateBeforeHealthyCheck -and $null -ne $stateBeforeHealthyCheck.language_model_only_request) {
        try {
            $rawLanguageModelOnly = [string]$stateBeforeHealthyCheck.language_model_only_request
            if ($rawLanguageModelOnly.Trim()) {
                $probe = $rawLanguageModelOnly.Trim().ToLowerInvariant()
                if ($probe -in @("1", "true", "yes", "on")) {
                    $managedLanguageModelOnly = $true
                } elseif ($probe -in @("0", "false", "no", "off")) {
                    $managedLanguageModelOnly = $false
                }
            }
        } catch {
            $managedLanguageModelOnly = $null
        }
    }
    $languageModelOnlyMatches = ($null -eq $managedLanguageModelOnly) -or ($managedLanguageModelOnly -eq $ResolvedLanguageModelOnly)
    $shouldRestartManagedEndpoint = $false
    if ($canTrustManagedModelDir) {
        $shouldRestartManagedEndpoint = (-not $managedModelDirMatches) -or (-not $servedModelMatches) -or (-not $maxModelLenMatches) -or (-not $maxInputTokensMatches) -or (-not $languageModelOnlyMatches) -or (-not $limitMmPerPromptMatches)
    } elseif (-not $servedModelMatches) {
        $shouldRestartManagedEndpoint = $true
    } elseif ($stateBeforeHealthyCheck -and ((-not $maxModelLenMatches) -or (-not $maxInputTokensMatches) -or (-not $languageModelOnlyMatches) -or (-not $limitMmPerPromptMatches))) {
        $shouldRestartManagedEndpoint = $true
    } elseif (($ResolvedRuntimeName -eq "private") -and (-not $stateBeforeHealthyCheck) -and $ResolvedLimitMmPerPrompt) {
        $shouldRestartManagedEndpoint = $true
    }
    if ($shouldRestartManagedEndpoint) {
        if ($stateBeforeHealthyCheck) {
            Write-Host "Managed vLLM endpoint is serving '$activeServedModelName' from '$($stateBeforeHealthyCheck.model_dir)' with max_model_len=$managedMaxModelLen, max_input_tokens_per_turn=$managedMaxInputTokensPerTurn, language_model_only=$managedLanguageModelOnly, limit_mm_per_prompt='$managedLimitMmPerPrompt'. Restarting for '$ResolvedServedModelName' from '$ResolvedModelDir' with max_model_len=$ResolvedMaxModelLen, max_input_tokens_per_turn=$ResolvedMaxInputTokensPerTurn, language_model_only=$ResolvedLanguageModelOnly, limit_mm_per_prompt='$ResolvedLimitMmPerPrompt'."
            $null = Stop-ManagedVllm
            $healthyPayload = $null
        } else {
            $handledLocalRestart = $false
            if ((($Restart) -or (($ResolvedRuntimeName -eq "private") -and $ResolvedLimitMmPerPrompt)) -and $IsWindowsHost -and $ResolvedBaseUri.Host -in @("127.0.0.1", "localhost")) {
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
    Write-RuntimeEnv -BaseUrl $ResolvedBaseUrl -ResolvedModelDir $ResolvedModelDir -ResolvedServedModelName $ResolvedServedModelName -ResolvedApiKey $ResolvedApiKey -ResolvedGpuMemoryUtilization $ResolvedGpuMemoryUtilization -ResolvedMaxModelLen $ResolvedMaxModelLen -ResolvedMaxInputTokensPerTurn $ResolvedMaxInputTokensPerTurn -EnableThinking $false -ResolvedLimitMmPerPrompt $ResolvedLimitMmPerPrompt
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
    if (-not $ResolvedWslExe) {
        throw "wsl.exe was not found. Install WSL or start a Linux vLLM endpoint manually."
    }
    if (-not $ResolvedWslDistro) {
        $ResolvedWslDistro = Resolve-WslDistro -ExplicitDistro $WslDistro
    }
    $ResolvedLinuxModelDir = if ($LinuxModelDir -and $LinuxModelDir.Trim()) { $LinuxModelDir.Trim() } else { Convert-ToWslPath -WindowsPath $ResolvedModelDir }
    $ResolvedLinuxPython = Resolve-LinuxPython -ExplicitPath $LinuxPython -WslExe $ResolvedWslExe.Source -Distro $ResolvedWslDistro
    $ResolvedSafetensorsLoadStrategy = Resolve-SafetensorsLoadStrategy -LinuxModelPath $ResolvedLinuxModelDir
    if (-not $ResolvedWslGuestIp) {
        $ResolvedWslGuestIp = Resolve-WslGuestIpAddress -WslExe $ResolvedWslExe.Source -Distro $ResolvedWslDistro
        if (-not $AlternativeBaseUrl) {
            $AlternativeBaseUrl = Resolve-WslAlternativeBaseUrl -BaseUri $ResolvedBaseUri -WslGuestIp $ResolvedWslGuestIp
        }
        $ProbeCandidates = @(Get-VllmProbeCandidates -PrimaryBaseUrl $ResolvedBaseUrl -AlternativeBaseUrl $AlternativeBaseUrl)
    }
    Assert-WslRuntimeReady -WslExe $ResolvedWslExe.Source -Distro $ResolvedWslDistro -LinuxPython $ResolvedLinuxPython
    $LinuxCommandArgs = @(
        $ResolvedLinuxPython,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--host", $BindHost,
        "--port", [string]$ResolvedPort,
        "--model", $ResolvedLinuxModelDir,
        "--served-model-name", $ResolvedServedModelName,
        "--api-key", $ResolvedApiKey,
        "--max-model-len", [string]$ResolvedMaxModelLen,
        "--gpu-memory-utilization", [string]$ResolvedGpuMemoryUtilization,
        "--enforce-eager",
        "--trust-remote-code"
    )
    if ($ResolvedReasoningParser) {
        $LinuxCommandArgs += @("--reasoning-parser", $ResolvedReasoningParser)
    }
    if ($ResolvedKvCacheDtype) {
        $LinuxCommandArgs += @("--kv-cache-dtype", $ResolvedKvCacheDtype)
    }
    if ($ResolvedCpuOffloadGb) {
        $LinuxCommandArgs += @("--cpu-offload-gb", $ResolvedCpuOffloadGb)
    }
    if ($ResolvedAttentionBackend) {
        $LinuxCommandArgs += @("--attention-backend", $ResolvedAttentionBackend)
    }
    if ($ResolvedLimitMmPerPrompt) {
        $LinuxCommandArgs += @("--limit-mm-per-prompt", $ResolvedLimitMmPerPrompt)
    }
    if ($ResolvedLanguageModelOnly) {
        $LinuxCommandArgs += @("--language-model-only")
    }
    if ($ResolvedSafetensorsLoadStrategy) {
        $LinuxCommandArgs += @("--safetensors-load-strategy", $ResolvedSafetensorsLoadStrategy)
    }
    $ArgumentList = @("-d", $ResolvedWslDistro)
    if ($ResolvedLimitMmPerPrompt) {
        # WSL argument forwarding strips embedded JSON quotes from this specific argument.
        # Write a small launch script and run it under bash so vLLM receives the raw JSON.
        $BashCommand = "exec " + (($LinuxCommandArgs | ForEach-Object { ConvertTo-BashLiteral -Value ([string]$_) }) -join " ")
        $scriptBody = "#!/usr/bin/env bash`nset -euo pipefail`n$BashCommand`n"
        [System.IO.File]::WriteAllText($WslLaunchScriptPath, $scriptBody, [System.Text.UTF8Encoding]::new($false))
        $LinuxLaunchScriptPath = Convert-ToWslPath -WindowsPath $WslLaunchScriptPath
        $ArgumentList += @("--exec", "bash", $LinuxLaunchScriptPath)
    } else {
        $ArgumentList += @("--exec")
        $ArgumentList += $LinuxCommandArgs
    }
    $launcherProc = Start-Process -FilePath $ResolvedWslExe.Source -ArgumentList $ArgumentList -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdoutLogPath -RedirectStandardError $StderrLogPath -WindowStyle Hidden -PassThru
    Write-Host "Started WSL vLLM launcher pid=$($launcherProc.Id)"
    Write-Host "wsl_distro=$ResolvedWslDistro"
    Write-Host "linux_python=$ResolvedLinuxPython"
    Write-Host "linux_model_dir=$ResolvedLinuxModelDir"
    if ($ResolvedWslGuestIp) {
        Write-Host "wsl_guest_ip=$ResolvedWslGuestIp"
    }
    if ($AlternativeBaseUrl) {
        Write-Host "wsl_guest_base_url=$AlternativeBaseUrl"
    }
    if ($ResolvedSafetensorsLoadStrategy) {
        Write-Host "safetensors_load_strategy=$ResolvedSafetensorsLoadStrategy"
    }
    if ($ResolvedReasoningParser) {
        Write-Host "reasoning_parser=$ResolvedReasoningParser"
    }
    if ($ResolvedAttentionBackend) {
        Write-Host "attention_backend=$ResolvedAttentionBackend"
    }
    if ($ResolvedLimitMmPerPrompt) {
        Write-Host "limit_mm_per_prompt=$ResolvedLimitMmPerPrompt"
    }
    if ($ResolvedLanguageModelOnly) {
        Write-Host "language_model_only=true"
    }
    Write-Host "stdout_log=$StdoutLogPath"
    Write-Host "stderr_log=$StderrLogPath"
    $launcherLabel = "wsl"
} else {
    $ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
    $ResolvedSafetensorsLoadStrategy = Resolve-SafetensorsLoadStrategy
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
    if ($ResolvedReasoningParser) {
        $ArgumentList += @("--reasoning-parser", $ResolvedReasoningParser)
    }
    if ($ResolvedKvCacheDtype) {
        $ArgumentList += @("--kv-cache-dtype", $ResolvedKvCacheDtype)
    }
    if ($ResolvedCpuOffloadGb) {
        $ArgumentList += @("--cpu-offload-gb", $ResolvedCpuOffloadGb)
    }
    if ($ResolvedAttentionBackend) {
        $ArgumentList += @("--attention-backend", $ResolvedAttentionBackend)
    }
    if ($ResolvedLimitMmPerPrompt) {
        $ArgumentList += @("--limit-mm-per-prompt", $ResolvedLimitMmPerPrompt)
    }
    if ($ResolvedLanguageModelOnly) {
        $ArgumentList += @("--language-model-only")
    }
    if ($ResolvedSafetensorsLoadStrategy) {
        $ArgumentList += @("--safetensors-load-strategy", $ResolvedSafetensorsLoadStrategy)
    }
    $launcherProc = Start-Process -FilePath $ResolvedPython -ArgumentList $ArgumentList -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdoutLogPath -RedirectStandardError $StderrLogPath -PassThru
    Write-Host "Started local vLLM launcher pid=$($launcherProc.Id)"
    if ($ResolvedSafetensorsLoadStrategy) {
        Write-Host "safetensors_load_strategy=$ResolvedSafetensorsLoadStrategy"
    }
    if ($ResolvedReasoningParser) {
        Write-Host "reasoning_parser=$ResolvedReasoningParser"
    }
    if ($ResolvedAttentionBackend) {
        Write-Host "attention_backend=$ResolvedAttentionBackend"
    }
    if ($ResolvedLimitMmPerPrompt) {
        Write-Host "limit_mm_per_prompt=$ResolvedLimitMmPerPrompt"
    }
    if ($ResolvedLanguageModelOnly) {
        Write-Host "language_model_only=true"
    }
    Write-Host "stdout_log=$StdoutLogPath"
    Write-Host "stderr_log=$StderrLogPath"
    $launcherLabel = "native"
}

$probeResult = Wait-VllmEndpoint -ProbeCandidates $ProbeCandidates -ResolvedApiKey $ResolvedApiKey -TimeoutSeconds $ResolvedBootTimeoutSeconds -OwnedProcess $launcherProc -BootLabel "$launcherLabel vLLM on $ResolvedBaseUrl"
$payload = if ($probeResult) { $probeResult.payload } else { $null }
if ($probeResult -and $probeResult.base_url) {
    $ResolvedActiveBaseUrl = [string]$probeResult.base_url
    $ResolvedActiveModelsUrl = [string]$probeResult.models_url
    if ($ResolvedActiveBaseUrl -ne $ResolvedBaseUrl) {
        Write-Host "Windows localhost forwarding was unavailable. Using reachable WSL base URL: $ResolvedActiveBaseUrl"
    }
    $ResolvedBaseUrl = $ResolvedActiveBaseUrl
    $ModelsUrl = $ResolvedActiveModelsUrl
}
if ($payload -and $payload.data -and $payload.data.Count -gt 0 -and $payload.data[0].id) {
    $ResolvedServedModelName = [string]$payload.data[0].id
}
$null = Invoke-VllmWarmup -BaseUrl $ResolvedBaseUrl -ResolvedApiKey $ResolvedApiKey -ResolvedServedModelName $ResolvedServedModelName

Write-RuntimeEnv -BaseUrl $ResolvedBaseUrl -ResolvedModelDir $ResolvedModelDir -ResolvedServedModelName $ResolvedServedModelName -ResolvedApiKey $ResolvedApiKey -ResolvedGpuMemoryUtilization $ResolvedGpuMemoryUtilization -ResolvedMaxModelLen $ResolvedMaxModelLen -ResolvedMaxInputTokensPerTurn $ResolvedMaxInputTokensPerTurn -EnableThinking $false -ResolvedLimitMmPerPrompt $ResolvedLimitMmPerPrompt
Write-RuntimeState @{
    pid = $launcherProc.Id
    launcher = $launcherLabel
    model_dir = $ResolvedModelDir
    served_model = $ResolvedServedModelName
    base_url = $ResolvedBaseUrl
    models_url = $ModelsUrl
    api_key = $ResolvedApiKey
    max_model_len = $ResolvedMaxModelLen
    max_input_tokens_per_turn = $ResolvedMaxInputTokensPerTurn
    kv_cache_dtype = $ResolvedKvCacheDtype
    cpu_offload_gb = $ResolvedCpuOffloadGb
    attention_backend_request = $ResolvedAttentionBackend
    limit_mm_per_prompt_request = $ResolvedLimitMmPerPrompt
    language_model_only_request = $ResolvedLanguageModelOnly
    reasoning_parser_request = $ResolvedReasoningParser
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
