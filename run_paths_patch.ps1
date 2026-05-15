[CmdletBinding()]
param(
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$GuiScript = Join-Path $ProjectRoot "paths_patch.py"

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

if (-not (Test-Path -LiteralPath $GuiScript)) {
    throw "Paths Patch GUI not found: $GuiScript"
}

$ResolvedPython = Resolve-PythonExe -ExplicitPath $PythonExe
Set-Location -LiteralPath $ProjectRoot
& $ResolvedPython $GuiScript
exit $LASTEXITCODE
