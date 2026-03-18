[CmdletBinding()]
param(
    [switch]$Tools,
    [switch]$NoAutoInstallDeps,
    [int]$Port = 8000,
    [string]$PathPrefix = "/AthenaV5",
    [string]$PythonExe = "",
    [string]$ModelDir = "",
    [string]$BaseUrl = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExclusiveRoot = Join-Path $ProjectRoot "exclusive"
$SeedRoot = Join-Path $ProjectRoot "archive\shared_archives\private_desktop_seed_2026-03"
$PrivateQtUi = Join-Path $ExclusiveRoot "desktop\qt_ui.py"
$PrivateDesktopApp = Join-Path $ExclusiveRoot "desktop_app"
$ConfigDir = Join-Path $ExclusiveRoot "config"
$LogsDir = Join-Path $ExclusiveRoot "logs"
$DesktopLogDir = Join-Path $LogsDir "desktop"
$DataDir = Join-Path $ExclusiveRoot "data"
$DesktopImageDir = Join-Path $DataDir "desktop_images"
$TranscriptHtml = Join-Path $PrivateDesktopApp "assets\transcript.html"
$Requirements = Join-Path $ProjectRoot "requirements.txt"
$DefaultExclusiveModelDir = Join-Path $ExclusiveRoot "AthenaV1"
$DefaultTrackedModelDir = Join-Path $ProjectRoot "models\tuned\AthenaV1"
$ResolvedModelDir = if ($ModelDir -and $ModelDir.Trim()) {
    if ([System.IO.Path]::IsPathRooted($ModelDir)) { $ModelDir.Trim() } else { Join-Path $ProjectRoot $ModelDir.Trim() }
} elseif (Test-Path -LiteralPath $DefaultExclusiveModelDir) {
    $DefaultExclusiveModelDir
} else {
    $DefaultTrackedModelDir
}
$GuiConfigPath = Join-Path $ConfigDir "gui_config.json"
$SystemPromptPath = Join-Path $ConfigDir "system_prompt.json"
$PrivateRuntimeName = "private"
$DefaultPrivateVllmBaseUrl = "http://127.0.0.1:8002/v1"
$PrivateRuntimeEnvFile = Join-Path $ProjectRoot ".local\runtime\vllm_private_runtime.env"
$PrivateVllmExportRoot = Join-Path $ProjectRoot ".local\runtime\vllm_private_models"
$PrivateVllmExportScript = Join-Path $ProjectRoot "exclusive\desktop_engine\export_vllm_ready_model.py"
$SharedVllmLauncher = Join-Path $ProjectRoot "run_vllm.ps1"

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
    throw "No Python runtime found. Activate/create a venv first."
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

function Test-QtDeps {
    param([string]$ResolvedPython)
    & $ResolvedPython -c "import PySide6; from PySide6.QtWebEngineWidgets import QWebEngineView" 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Install-UiDeps {
    param([string]$ResolvedPython)
    if (Test-Path -LiteralPath $Requirements) {
        & $ResolvedPython -m pip install --disable-pip-version-check -r $Requirements
    } else {
        & $ResolvedPython -m pip install --disable-pip-version-check PySide6 PySide6-Addons
    }
    return ($LASTEXITCODE -eq 0)
}

function Invoke-SharedVllmBootstrap {
    param(
        [string]$ResolvedVllmModelDir,
        [string]$ResolvedPython,
        [string]$ResolvedServedModelName,
        [string]$ResolvedBaseUrl
    )
    if (-not (Test-Path -LiteralPath $SharedVllmLauncher)) {
        throw "Shared vLLM launcher not found: $SharedVllmLauncher"
    }
    $launcherArgs = @{
        ModelDir = $ResolvedVllmModelDir
        ServedModelName = $ResolvedServedModelName
        RuntimeName = $PrivateRuntimeName
        BaseUrl = $ResolvedBaseUrl
    }
    if ($ResolvedPython -and $ResolvedPython.Trim()) {
        $launcherArgs.PythonExe = $ResolvedPython
    }
    & $SharedVllmLauncher @launcherArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Shared vLLM bootstrap failed with code $LASTEXITCODE."
    }
    $null = Import-EnvFile -FilePath $PrivateRuntimeEnvFile
}

function Export-PrivateVllmModel {
    param(
        [string]$SourceModelDir,
        [string]$ResolvedPython,
        [string]$ResolvedServedModelName
    )
    if (-not (Test-Path -LiteralPath $PrivateVllmExportScript)) {
        throw "Private vLLM export script not found: $PrivateVllmExportScript"
    }
    if (-not (Test-Path -LiteralPath $PrivateVllmExportRoot)) {
        New-Item -ItemType Directory -Path $PrivateVllmExportRoot -Force | Out-Null
    }
    $targetDir = Join-Path $PrivateVllmExportRoot $ResolvedServedModelName
    Write-Host "Preparing private vLLM runtime model..."
    Write-Host "source=$SourceModelDir"
    Write-Host "target=$targetDir"
    $exportOutput = & $ResolvedPython $PrivateVllmExportScript --source-model-dir $SourceModelDir --output-dir $targetDir
    if ($LASTEXITCODE -ne 0) {
        throw "Private vLLM model export failed with code $LASTEXITCODE."
    }
    if ($exportOutput) {
        foreach ($line in @($exportOutput)) {
            $text = ([string]$line).Trim()
            if ($text) {
                Write-Host $text
            }
        }
    }
    if (-not (Test-Path -LiteralPath $targetDir)) {
        throw "Private vLLM model export did not create $targetDir"
    }
    return (Resolve-Path -LiteralPath $targetDir).Path
}

function Initialize-ExclusiveDesktop {
    $requiredDirectories = @(
        $ExclusiveRoot
        $ConfigDir
        $LogsDir
        $DesktopLogDir
        $DataDir
        $DesktopImageDir
        (Join-Path $ExclusiveRoot 'desktop')
        $PrivateDesktopApp
        (Join-Path $PrivateDesktopApp 'assets')
    )
    foreach ($dir in $requiredDirectories) {
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    if (-not (Test-Path -LiteralPath $PrivateQtUi)) {
        if (-not (Test-Path -LiteralPath $SeedRoot)) {
            throw "Private desktop seed not found: $SeedRoot"
        }
        Copy-Item -LiteralPath (Join-Path $SeedRoot 'desktop\qt_ui.py') -Destination $PrivateQtUi -Force
        Copy-Item -LiteralPath (Join-Path $SeedRoot 'desktop_app\main.py') -Destination (Join-Path $PrivateDesktopApp 'main.py') -Force
        Copy-Item -LiteralPath (Join-Path $SeedRoot 'desktop_app\session_logger.py') -Destination (Join-Path $PrivateDesktopApp 'session_logger.py') -Force
        Copy-Item -LiteralPath (Join-Path $SeedRoot 'desktop_app\__init__.py') -Destination (Join-Path $PrivateDesktopApp '__init__.py') -Force
        Copy-Item -LiteralPath (Join-Path $SeedRoot 'desktop_app\assets\transcript.html') -Destination (Join-Path $PrivateDesktopApp 'assets\transcript.html') -Force
        Copy-Item -LiteralPath (Join-Path $SeedRoot 'desktop_app\assets\transcript.css') -Destination (Join-Path $PrivateDesktopApp 'assets\transcript.css') -Force
        Copy-Item -LiteralPath (Join-Path $SeedRoot 'desktop_app\assets\transcript.js') -Destination (Join-Path $PrivateDesktopApp 'assets\transcript.js') -Force
    }
    if (-not (Test-Path -LiteralPath $GuiConfigPath)) {
        Set-Content -LiteralPath $GuiConfigPath -Encoding utf8 -Value '{
  "temperature": 0.45,
  "max_new_tokens": 2048,
  "top_p": 0.9,
  "top_k": 40,
  "repetition_penalty": 1.18,
  "no_repeat_ngram_size": 6,
  "tools_enabled": false,
  "enable_thinking": false,
  "hide_thoughts": true,
  "renderer_mode": "qt_web",
  "render_throttle_ms": 75
}'
    }
    if (-not (Test-Path -LiteralPath $SystemPromptPath)) {
        Set-Content -LiteralPath $SystemPromptPath -Encoding utf8 -Value '{
  "version": "1.0",
  "name": "exclusive_athena_v1",
  "system_prompt": "You are speaking to Neohm himself. You are AthenaV1, his canonical private model. Respond with continuity, clarity, recognition, and privacy-aware exclusivity to this local shell."
}'
    }
}

