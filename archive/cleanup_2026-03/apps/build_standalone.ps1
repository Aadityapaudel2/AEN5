[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EntryScript = Join-Path $AppRoot "app.py"
$AppName = "TwoModelDialogueEvaluator"
$DistRoot = Join-Path $AppRoot "dist"
$BuildRoot = Join-Path $AppRoot "build"
$SpecRoot = Join-Path $BuildRoot "spec"
$WorkRoot = Join-Path $BuildRoot "work"

function Resolve-PythonExe {
    param([string]$ExplicitPath)
    if ($ExplicitPath -and (Test-Path -LiteralPath $ExplicitPath)) {
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }
    $Candidates = @()
    if ($env:VIRTUAL_ENV) {
        $Candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\\python.exe")
    }
    $SearchRoots = @()
    $Cursor = $AppRoot
    for ($i = 0; $i -lt 4; $i++) {
        if (-not $Cursor) { break }
        $SearchRoots += $Cursor
        $Next = Split-Path -Parent $Cursor
        if (-not $Next -or $Next -eq $Cursor) { break }
        $Cursor = $Next
    }
    foreach ($Root in ($SearchRoots | Select-Object -Unique)) {
        if ($Root) {
            $Candidates += (Join-Path $Root ".venv\\Scripts\\python.exe")
        }
    }
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    $Cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($Cmd) { return $Cmd.Source }
    throw "No Python runtime found. Activate/create a venv first."
}

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
if (-not (Test-Path -LiteralPath $EntryScript)) {
    throw "app.py not found: $EntryScript"
}

& $ResolvedPython -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed for $ResolvedPython. Install with: `"$ResolvedPython`" -m pip install pyinstaller"
}

if ($Clean) {
    foreach ($target in @($BuildRoot, (Join-Path $DistRoot $AppName))) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

New-Item -ItemType Directory -Path $SpecRoot -Force | Out-Null
New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null

$PyArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--windowed",
    "--onedir",
    "--name", $AppName,
    "--distpath", $DistRoot,
    "--workpath", $WorkRoot,
    "--specpath", $SpecRoot,
    "--hidden-import", "runtime",
    "--hidden-import", "runtime.events",
    "--hidden-import", "runtime.engine",
    "--hidden-import", "runtime.session",
    "--hidden-import", "transformers",
    "--hidden-import", "accelerate",
    "--exclude-module", "bitsandbytes",
    "--exclude-module", "datasets",
    "--exclude-module", "matplotlib",
    "--exclude-module", "pandas",
    "--exclude-module", "pyarrow",
    "--exclude-module", "tensorboard",
    "--exclude-module", "tensorflow",
    "--exclude-module", "torchaudio",
    $EntryScript
)

Set-Location -LiteralPath $AppRoot
Write-Host "Building $AppName standalone..."
& $ResolvedPython @PyArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$OutputDir = Join-Path $DistRoot $AppName
Write-Host "Standalone evaluator built at: $OutputDir"
