[CmdletBinding()]
param(
    [string]$ModelDir = "",
    [switch]$LegacyTk,
    [switch]$NoAutoInstallDeps,
    [switch]$NoMathJaxBootstrap,
    [switch]$BootstrapVerbose
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvLocal = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvWorkspace = Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe"
$LogsDir = Join-Path $ProjectRoot "logs"
$UiEventsLog = Join-Path $LogsDir "ui_events.jsonl"
$BootstrapStatePath = Join-Path $LogsDir "bootstrap_state.json"

try {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
} catch {
    # Non-fatal.
}

function Write-BootstrapInfo {
    param([string]$Message)
    if ($BootstrapVerbose) {
        Write-Host "[bootstrap] $Message"
    }
}

function Add-UiEvent {
    param(
        [Parameter(Mandatory = $true)][string]$Event,
        [Parameter(Mandatory = $true)][string]$Mode,
        [string]$ModelDir = "",
        [hashtable]$Details = @{}
    )
    try {
        $payload = [ordered]@{
            timestamp = [DateTime]::UtcNow.ToString("o")
            event     = $Event
            mode      = $Mode
            model_dir = $ModelDir
            details   = $Details
        }
        Add-Content -LiteralPath $UiEventsLog -Value ($payload | ConvertTo-Json -Compress -Depth 8)
    } catch {
        # Best effort only.
    }
}

function Write-BootstrapState {
    param([Parameter(Mandatory = $true)][hashtable]$State)
    try {
        $State.timestamp = [DateTime]::UtcNow.ToString("o")
        Set-Content -LiteralPath $BootstrapStatePath -Value ($State | ConvertTo-Json -Depth 8)
    } catch {
        # Diagnostics only.
    }
}

if (Test-Path -LiteralPath $VenvLocal) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvLocal).Path
} elseif (Test-Path -LiteralPath $VenvWorkspace) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvWorkspace).Path
} else {
    throw "No venv python found. Expected either: $VenvLocal or $VenvWorkspace"
}

function Test-QtWebUiDeps {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    $QuotedPython = '"' + $PythonExe + '"'
    $ImportProbe = $QuotedPython + ' -c "import PySide6; from PySide6.QtWebEngineWidgets import QWebEngineView" >nul 2>nul'
    cmd.exe /d /c $ImportProbe | Out-Null
    Write-BootstrapInfo "Qt dependency probe exit code=$LASTEXITCODE"
    return ($LASTEXITCODE -eq 0)
}

function Install-QtDeps {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$RequirementsPath
    )
    Add-UiEvent -Event "deps_install_attempt" -Mode "qt-web" -Details @{ method = "requirements"; requirements = $RequirementsPath }
    if (Test-Path -LiteralPath $RequirementsPath) {
        & $PythonExe -m pip install --disable-pip-version-check -r $RequirementsPath
        $ExitCode = $LASTEXITCODE
        Add-UiEvent -Event "deps_install_result" -Mode "qt-web" -Details @{ method = "requirements"; success = ($ExitCode -eq 0); exit_code = $ExitCode }
        if ($ExitCode -eq 0) {
            return $true
        }
    }

    # Recovery path: UI essentials only.
    Add-UiEvent -Event "deps_install_attempt" -Mode "qt-web" -Details @{ method = "ui-only" }
    & $PythonExe -m pip install --disable-pip-version-check markdown-it-py PySide6 PySide6-Addons
    $UiOnlyExit = $LASTEXITCODE
    Add-UiEvent -Event "deps_install_result" -Mode "qt-web" -Details @{ method = "ui-only"; success = ($UiOnlyExit -eq 0); exit_code = $UiOnlyExit }
    return ($UiOnlyExit -eq 0)
}

function Invoke-MathJaxBootstrap {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)
    $BootstrapScript = Join-Path $ProjectRoot "scripts\bootstrap_mathjax.ps1"
    if (-not (Test-Path -LiteralPath $BootstrapScript)) {
        Write-Warning "MathJax bootstrap script missing: $BootstrapScript"
        return $false
    }

    Add-UiEvent -Event "mathjax_bootstrap_attempt" -Mode "qt-web" -Details @{ script = $BootstrapScript }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $BootstrapScript -ProjectRoot $ProjectRoot
    $ExitCode = $LASTEXITCODE
    Add-UiEvent -Event "mathjax_bootstrap_result" -Mode "qt-web" -Details @{ success = ($ExitCode -eq 0); exit_code = $ExitCode }
    return ($ExitCode -eq 0)
}

$QtUiPy = Join-Path $ProjectRoot "qt_ui.py"
$TkUiPy = Join-Path $ProjectRoot "ui.py"
$UiPy = if ($LegacyTk) { $TkUiPy } else { $QtUiPy }
if (-not (Test-Path -LiteralPath $UiPy)) {
    throw "UI entrypoint not found: $UiPy"
}