$LoadedPrivateRuntimeEnv = Import-EnvFile -FilePath $PrivateRuntimeEnvFile
$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
Initialize-ExclusiveDesktop
if (-not (Test-Path -LiteralPath $ResolvedModelDir)) {
    throw "Private Athena model not found: $ResolvedModelDir"
}
if (-not (Test-Path -LiteralPath $PrivateQtUi)) {
    throw "Private Qt UI not found: $PrivateQtUi"
}
if (-not (Test-Path -LiteralPath $TranscriptHtml)) {
    throw "Private transcript asset not found: $TranscriptHtml"
}

$QtReady = Test-QtDeps -ResolvedPython $ResolvedPython
if (-not $QtReady -and -not $NoAutoInstallDeps) {
    Write-Host "Installing desktop UI dependencies..."
    $null = Install-UiDeps -ResolvedPython $ResolvedPython
    $QtReady = Test-QtDeps -ResolvedPython $ResolvedPython
}
if (-not $QtReady) {
    throw "PySide6 + QtWebEngine is required. Install requirements or rerun without -NoAutoInstallDeps."
}

$envNames = @(
    'ATHENA_CHAT_MODEL_DIR',
    'ATHENA_GUI_CONFIG_PATH',
    'ATHENA_SYSTEM_PROMPT_FILE',
    'ATHENA_LOG_ROOT',
    'ATHENA_DESKTOP_IMAGE_STAGE_DIR',
    'ATHENA_DESKTOP_TRANSCRIPT_HTML',
    'ATHENA_DESKTOP_NDJSON_LOG',
    'ATHENA_PRIVATE_MODE',
    'ATHENA_RUNTIME_SCOPE',
    'ATHENA_RUNTIME_BACKEND',
    'ATHENA_VLLM_BASE_URL',
    'ATHENA_VLLM_MODEL',
    'ATHENA_VLLM_API_KEY',
    'ATHENA_VLLM_MODEL_DIR'
)
$originalEnv = @{}
foreach ($name in $envNames) {
    $item = Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    $originalEnv[$name] = if ($null -ne $item) { $item.Value } else { $null }
}

