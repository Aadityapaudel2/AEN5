param(
    [switch]$AllowCpu,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$RunTraining = Join-Path $ScriptDir "run_training.ps1"
if (-not (Test-Path -LiteralPath $RunTraining)) {
    throw "run_training.ps1 not found: $RunTraining"
}

$ArgsFile = Join-Path $ScriptDir "orchestrator_v1_fast.json"
if (-not (Test-Path -LiteralPath $ArgsFile)) {
    throw "Args file not found: $ArgsFile"
}

function Resolve-ExistingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseDir,
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )
    $Candidate = if ([System.IO.Path]::IsPathRooted($PathValue)) { $PathValue } else { Join-Path $BaseDir $PathValue }
    return (Resolve-Path -LiteralPath $Candidate).Path
}

function Resolve-OutputPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseDir,
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )
    $Normalized = ($PathValue -replace "/", "\").Trim()
    $UseFutureTunedRoot = -not [System.IO.Path]::IsPathRooted($Normalized) -and (
        $Normalized -ieq "models\tuned" -or
        $Normalized.StartsWith("models\tuned\", [System.StringComparison]::OrdinalIgnoreCase)
    )
    if ($UseFutureTunedRoot) {
        $TunedRoot = if ($env:ATHENA_TUNED_MODELS_ROOT) { $env:ATHENA_TUNED_MODELS_ROOT } else { "N:\AthenaModels\tuned" }
        $Suffix = ""
        if ($Normalized.Length -gt "models\tuned".Length) {
            $Suffix = $Normalized.Substring("models\tuned".Length).TrimStart("\")
        }
        $Candidate = if ($Suffix) { Join-Path $TunedRoot $Suffix } else { $TunedRoot }
    } else {
        $Candidate = if ([System.IO.Path]::IsPathRooted($Normalized)) { $Normalized } else { Join-Path $BaseDir $Normalized }
    }
    if (-not (Test-Path -LiteralPath $Candidate)) {
        New-Item -ItemType Directory -Path $Candidate -Force | Out-Null
    }
    return (Resolve-Path -LiteralPath $Candidate).Path
}

$Config = Get-Content -LiteralPath $ArgsFile -Raw -Encoding UTF8 | ConvertFrom-Json
$ResolvedModelPath = Resolve-ExistingPath -BaseDir $ProjectRoot -PathValue ([string]$Config.paths.model_path)
$ResolvedTrainFile = Resolve-ExistingPath -BaseDir $ProjectRoot -PathValue ([string]$Config.paths.train_file)
$ResolvedOutputDir = Resolve-OutputPath -BaseDir $ProjectRoot -PathValue ([string]$Config.paths.output_dir)

$SourceSnapshotDir = Join-Path $ResolvedOutputDir "_finetune_source"
if (-not (Test-Path -LiteralPath $SourceSnapshotDir)) {
    New-Item -ItemType Directory -Path $SourceSnapshotDir -Force | Out-Null
}

$TrainFileName = Split-Path -Leaf $ResolvedTrainFile
$ScenarioCardsPath = Join-Path (Split-Path -Parent $ResolvedTrainFile) "scenario_cards.yaml"
$ManifestPath = Join-Path (Split-Path -Parent $ResolvedTrainFile) "manifest.json"
$ArgsSnapshotPath = Join-Path $SourceSnapshotDir "orchestrator_v1_fast.args.json"
$TrainSnapshotPath = Join-Path $SourceSnapshotDir $TrainFileName
$ScenarioSnapshotPath = Join-Path $SourceSnapshotDir "scenario_cards.yaml"
$ManifestSnapshotPath = Join-Path $SourceSnapshotDir "manifest.json"
$FinetuneCardPath = Join-Path $ResolvedOutputDir "FINETUNE_CARD.md"

Copy-Item -LiteralPath $ArgsFile -Destination $ArgsSnapshotPath -Force
Copy-Item -LiteralPath $ResolvedTrainFile -Destination $TrainSnapshotPath -Force
if (Test-Path -LiteralPath $ScenarioCardsPath) {
    Copy-Item -LiteralPath $ScenarioCardsPath -Destination $ScenarioSnapshotPath -Force
}
if (Test-Path -LiteralPath $ManifestPath) {
    Copy-Item -LiteralPath $ManifestPath -Destination $ManifestSnapshotPath -Force
}

$FinetuneCard = @"
# Finetune Card

## Expected Checkpoint

- Output directory: `$ResolvedOutputDir`
- Base model: `$ResolvedModelPath`
- Training mode: `SFT`
- Adapter: `No`

## Data

- Train file: `$ResolvedTrainFile`
- Copied train file: `$TrainSnapshotPath`
- Copied args file: `$ArgsSnapshotPath`
- Copied scenario cards: `$(if (Test-Path -LiteralPath $ScenarioSnapshotPath) { $ScenarioSnapshotPath } else { 'not available' })`
- Copied manifest: `$(if (Test-Path -LiteralPath $ManifestSnapshotPath) { $ManifestSnapshotPath } else { 'not available' })`

## Intent

Teach a 4B model the minimal orchestrator role for math and logic tasks, with selective querying behavior over two external solver personas rather than defaulting to a single monolithic answer path.

## Reason For Finetune

This run seeds the orchestration layer before the full multi-model runtime is built. The goal is to make the model treat solver querying as a natural next action when warranted, while keeping the role pure and disciplined.

## Expected Behavior

- Answer directly when the request is trivial and reliable from first principles.
- Ask exactly one focused clarification when essential information is missing.
- Query Solver-A for direct formal derivation tasks.
- Query Solver-B for alternate-path or edge-case checking.
- Query both only when dual evidence is justified.
- Reconcile disagreement cases into a single lawful final answer.
- Stay within the orchestrator wire format and avoid role blending.

## Notes

- This run is supervised finetuning, not an adapter.
- The copied source snapshot is intended to preserve provenance even when the trained checkpoint lives outside the repo on `N:\AthenaModels\tuned`.
"@
$FinetuneCard | Set-Content -LiteralPath $FinetuneCardPath -Encoding UTF8

$RunRoot = Join-Path $ScriptDir "runs\orchestrator_v1_fast"
if (-not (Test-Path -LiteralPath $RunRoot)) {
    New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$TranscriptPath = Join-Path $RunRoot "train_$Stamp.log"
$MetaPath = Join-Path $RunRoot "train_$Stamp.meta.json"

$Meta = [ordered]@{
    started_at = (Get-Date).ToString("o")
    args_file = (Resolve-Path -LiteralPath $ArgsFile).Path
    transcript = $TranscriptPath
    mode = "orchestrator_v1_fast"
    dry_run = [bool]$DryRun
    allow_cpu = [bool]$AllowCpu
    base_model = $ResolvedModelPath
    expected_output_dir = $ResolvedOutputDir
    train_file = $ResolvedTrainFile
    finetune_card = $FinetuneCardPath
    source_snapshot_dir = $SourceSnapshotDir
}
$Meta | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $MetaPath -Encoding UTF8

Start-Transcript -Path $TranscriptPath -Force | Out-Null
try {
    $invokeArgs = @{
        ArgsFile = $ArgsFile
    }
    if ($AllowCpu) {
        $invokeArgs.AllowCpu = $true
    }
    if ($DryRun) {
        $invokeArgs.DryRun = $true
    }

    Write-Host "orchestrator_fast_meta=$MetaPath"
    Write-Host "orchestrator_fast_log=$TranscriptPath"
    Write-Host "orchestrator_fast_card=$FinetuneCardPath"
    Write-Host "orchestrator_fast_base_model=$ResolvedModelPath"
    & $RunTraining @invokeArgs
}
finally {
    Stop-Transcript | Out-Null
}
