[CmdletBinding()]
param(
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $AppRoot)
$EntryScript = Join-Path $AppRoot "app.py"

function Resolve-PythonExe {
    param([string]$ExplicitPath)
    if ($ExplicitPath -and (Test-Path -LiteralPath $ExplicitPath)) {
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $candidates = @()
    if ($env:VIRTUAL_ENV) {
        $candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    }
    $candidates += (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
    $candidates += (Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe")

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    throw "No Python runtime found. Activate a venv or create .venv first."
}

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
if (-not (Test-Path -LiteralPath $EntryScript)) {
    throw "Finetune Studio entry script not found: $EntryScript"
}

Set-Location -LiteralPath $ProjectRoot
Write-Host "Launching Finetune Studio..."
& $ResolvedPython $EntryScript
$ExitCode = $LASTEXITCODE

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $ExitCode
    return
}

exit $ExitCode