try {
    Set-Location -LiteralPath $ProjectRoot
    $ResolvedPrivateBaseUrl = if ($BaseUrl -and $BaseUrl.Trim()) {
        $BaseUrl.Trim().TrimEnd("/")
    } elseif ($LoadedPrivateRuntimeEnv -and $env:ATHENA_VLLM_BASE_URL -and $env:ATHENA_VLLM_BASE_URL.Trim()) {
        $env:ATHENA_VLLM_BASE_URL.Trim().TrimEnd("/")
    } elseif ($env:ATHENA_PRIVATE_VLLM_BASE_URL -and $env:ATHENA_PRIVATE_VLLM_BASE_URL.Trim()) {
        $env:ATHENA_PRIVATE_VLLM_BASE_URL.Trim().TrimEnd("/")
    } else {
        $DefaultPrivateVllmBaseUrl
    }
    $ResolvedServedModelName = Split-Path -Leaf $ResolvedModelDir
    $ResolvedVllmModelDir = Export-PrivateVllmModel -SourceModelDir $ResolvedModelDir -ResolvedPython $ResolvedPython -ResolvedServedModelName $ResolvedServedModelName
    $env:ATHENA_CHAT_MODEL_DIR = $ResolvedModelDir
    $env:ATHENA_VLLM_MODEL_DIR = $ResolvedVllmModelDir
    $env:ATHENA_GUI_CONFIG_PATH = $GuiConfigPath
    $env:ATHENA_SYSTEM_PROMPT_FILE = $SystemPromptPath
    $env:ATHENA_LOG_ROOT = $LogsDir
    $env:ATHENA_DESKTOP_IMAGE_STAGE_DIR = $DesktopImageDir
    $env:ATHENA_DESKTOP_TRANSCRIPT_HTML = $TranscriptHtml
    $env:ATHENA_DESKTOP_NDJSON_LOG = '1'
    $env:ATHENA_PRIVATE_MODE = '1'
    $env:ATHENA_RUNTIME_SCOPE = 'private'
    $env:ATHENA_RUNTIME_BACKEND = 'vllm_openai'
    $env:ATHENA_VLLM_BASE_URL = $ResolvedPrivateBaseUrl
    if (-not $env:ATHENA_VLLM_API_KEY -or -not $env:ATHENA_VLLM_API_KEY.Trim()) {
        $env:ATHENA_VLLM_API_KEY = 'athena-local'
    }
    $env:ATHENA_VLLM_MODEL = $ResolvedServedModelName
    Invoke-SharedVllmBootstrap -ResolvedVllmModelDir $ResolvedVllmModelDir -ResolvedPython $ResolvedPython -ResolvedServedModelName $env:ATHENA_VLLM_MODEL -ResolvedBaseUrl $ResolvedPrivateBaseUrl

    if (-not $env:QTWEBENGINE_DISABLE_SANDBOX) { $env:QTWEBENGINE_DISABLE_SANDBOX = '1' }
    if (-not $env:QT_LOGGING_RULES) {
        $env:QT_LOGGING_RULES = 'qt.webenginecontext.warning=false;qt.webenginecontext.info=false;qt.webenginecontext.debug=false;qt.qpa.gl=false'
    }
    if (-not $env:QT_OPENGL) { $env:QT_OPENGL = 'software' }
    if (-not $env:QT_QUICK_BACKEND) { $env:QT_QUICK_BACKEND = 'software' }
    $RequiredQtFlags = @('--no-sandbox','--disable-gpu-sandbox','--disable-gpu','--disable-gpu-compositing','--use-angle=swiftshader','--disable-logging','--log-level=3')
    $ExistingQtFlags = @()
    if ($env:QTWEBENGINE_CHROMIUM_FLAGS) {
        $ExistingQtFlags = $env:QTWEBENGINE_CHROMIUM_FLAGS -split "\s+" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
    }
    foreach ($Flag in $RequiredQtFlags) {
        if ($ExistingQtFlags -notcontains $Flag) { $ExistingQtFlags += $Flag }
    }
    $env:QTWEBENGINE_CHROMIUM_FLAGS = ($ExistingQtFlags -join ' ').Trim()

    $CommandArgs = @($PrivateQtUi)
    if ($Tools) { $CommandArgs += '--tools' }

    Write-Host 'Launching Athena V5 exclusive desktop...'
    Write-Host "scope=private model=$ResolvedModelDir"
    Write-Host "config=$GuiConfigPath"
    Write-Host "prompt=$SystemPromptPath"
    Write-Host "logs=$DesktopLogDir"
    Write-Host "assets=$TranscriptHtml"
    Write-Host "runtime=vllm_openai base_url=$($env:ATHENA_VLLM_BASE_URL) served_model=$($env:ATHENA_VLLM_MODEL)"

    & $ResolvedPython @CommandArgs
    $exitCode = $LASTEXITCODE
} finally {
    foreach ($name in $envNames) {
        $prior = $originalEnv[$name]
        if ($null -eq $prior) {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        } else {
            Set-Item -Path "Env:$name" -Value $prior
        }
    }
}

if ($MyInvocation.InvocationName -eq '.') {
    $global:LASTEXITCODE = $exitCode
    return
}
exit $exitCode
