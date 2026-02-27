[CmdletBinding()]
param(
    [switch]$AttemptMathJaxBootstrap = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$VenvLocal = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvWorkspace = Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe"

$Results = @()

function Add-CheckResult {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Passed,
        [Parameter(Mandatory = $true)][string]$Details
    )
    $script:Results += [pscustomobject]@{
        check   = $Name
        passed  = $Passed
        details = $Details
    }
}

if (Test-Path -LiteralPath $VenvLocal) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvLocal).Path
} elseif (Test-Path -LiteralPath $VenvWorkspace) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvWorkspace).Path
} else {
    Add-CheckResult -Name "python_path" -Passed $false -Details "No venv python found."
    $Results | Format-Table -AutoSize | Out-String | Write-Host
    exit 1
}
Add-CheckResult -Name "python_path" -Passed $true -Details $PythonExe

# 1) Import probe for Qt + local modules.
& $PythonExe -c "import athena_paths,qt_render,tk_chat,wrap;import PySide6;from PySide6.QtWebEngineWidgets import QWebEngineView" *> $null
if ($LASTEXITCODE -eq 0) {
    Add-CheckResult -Name "imports_probe" -Passed $true -Details "Qt + local imports resolved."
} else {
    Add-CheckResult -Name "imports_probe" -Passed $false -Details "Import probe failed."
}

# 2) MathJax local bundle check (or bootstrap result).
$MathJaxMain = Join-Path $ProjectRoot "assets\mathjax\es5\tex-mml-chtml.js"
if (Test-Path -LiteralPath $MathJaxMain) {
    Add-CheckResult -Name "mathjax_bundle" -Passed $true -Details "Local MathJax present."
} elseif ($AttemptMathJaxBootstrap) {
    $BootstrapScript = Join-Path $ProjectRoot "scripts\bootstrap_mathjax.ps1"
    if (-not (Test-Path -LiteralPath $BootstrapScript)) {
        Add-CheckResult -Name "mathjax_bundle" -Passed $false -Details "Missing bootstrap script."
    } else {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $BootstrapScript -ProjectRoot $ProjectRoot *> $null
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $MathJaxMain)) {
            Add-CheckResult -Name "mathjax_bundle" -Passed $true -Details "Bootstrapped successfully."
        } else {
            Add-CheckResult -Name "mathjax_bundle" -Passed $false -Details "Bootstrap failed."
        }
    }
} else {
    Add-CheckResult -Name "mathjax_bundle" -Passed $false -Details "Missing and bootstrap disabled."
}

# 3) Parser check for launcher.
$tokens = $null
$errs = $null
[void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $ProjectRoot "run_ui.ps1"), [ref]$tokens, [ref]$errs)
if ($errs -and $errs.Count -gt 0) {
    Add-CheckResult -Name "run_ui_parser" -Passed $false -Details (($errs | ForEach-Object { $_.Message }) -join "; ")
} else {
    Add-CheckResult -Name "run_ui_parser" -Passed $true -Details "run_ui.ps1 syntax OK."
}

# 4) Compile checks for qt_ui.py and qt_render.py.
$CompileScript = @'
from pathlib import Path
targets = ["qt_ui.py", "qt_render.py"]
for t in targets:
    compile(Path(t).read_text(encoding="utf-8-sig"), t, "exec")
print("ok")
'@
$CompileScript | & $PythonExe - *> $null
if ($LASTEXITCODE -eq 0) {
    Add-CheckResult -Name "python_compile" -Passed $true -Details "qt_ui.py + qt_render.py compile OK."
} else {
    Add-CheckResult -Name "python_compile" -Passed $false -Details "Python compile check failed."
}

$Failed = @($Results | Where-Object { -not $_.passed })
$Results | Format-Table -AutoSize | Out-String | Write-Host
if ($Failed.Count -gt 0) {
    Write-Host "Smoke summary: FAILED ($($Failed.Count)/$($Results.Count) checks failed)." -ForegroundColor Yellow
    exit 1
}

Write-Host "Smoke summary: PASS ($($Results.Count) checks)." -ForegroundColor Green
exit 0
