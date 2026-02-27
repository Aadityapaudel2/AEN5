[CmdletBinding()]
param(
    [string]$ModelPath = "D:\AthenaPlayground\AthenaV5\models\Qwen3-4B-Instruct-2507",
    [string]$TrainFile = "D:\AthenaPlayground\AthenaV5\Finetune\trainingdata\math_canon_v2_1\math_master_canon_v2_1_chat_sft_train.jsonl",
    [string]$OutputDir = "D:\AthenaPlayground\AthenaV5\models\tuned\math_canon_v2_1_run1",
    [int]$MaxSeqLen = 2048,
    [int]$BatchSize = 1,
    [int]$GradAccum = 8,
    [double]$LearningRate = 2e-5,
    [double]$Epochs = 2.0,
    [int]$LoggingSteps = 10,
    [int]$SaveSteps = 100,
    [switch]$Bf16,
    [switch]$Fp16,
    [switch]$GradientCheckpointing
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "D:\AthenaPlayground\AthenaV5\Finetune"
$VenvLocal = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvWorkspace = "D:\AthenaPlayground\.venv\Scripts\python.exe"

if (Test-Path -LiteralPath $VenvLocal) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvLocal).Path
} elseif (Test-Path -LiteralPath $VenvWorkspace) {
    $PythonExe = (Resolve-Path -LiteralPath $VenvWorkspace).Path
} else {
    throw "No venv python found. Checked: $VenvLocal and $VenvWorkspace"
}

if (-not (Test-Path -LiteralPath $ModelPath)) {
    throw "Model path not found: $ModelPath"
}
if (-not (Test-Path -LiteralPath $TrainFile)) {
    throw "Train file not found: $TrainFile"
}

$Args = @(
    "D:\AthenaPlayground\AthenaV5\Finetune\train.py",
    "--model_name_or_path", $ModelPath,
    "--train_file", $TrainFile,
    "--output_dir", $OutputDir,
    "--max_seq_length", "$MaxSeqLen",
    "--per_device_train_batch_size", "$BatchSize",
    "--gradient_accumulation_steps", "$GradAccum",
    "--learning_rate", "$LearningRate",
    "--num_train_epochs", "$Epochs",
    "--logging_steps", "$LoggingSteps",
    "--save_steps", "$SaveSteps"
)

if ($Bf16) { $Args += "--bf16" }
if ($Fp16) { $Args += "--fp16" }
if ($GradientCheckpointing) { $Args += "--gradient_checkpointing" }

Write-Host "Launching training with: $PythonExe"
Write-Host "Model: $ModelPath"
Write-Host "Train: $TrainFile"
Write-Host "Out:   $OutputDir"

Set-Location -LiteralPath $ProjectRoot
& $PythonExe @Args
exit $LASTEXITCODE
