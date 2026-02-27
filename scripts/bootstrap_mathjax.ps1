[CmdletBinding()]
param(
    [string]$ProjectRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ProjectRoot -or $ProjectRoot.Trim().Length -eq 0) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $ScriptDir
}
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

$MathJaxVersion = "3.2.2"
$MathJaxUrl = "https://github.com/mathjax/MathJax/archive/refs/tags/$MathJaxVersion.zip"

$AssetsRoot = Join-Path $ProjectRoot "assets\mathjax"
$TargetEs5Dir = Join-Path $AssetsRoot "es5"
$TargetMain = Join-Path $TargetEs5Dir "tex-mml-chtml.js"

if (Test-Path -LiteralPath $TargetMain) {
    Write-Host "MathJax already present at: $TargetMain"
    exit 0
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("athena-mathjax-" + [guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempRoot "mathjax.zip"

try {
    New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $AssetsRoot -Force | Out-Null

    Write-Host "Downloading MathJax v$MathJaxVersion from $MathJaxUrl"
    Invoke-WebRequest -Uri $MathJaxUrl -OutFile $ZipPath -UseBasicParsing

    Write-Host "Extracting MathJax archive..."
    Expand-Archive -Path $ZipPath -DestinationPath $TempRoot -Force

    $Es5SourceDir = Get-ChildItem -Path $TempRoot -Recurse -Directory -Filter "es5" |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "tex-mml-chtml.js") } |
        Select-Object -First 1

    if ($null -eq $Es5SourceDir) {
        throw "Could not find MathJax es5 directory in downloaded archive."
    }

    if (Test-Path -LiteralPath $TargetEs5Dir) {
        Remove-Item -LiteralPath $TargetEs5Dir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TargetEs5Dir -Force | Out-Null
    Copy-Item -Path (Join-Path $Es5SourceDir.FullName "*") -Destination $TargetEs5Dir -Recurse -Force

    if (-not (Test-Path -LiteralPath $TargetMain)) {
        throw "MathJax bootstrap finished but expected file is missing: $TargetMain"
    }

    Write-Host "MathJax bootstrap complete: $TargetMain"
    exit 0
} catch {
    Write-Error "MathJax bootstrap failed: $($_.Exception.Message)"
    exit 1
} finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
