[CmdletBinding()]
param(
    [string]$RepoUrl = "https://github.com/Aadityapaudel2/AthenaV5.git",
    [string]$Message = "",
    [switch]$StageAll,
    [switch]$NoCommit,
    [switch]$ForceWithLease
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is not installed or not in PATH."
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot

# Ensure main branch for this repo.
$current = (git rev-parse --abbrev-ref HEAD).Trim()
if ($current -ne "main") {
    git branch -M main
}

# Ensure origin remote points to requested GitHub repo.
try {
    git remote get-url origin | Out-Null
    git remote set-url origin $RepoUrl
} catch {
    git remote add origin $RepoUrl
}

if ($StageAll) {
    git add -A
}

$stagedFiles = (git diff --cached --name-only)
$hasStaged = -not [string]::IsNullOrWhiteSpace(($stagedFiles -join "").Trim())

if (-not $NoCommit) {
    if (-not $hasStaged) {
        Write-Host "No staged changes. Skipping commit."
    } else {
        if ([string]::IsNullOrWhiteSpace($Message)) {
            throw "Commit message is required when staged changes exist. Pass -Message `"your message`"."
        }
        git commit -m $Message
    }
}

if ($ForceWithLease) {
    git push -u origin main --force-with-lease
} else {
    git push -u origin main
}

Write-Host "Done."
