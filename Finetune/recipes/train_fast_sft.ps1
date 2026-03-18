param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FinetuneRoot = Split-Path -Parent $ScriptDir

$RunTraining = Join-Path $FinetuneRoot "run_training.ps1"
if (-not (Test-Path -LiteralPath $RunTraining)) {
    throw "run_training.ps1 not found: $RunTraining"
}

$ArgsFile = Join-Path $ScriptDir "fast_sft.json"
if (-not (Test-Path -LiteralPath $ArgsFile)) {
    throw "Args file not found: $ArgsFile"
}

$invokeArgs = @{
    ArgsFile = $ArgsFile
}
if ($DryRun) {
    $invokeArgs.DryRun = $true
}

& $RunTraining @invokeArgs
