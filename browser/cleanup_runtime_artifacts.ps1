[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$targets = @(
    "browser\__pycache__",
    "browser\tests\__pycache__",
    "miamioh\__pycache__",
    "institutions\__pycache__"
)

foreach ($relative in $targets) {
    $path = Join-Path $ProjectRoot $relative
    if (Test-Path -LiteralPath $path) {
        Remove-Item -Recurse -Force $path
        Write-Host "Removed $relative"
    }
}

Get-ChildItem -Path $ProjectRoot -Filter "temp_*" -File -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Force $_.FullName
    Write-Host "Removed temp file $($_.Name)"
}

Write-Host "Runtime artifact cleanup complete."
