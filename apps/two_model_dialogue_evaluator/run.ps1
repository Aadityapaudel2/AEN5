[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$ModelA = "",
    [string]$ModelB = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EntryScript = Join-Path $AppRoot "app.py"

function Resolve-PythonExe {
    param([string]$ExplicitPath)
    if ($ExplicitPath -and (Test-Path -LiteralPath $ExplicitPath)) {
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }
    $candidates = @()
    if ($env:VIRTUAL_ENV) {
        $candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\\python.exe")
    }
    $searchRoots = @()
    $cursor = $AppRoot
    for ($i = 0; $i -lt 4; $i++) {
        if (-not $cursor) { break }
        $searchRoots += $cursor
        $next = Split-Path -Parent $cursor
        if (-not $next -or $next -eq $cursor) { break }
        $cursor = $next
    }
    foreach ($root in ($searchRoots | Select-Object -Unique)) {
        if ($root) {
            $candidates += (Join-Path $root ".venv\\Scripts\\python.exe")
        }
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "No Python runtime found. Activate/create a venv first."
}

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
if (-not (Test-Path -LiteralPath $EntryScript)) {
    throw "app.py not found: $EntryScript"
}

$CommandArgs = @($EntryScript)
if ($ModelA) {
    $CommandArgs += "--model-a"
    $CommandArgs += $ModelA
}
if ($ModelB) {
    $CommandArgs += "--model-b"
    $CommandArgs += $ModelB
}

Set-Location -LiteralPath $AppRoot
Write-Host "Launching Two-Model Dialogue Evaluator..."
& $ResolvedPython @CommandArgs
$ExitCode = $LASTEXITCODE

if ($MyInvocation.InvocationName -eq ".") {
    $global:LASTEXITCODE = $ExitCode
    return
}
exit $ExitCode