if (-not $LegacyTk) {
    $RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
    $QtReady = Test-QtWebUiDeps -PythonExe $PythonExe
    Add-UiEvent -Event "deps_check" -Mode "qt-web" -Details @{ success = $QtReady; no_auto_install = [bool]$NoAutoInstallDeps }

    if (-not $QtReady -and -not $NoAutoInstallDeps) {
        $null = Install-QtDeps -PythonExe $PythonExe -RequirementsPath $RequirementsPath
        $QtReady = Test-QtWebUiDeps -PythonExe $PythonExe
        Add-UiEvent -Event "deps_check" -Mode "qt-web" -Details @{ success = $QtReady; after_install = $true }
    } elseif (-not $QtReady -and $NoAutoInstallDeps) {
        Write-Warning "Qt dependencies missing and -NoAutoInstallDeps was specified."
    }

    if (-not $QtReady) {
        Write-Warning (
            "Qt UI requires PySide6 + QtWebEngine. Falling back to legacy Tk UI.`n" +
            "Manual install command:`n" +
            "  $PythonExe -m pip install -r $RequirementsPath"
        )
        $UiPy = $TkUiPy
        $LegacyTk = $true
    }

    if (-not $LegacyTk) {
        $MathJaxMain = Join-Path $ProjectRoot "assets\mathjax\es5\tex-mml-chtml.js"
        if (-not (Test-Path -LiteralPath $MathJaxMain)) {
            if (-not $NoMathJaxBootstrap) {
                $null = Invoke-MathJaxBootstrap -ProjectRoot $ProjectRoot
            } else {
                Write-Warning "-NoMathJaxBootstrap specified; skipping local MathJax bootstrap."
            }
        }
    }
}

$UiArgs = @($UiPy)
$SelectedModelDir = ""
if ($ModelDir -and $ModelDir.Trim().Length -gt 0) {
    $ModelCandidate = if ([System.IO.Path]::IsPathRooted($ModelDir)) { $ModelDir } else { Join-Path $ProjectRoot $ModelDir }
    if (-not (Test-Path -LiteralPath $ModelCandidate)) {
        throw "Model path not found: $ModelCandidate"
    }
    $ResolvedModelDir = (Resolve-Path -LiteralPath $ModelCandidate).Path
    $UiArgs += @("--model-dir", $ResolvedModelDir)
    $SelectedModelDir = $ResolvedModelDir
}

$Mode = if ($LegacyTk) { "legacy-tk" } else { "qt-web" }
$DepsReady = if ($LegacyTk) { $false } else { $true }
$MathJaxReady = $false
if (-not $LegacyTk) {
    $MathJaxMain = Join-Path $ProjectRoot "assets\mathjax\es5\tex-mml-chtml.js"
    $MathJaxReady = Test-Path -LiteralPath $MathJaxMain
}

Add-UiEvent -Event "launch_start" -Mode $Mode -ModelDir $SelectedModelDir -Details @{
    no_auto_install_deps = [bool]$NoAutoInstallDeps
    no_mathjax_bootstrap = [bool]$NoMathJaxBootstrap
}
Add-UiEvent -Event "ui_mode_selected" -Mode $Mode -ModelDir $SelectedModelDir -Details @{
    deps_ready = $DepsReady
    mathjax_ready = $MathJaxReady
}
Write-BootstrapState -State @{
    ui_mode = $Mode
    deps_ready = $DepsReady
    mathjax_ready = $MathJaxReady
    no_auto_install_deps = [bool]$NoAutoInstallDeps
    no_mathjax_bootstrap = [bool]$NoMathJaxBootstrap
}

$DepsReadyStr = $DepsReady.ToString().ToLowerInvariant()
$MathJaxReadyStr = $MathJaxReady.ToString().ToLowerInvariant()
Write-Host "ui_mode=$Mode deps_ready=$DepsReadyStr mathjax_ready=$MathJaxReadyStr"
Write-Host "Launching UI mode=$Mode with: $PythonExe"
Set-Location -LiteralPath $ProjectRoot

if (-not $LegacyTk) {
    if (-not $env:QTWEBENGINE_DISABLE_SANDBOX) {
        $env:QTWEBENGINE_DISABLE_SANDBOX = "1"
    }
    if (-not $env:QT_LOGGING_RULES) {
        $env:QT_LOGGING_RULES = "qt.webenginecontext.warning=false;qt.webenginecontext.info=false;qt.webenginecontext.debug=false;qt.qpa.gl=false"
    }
    $RequiredQtFlags = @(
        "--no-sandbox",
        "--disable-gpu-sandbox",
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--use-angle=swiftshader",
        "--disable-logging",
        "--log-level=3"
    )
    $ExistingFlags = @()
    if ($env:QTWEBENGINE_CHROMIUM_FLAGS) {
        $ExistingFlags = $env:QTWEBENGINE_CHROMIUM_FLAGS -split "\s+" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
    }
    foreach ($flag in $RequiredQtFlags) {
        if ($ExistingFlags -notcontains $flag) {
            $ExistingFlags += $flag
        }
    }
    $env:QTWEBENGINE_CHROMIUM_FLAGS = ($ExistingFlags -join " ")
    if (-not $env:QT_OPENGL) {
        $env:QT_OPENGL = "software"
    }
    if (-not $env:QT_QUICK_BACKEND) {
        $env:QT_QUICK_BACKEND = "software"
    }
}

& $PythonExe @UiArgs
$LaunchExitCode = $LASTEXITCODE

if ($LaunchExitCode -ne 0 -and -not $LegacyTk) {
    Write-Warning "Qt UI exited with code $LaunchExitCode. Falling back to legacy Tk UI."
    Add-UiEvent -Event "ui_mode_selected" -Mode "legacy-tk" -ModelDir $SelectedModelDir -Details @{
        reason = "qt_exit_nonzero"
        qt_exit_code = $LaunchExitCode
    }
    $TkArgs = @($TkUiPy)
    if ($SelectedModelDir -and $SelectedModelDir.Trim().Length -gt 0) {
        $TkArgs += @("--model-dir", $SelectedModelDir)
    }
    Write-Host "Launching fallback UI mode=legacy-tk with: $PythonExe"
    & $PythonExe @TkArgs
    $LaunchExitCode = $LASTEXITCODE
}

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $LaunchExitCode
    return
}
exit $LaunchExitCode
