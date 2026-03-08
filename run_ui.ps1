[CmdletBinding()]
param(
    [switch]$Tools,
    [switch]$NoAutoInstallDeps,
    [int]$Port = 8000,
    [string]$PathPrefix = "/AthenaV5",
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$QtUi = Join-Path $ProjectRoot "qt_ui.py"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

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

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
if (-not (Test-Path -LiteralPath $QtUi)) {
    throw "qt_ui.py not found: $QtUi"
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

Set-Location -LiteralPath $ProjectRoot

if (-not $env:QTWEBENGINE_DISABLE_SANDBOX) { $env:QTWEBENGINE_DISABLE_SANDBOX = "1" }
if (-not $env:QT_LOGGING_RULES) {
    $env:QT_LOGGING_RULES = "qt.webenginecontext.warning=false;qt.webenginecontext.info=false;qt.webenginecontext.debug=false;qt.qpa.gl=false"
}
if (-not $env:QT_OPENGL) { $env:QT_OPENGL = "software" }
if (-not $env:QT_QUICK_BACKEND) { $env:QT_QUICK_BACKEND = "software" }
$RequiredQtFlags = @(
    "--no-sandbox",
    "--disable-gpu-sandbox",
    "--disable-gpu",
    "--disable-gpu-compositing",
    "--use-angle=swiftshader",
    "--disable-logging",
    "--log-level=3"
)
$ExistingQtFlags = @()
if ($env:QTWEBENGINE_CHROMIUM_FLAGS) {
    $ExistingQtFlags = $env:QTWEBENGINE_CHROMIUM_FLAGS -split "\s+" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
}
foreach ($Flag in $RequiredQtFlags) {
    if ($ExistingQtFlags -notcontains $Flag) {
        $ExistingQtFlags += $Flag
    }
}
$env:QTWEBENGINE_CHROMIUM_FLAGS = ($ExistingQtFlags -join " ").Trim()

$Args = @($QtUi)
if ($Tools) { $Args += "--tools" }

Write-Host "Launching Athena V5 desktop..."
Write-Host "mode=desktop engine=local tools=$([int][bool]$Tools)"
& $ResolvedPython @Args
$ExitCode = $LASTEXITCODE

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
