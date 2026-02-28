param(
    [string]$CheckpointPath = "models/tuned/AthenaV7.02/checkpoint-25",
    [string]$OutputDir = "models/tuned/AthenaV7.03_recover",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$Runner = Join-Path $ScriptDir "run_training.ps1"
$RecoverArgs = Join-Path $ScriptDir "finetune_args_recover.json"

$InvokeArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $Runner,
    "-ArgsFile", $RecoverArgs,
    "-ModelPath", $CheckpointPath,
    "-OutputDir", $OutputDir
)

if ($DryRun) {
    $InvokeArgs += "-DryRun"
}

Write-Host "Starting recovery training run..."
Write-Host "checkpoint=$CheckpointPath"
Write-Host "output_dir=$OutputDir"

powershell @InvokeArgs
