param(
    [string]$ArgsFile = "Finetune/finetune_args.json",
    [string]$ModelPath,
    [string]$TrainFile,
    [string]$OutputDir,
    [string]$ResumeFromCheckpoint,
    [switch]$AllowCpu,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

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
        [string]$PathValue,
        [bool]$CreateIfMissing = $true
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
    if ($CreateIfMissing -and -not (Test-Path -LiteralPath $Candidate)) {
        New-Item -ItemType Directory -Path $Candidate -Force | Out-Null
    }
    if (Test-Path -LiteralPath $Candidate) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }
    return [System.IO.Path]::GetFullPath($Candidate)
}

function Resolve-OptionalExistingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseDir,
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }
    $Candidate = if ([System.IO.Path]::IsPathRooted($PathValue)) { $PathValue } else { Join-Path $BaseDir $PathValue }
    if (-not (Test-Path -LiteralPath $Candidate)) {
        return $null
    }
    return (Resolve-Path -LiteralPath $Candidate).Path
}

function Get-BoolValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Value
    )
    return [System.Convert]::ToBoolean($Value)
}

function Add-BoolFlag {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$ArgumentList,
        [Parameter(Mandatory = $true)]
        [string]$FlagName,
        [Parameter(Mandatory = $true)]
        [object]$Enabled
    )
    if (Get-BoolValue -Value $Enabled) {
        $ArgumentList.Add($FlagName)
    }
}

function Get-ConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$ConfigObject,
        [Parameter(Mandatory = $true)]
        [string]$PropertyName,
        $DefaultValue = $null
    )
    if ($null -eq $ConfigObject) {
        return $DefaultValue
    }
    if ($ConfigObject.PSObject.Properties.Name -contains $PropertyName) {
        return $ConfigObject.$PropertyName
    }
    return $DefaultValue
}

function Get-PythonExeCandidates {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRootPath
    )

    $Candidates = [System.Collections.Generic.List[string]]::new()

    function Add-Candidate {
        param(
            [string]$CandidatePath
        )
        if ([string]::IsNullOrWhiteSpace($CandidatePath)) {
            return
        }
        if (-not (Test-Path -LiteralPath $CandidatePath)) {
            return
        }
        $Resolved = (Resolve-Path -LiteralPath $CandidatePath).Path
        if (-not $Candidates.Contains($Resolved)) {
            $Candidates.Add($Resolved)
        }
    }

    if ($env:VIRTUAL_ENV) {
        Add-Candidate (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    }
    Add-Candidate (Join-Path $ProjectRootPath ".venv\Scripts\python.exe")
    $ParentDir = Split-Path -Parent $ProjectRootPath
    if ($ParentDir) {
        Add-Candidate (Join-Path $ParentDir ".venv\Scripts\python.exe")
    }

    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd -and -not [string]::IsNullOrWhiteSpace($PythonCmd.Source)) {
        Add-Candidate $PythonCmd.Source
    }

    if ($Candidates.Count -eq 0) {
        throw "Python executable not found. Activate a venv or create .venv in the project root."
    }

    return $Candidates.ToArray()
}

function Invoke-TrainingProbe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,
        [Parameter(Mandatory = $true)]
        [string]$ModelPath,
        [Parameter(Mandatory = $true)]
        [string]$TrainFile
    )

    $ProbeScript = @'
import json
import sys
from pathlib import Path

def fail(stage, exc):
    print(json.dumps({"ok": False, "stage": stage, "error": f"{type(exc).__name__}: {exc}"}))
    raise SystemExit(0)

try:
    import accelerate
    import torch
    import transformers
    from transformers import AutoTokenizer
except Exception as exc:
    fail("imports", exc)

model_path = Path(sys.argv[1])
train_file = Path(sys.argv[2])

if not model_path.exists():
    print(json.dumps({"ok": False, "stage": "model_path", "error": f"Model path not found: {model_path}"}))
    raise SystemExit(0)

if not train_file.exists():
    print(json.dumps({"ok": False, "stage": "train_file", "error": f"Train file not found: {train_file}"}))
    raise SystemExit(0)

samples = []
try:
    with train_file.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            messages = payload.get("messages")
            if not isinstance(messages, list) or not messages:
                raise ValueError(f"Line {line_number}: missing non-empty 'messages' list")
            samples.append(messages)
except Exception as exc:
    fail("dataset_parse", exc)

if not samples:
    print(json.dumps({"ok": False, "stage": "dataset_parse", "error": "No usable training samples found"}))
    raise SystemExit(0)

try:
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), use_fast=True)
    if not hasattr(tokenizer, "apply_chat_template"):
        raise ValueError("Tokenizer must support apply_chat_template()")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token if tokenizer.eos_token is not None else "<|pad|>"
except Exception as exc:
    fail("tokenizer", exc)

lengths = []
try:
    for messages in samples:
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        lengths.append(len(tokenizer(rendered, add_special_tokens=False)["input_ids"]))
except Exception as exc:
    fail("token_lengths", exc)

lengths.sort()
p95_index = int(0.95 * (len(lengths) - 1))

print(json.dumps({
    "ok": True,
    "python": sys.executable,
    "python_version": sys.version.split()[0],
    "accelerate_version": accelerate.__version__,
    "transformers_version": transformers.__version__,
    "torch_version": torch.__version__,
    "cuda_available": bool(torch.cuda.is_available()),
    "cuda_version": torch.version.cuda or "",
    "device_count": int(torch.cuda.device_count()),
    "total_vram_gib": round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 2) if torch.cuda.is_available() and torch.cuda.device_count() > 0 else 0.0,
    "tokenizer_class": type(tokenizer).__name__,
    "sample_count": len(samples),
    "min_tokens": lengths[0],
    "p95_tokens": lengths[p95_index],
    "max_tokens": lengths[-1]
}))
'@

    $ProbeOutput = $ProbeScript | & $PythonExe - $ModelPath $TrainFile 2>$null
    if ($LASTEXITCODE -ne 0) {
        return [pscustomobject]@{
            ok = $false
            stage = "probe"
            error = "Probe exited with status $LASTEXITCODE for $PythonExe"
        }
    }

    $ProbeText = ($ProbeOutput | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($ProbeText)) {
        return [pscustomobject]@{
            ok = $false
            stage = "probe"
            error = "Probe produced no output for $PythonExe"
        }
    }

    try {
        return ($ProbeText | ConvertFrom-Json)
    } catch {
        return [pscustomobject]@{
            ok = $false
            stage = "probe_parse"
            error = "Unable to parse probe output for ${PythonExe}: $ProbeText"
        }
    }
}

function Resolve-TrainingPythonRuntime {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRootPath,
        [Parameter(Mandatory = $true)]
        [string]$ModelPath,
        [Parameter(Mandatory = $true)]
        [string]$TrainFile,
        [bool]$AllowCpuTraining = $false
    )

    $Candidates = Get-PythonExeCandidates -ProjectRootPath $ProjectRootPath
    $Failures = [System.Collections.Generic.List[string]]::new()
    $CpuFallback = $null

    foreach ($Candidate in $Candidates) {
        $Probe = Invoke-TrainingProbe -PythonExe $Candidate -ModelPath $ModelPath -TrainFile $TrainFile
        if (-not $Probe.ok) {
            $Failures.Add("${Candidate} [$($Probe.stage)] $($Probe.error)")
            continue
        }

        if ([bool]$Probe.cuda_available) {
            return [pscustomobject]@{
                python_exe = $Candidate
                probe = $Probe
            }
        }

        if (-not $CpuFallback) {
            $CpuFallback = [pscustomobject]@{
                python_exe = $Candidate
                probe = $Probe
            }
        }
        $Failures.Add("${Candidate} [cuda] CUDA unavailable")
    }

    if ($AllowCpuTraining -and $CpuFallback) {
        return $CpuFallback
    }

    $Message = "No compatible Python runtime found for training."
    if ($Failures.Count -gt 0) {
        $Message += "`nChecked:`n - " + ($Failures -join "`n - ")
    }
    if (-not $AllowCpuTraining) {
        $Message += "`nUse -AllowCpu only if CPU training is intentional."
    }
    throw $Message
}

$ResolvedArgsFile = Resolve-ExistingPath -BaseDir $ProjectRoot -PathValue $ArgsFile
$Config = Get-Content -LiteralPath $ResolvedArgsFile -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not $Config.paths) { throw "Missing 'paths' section in args file: $ResolvedArgsFile" }
if (-not $Config.accelerate) { throw "Missing 'accelerate' section in args file: $ResolvedArgsFile" }
if (-not $Config.train) { throw "Missing 'train' section in args file: $ResolvedArgsFile" }

$SelectedModelPath = if ($PSBoundParameters.ContainsKey("ModelPath")) { $ModelPath } else { [string]$Config.paths.model_path }
$SelectedTrainFile = if ($PSBoundParameters.ContainsKey("TrainFile")) { $TrainFile } else { [string]$Config.paths.train_file }
$SelectedOutputDir = if ($PSBoundParameters.ContainsKey("OutputDir")) { $OutputDir } else { [string]$Config.paths.output_dir }
$ConfigResumeCheckpoint = ""
if ($Config.paths.PSObject.Properties.Name -contains "resume_from_checkpoint") {
    $ConfigResumeCheckpoint = [string]$Config.paths.resume_from_checkpoint
}
$SelectedResumeCheckpoint = if ($PSBoundParameters.ContainsKey("ResumeFromCheckpoint")) { $ResumeFromCheckpoint } else { $ConfigResumeCheckpoint }

if ([string]::IsNullOrWhiteSpace($SelectedModelPath)) { throw "model_path is required." }
if ([string]::IsNullOrWhiteSpace($SelectedTrainFile)) { throw "train_file is required." }
if ([string]::IsNullOrWhiteSpace($SelectedOutputDir)) { throw "output_dir is required." }

$ResolvedModelPath = Resolve-ExistingPath -BaseDir $ProjectRoot -PathValue $SelectedModelPath
$ResolvedTrainFile = Resolve-ExistingPath -BaseDir $ProjectRoot -PathValue $SelectedTrainFile
$ResolvedOutputDir = Resolve-OutputPath -BaseDir $ProjectRoot -PathValue $SelectedOutputDir -CreateIfMissing:(-not $DryRun)
$ResolvedResumeCheckpoint = $null
if (-not [string]::IsNullOrWhiteSpace($SelectedResumeCheckpoint)) {
    $ResolvedResumeCheckpoint = Resolve-ExistingPath -BaseDir $ProjectRoot -PathValue $SelectedResumeCheckpoint
}

$RuntimeSelection = Resolve-TrainingPythonRuntime -ProjectRootPath $ProjectRoot -ModelPath $ResolvedModelPath -TrainFile $ResolvedTrainFile -AllowCpuTraining ([bool]$AllowCpu)
$PythonExe = [string]$RuntimeSelection.python_exe
$RuntimeProbe = $RuntimeSelection.probe
$ResolvedExpectedSamples = [int]$RuntimeProbe.sample_count

if ([int]$Config.train.expected_samples -gt 0 -and [int]$Config.train.expected_samples -ne $ResolvedExpectedSamples) {
    Write-Warning (
        "Config expected_samples=" + [int]$Config.train.expected_samples +
        " does not match train file count=" + $ResolvedExpectedSamples +
        ". Using the train file count."
    )
}

if ((Get-BoolValue -Value $Config.train.strict_no_truncation) -and ([int]$RuntimeProbe.max_tokens -gt [int]$Config.train.max_seq_length)) {
    throw (
        "Dataset max token length (" + [int]$RuntimeProbe.max_tokens +
        ") exceeds train.max_seq_length=" + [int]$Config.train.max_seq_length +
        " while strict_no_truncation is enabled."
    )
}

if ((Get-BoolValue -Value $Config.train.bf16) -and (Get-BoolValue -Value $Config.train.fp16)) {
    throw "Invalid config: both train.bf16 and train.fp16 are true. Enable only one."
}

$UseLora = Get-BoolValue -Value (Get-ConfigValue -ConfigObject $Config.train -PropertyName "use_lora" -DefaultValue $false)
$LoadIn4Bit = Get-BoolValue -Value (Get-ConfigValue -ConfigObject $Config.train -PropertyName "load_in_4bit" -DefaultValue $false)
$MaxSeqLength = [int](Get-ConfigValue -ConfigObject $Config.train -PropertyName "max_seq_length" -DefaultValue 2048)
$PerDeviceTrainBatchSize = [int](Get-ConfigValue -ConfigObject $Config.train -PropertyName "per_device_train_batch_size" -DefaultValue 1)
$MaxSteps = [int](Get-ConfigValue -ConfigObject $Config.train -PropertyName "max_steps" -DefaultValue 0)
$Optim = [string](Get-ConfigValue -ConfigObject $Config.train -PropertyName "optim" -DefaultValue "adamw_torch")
$OptimArgs = [string](Get-ConfigValue -ConfigObject $Config.train -PropertyName "optim_args" -DefaultValue "")
$OptimTargetModules = [string](Get-ConfigValue -ConfigObject $Config.train -PropertyName "optim_target_modules" -DefaultValue "")
$TorchEmptyCacheSteps = [int](Get-ConfigValue -ConfigObject $Config.train -PropertyName "torch_empty_cache_steps" -DefaultValue 0)
$LoraR = [int](Get-ConfigValue -ConfigObject $Config.train -PropertyName "lora_r" -DefaultValue 16)
$LoraAlpha = [int](Get-ConfigValue -ConfigObject $Config.train -PropertyName "lora_alpha" -DefaultValue 32)
$LoraDropout = [double](Get-ConfigValue -ConfigObject $Config.train -PropertyName "lora_dropout" -DefaultValue 0.05)
$LoraTargetModules = [string](Get-ConfigValue -ConfigObject $Config.train -PropertyName "lora_target_modules" -DefaultValue "q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")

if ($LoadIn4Bit -and -not $UseLora) {
    throw "Invalid config: train.load_in_4bit requires train.use_lora=true."
}
$MemoryEfficientDenseOptimizers = @(
    "galore_adamw",
    "galore_adamw_8bit",
    "galore_adafactor",
    "galore_adamw_layerwise",
    "galore_adamw_8bit_layerwise",
    "galore_adafactor_layerwise",
    "apollo_adamw",
    "apollo_adamw_layerwise"
)
$IsMemoryEfficientDensePath = $MemoryEfficientDenseOptimizers -contains $Optim
$IsConservativeDenseFastpass = (
    (-not $UseLora) -and
    (-not $LoadIn4Bit) -and
    (-not $IsMemoryEfficientDensePath) -and
    ($MaxSeqLength -le 1024) -and
    ($PerDeviceTrainBatchSize -eq 1) -and
    (Get-BoolValue -Value $Config.train.gradient_checkpointing) -and
    ((Get-BoolValue -Value $Config.train.bf16) -or (Get-BoolValue -Value $Config.train.fp16))
)
if ((-not $UseLora) -and (-not $LoadIn4Bit) -and (-not $IsMemoryEfficientDensePath) -and (-not $IsConservativeDenseFastpass) -and [bool]$RuntimeProbe.cuda_available -and ([double]$RuntimeProbe.total_vram_gib -lt 64.0)) {
    throw (
        "Dense full-model finetuning is selected, but the detected GPU only has " +
        [double]$RuntimeProbe.total_vram_gib +
        " GiB VRAM. With the current trainer, Qwen3.5-4B full SFT typically needs well over 60 GiB. " +
        "Use a substantially larger GPU for this profile, switch back to the QLoRA adapter config, or use the conservative fastpass pattern (<=1024 tokens, batch size 1, checkpointing, mixed precision)."
    )
}

$RunMetadata = $null
if ($Config.PSObject.Properties.Name -contains "metadata") {
    $RunMetadata = $Config.metadata
}

$RunName = if ($RunMetadata -and -not [string]::IsNullOrWhiteSpace([string]$RunMetadata.run_name)) {
    [string]$RunMetadata.run_name
} else {
    [System.IO.Path]::GetFileName($ResolvedOutputDir)
}

$SourceSnapshotInputs = [System.Collections.Generic.List[string]]::new()
$SourceSnapshotInputs.Add($ResolvedArgsFile)
$SourceSnapshotInputs.Add($ResolvedTrainFile)
if ($RunMetadata -and $RunMetadata.PSObject.Properties.Name -contains "source_snapshot_files") {
    foreach ($PathValue in $RunMetadata.source_snapshot_files) {
        $ResolvedExtraSource = Resolve-OptionalExistingPath -BaseDir $ProjectRoot -PathValue ([string]$PathValue)
        if ($ResolvedExtraSource) {
            $SourceSnapshotInputs.Add($ResolvedExtraSource)
        }
    }
}

$SourceSnapshotDir = Join-Path $ResolvedOutputDir "_finetune_source"
$FinetuneCardPath = Join-Path $ResolvedOutputDir "FINETUNE_CARD.md"
$RunRoot = Join-Path $ScriptDir ("runs\" + $RunName)
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$TranscriptPath = Join-Path $RunRoot "train_$Stamp.log"
$MetaPath = Join-Path $RunRoot "train_$Stamp.meta.json"

$Summary = [ordered]@{
    args_file = $ResolvedArgsFile
    model = $ResolvedModelPath
    train_file = $ResolvedTrainFile
    output_dir = $ResolvedOutputDir
    run_name = $RunName
    finetune_card = $FinetuneCardPath
    source_snapshot_dir = $SourceSnapshotDir
    transcript = $TranscriptPath
    accelerate = [ordered]@{
        num_processes = $Config.accelerate.num_processes
        num_machines = $Config.accelerate.num_machines
        mixed_precision = $Config.accelerate.mixed_precision
        dynamo_backend = $Config.accelerate.dynamo_backend
    }
    train = [ordered]@{
        max_seq_length = $Config.train.max_seq_length
        expected_samples = $ResolvedExpectedSamples
        strict_no_truncation = $Config.train.strict_no_truncation
        per_device_train_batch_size = $Config.train.per_device_train_batch_size
        gradient_accumulation_steps = $Config.train.gradient_accumulation_steps
        learning_rate = $Config.train.learning_rate
        num_train_epochs = $Config.train.num_train_epochs
        warmup_ratio = $Config.train.warmup_ratio
        lr_scheduler_type = $Config.train.lr_scheduler_type
        weight_decay = $Config.train.weight_decay
        max_grad_norm = $Config.train.max_grad_norm
        logging_steps = $Config.train.logging_steps
        save_steps = $Config.train.save_steps
        save_total_limit = $Config.train.save_total_limit
        save_only_model = $Config.train.save_only_model
        bf16 = $Config.train.bf16
        fp16 = $Config.train.fp16
        gradient_checkpointing = $Config.train.gradient_checkpointing
        seed = $Config.train.seed
        max_steps = $MaxSteps
        optim = $Optim
        optim_args = $OptimArgs
        optim_target_modules = $OptimTargetModules
        torch_empty_cache_steps = $TorchEmptyCacheSteps
        use_lora = $UseLora
        load_in_4bit = $LoadIn4Bit
        lora_r = $LoraR
        lora_alpha = $LoraAlpha
        lora_dropout = $LoraDropout
        lora_target_modules = $LoraTargetModules
    }
    runtime = [ordered]@{
        python = $PythonExe
        python_version = $RuntimeProbe.python_version
        accelerate_version = $RuntimeProbe.accelerate_version
        transformers_version = $RuntimeProbe.transformers_version
        torch_version = $RuntimeProbe.torch_version
        tokenizer_class = $RuntimeProbe.tokenizer_class
        cuda_available = $RuntimeProbe.cuda_available
        cuda_version = $RuntimeProbe.cuda_version
        device_count = $RuntimeProbe.device_count
        total_vram_gib = $RuntimeProbe.total_vram_gib
    }
    dataset = [ordered]@{
        sample_count = $ResolvedExpectedSamples
        min_tokens = $RuntimeProbe.min_tokens
        p95_tokens = $RuntimeProbe.p95_tokens
        max_tokens = $RuntimeProbe.max_tokens
    }
}
if ($ResolvedResumeCheckpoint) {
    $Summary.resume_from_checkpoint = $ResolvedResumeCheckpoint
}
if ($RunMetadata) {
    if ($RunMetadata.PSObject.Properties.Name -contains "training_mode") {
        $Summary.training_mode = [string]$RunMetadata.training_mode
    }
    if ($RunMetadata.PSObject.Properties.Name -contains "intent") {
        $Summary.intent = [string]$RunMetadata.intent
    }
}

Set-Location -Path $ScriptDir
Write-Host "Finetune config:"
Write-Host ($Summary | ConvertTo-Json -Depth 5)
Write-Host ("training_runtime=" + ($RuntimeProbe | ConvertTo-Json -Compress))

$LaunchArgs = [System.Collections.Generic.List[string]]::new()
$LaunchArgs.Add("-m")
$LaunchArgs.Add("accelerate.commands.launch")
$LaunchArgs.Add("--num_processes"); $LaunchArgs.Add([string]$Config.accelerate.num_processes)
$LaunchArgs.Add("--num_machines"); $LaunchArgs.Add([string]$Config.accelerate.num_machines)
$LaunchArgs.Add("--mixed_precision"); $LaunchArgs.Add([string]$Config.accelerate.mixed_precision)
$LaunchArgs.Add("--dynamo_backend"); $LaunchArgs.Add([string]$Config.accelerate.dynamo_backend)
$LaunchArgs.Add((Join-Path $ScriptDir "train.py"))

$LaunchArgs.Add("--model_name_or_path"); $LaunchArgs.Add($ResolvedModelPath)
$LaunchArgs.Add("--train_file"); $LaunchArgs.Add($ResolvedTrainFile)
$LaunchArgs.Add("--output_dir"); $LaunchArgs.Add($ResolvedOutputDir)

$LaunchArgs.Add("--max_seq_length"); $LaunchArgs.Add([string]$Config.train.max_seq_length)
$LaunchArgs.Add("--expected_samples"); $LaunchArgs.Add([string]$ResolvedExpectedSamples)
$LaunchArgs.Add("--per_device_train_batch_size"); $LaunchArgs.Add([string]$Config.train.per_device_train_batch_size)
$LaunchArgs.Add("--gradient_accumulation_steps"); $LaunchArgs.Add([string]$Config.train.gradient_accumulation_steps)
$LaunchArgs.Add("--learning_rate"); $LaunchArgs.Add([string]$Config.train.learning_rate)
$LaunchArgs.Add("--num_train_epochs"); $LaunchArgs.Add([string]$Config.train.num_train_epochs)
$LaunchArgs.Add("--warmup_ratio"); $LaunchArgs.Add([string]$Config.train.warmup_ratio)
$LaunchArgs.Add("--lr_scheduler_type"); $LaunchArgs.Add([string]$Config.train.lr_scheduler_type)
$LaunchArgs.Add("--weight_decay"); $LaunchArgs.Add([string]$Config.train.weight_decay)
$LaunchArgs.Add("--max_grad_norm"); $LaunchArgs.Add([string]$Config.train.max_grad_norm)
$LaunchArgs.Add("--logging_steps"); $LaunchArgs.Add([string]$Config.train.logging_steps)
$LaunchArgs.Add("--save_steps"); $LaunchArgs.Add([string]$Config.train.save_steps)
$LaunchArgs.Add("--save_total_limit"); $LaunchArgs.Add([string]$Config.train.save_total_limit)
$LaunchArgs.Add("--seed"); $LaunchArgs.Add([string]$Config.train.seed)
$LaunchArgs.Add("--max_steps"); $LaunchArgs.Add([string]$MaxSteps)
$LaunchArgs.Add("--optim"); $LaunchArgs.Add($Optim)
if (-not [string]::IsNullOrWhiteSpace($OptimArgs)) {
    $LaunchArgs.Add("--optim_args"); $LaunchArgs.Add($OptimArgs)
}
if (-not [string]::IsNullOrWhiteSpace($OptimTargetModules)) {
    $LaunchArgs.Add("--optim_target_modules"); $LaunchArgs.Add($OptimTargetModules)
}
$LaunchArgs.Add("--torch_empty_cache_steps"); $LaunchArgs.Add([string]$TorchEmptyCacheSteps)
$LaunchArgs.Add("--lora_r"); $LaunchArgs.Add([string]$LoraR)
$LaunchArgs.Add("--lora_alpha"); $LaunchArgs.Add([string]$LoraAlpha)
$LaunchArgs.Add("--lora_dropout"); $LaunchArgs.Add([string]$LoraDropout)
$LaunchArgs.Add("--lora_target_modules"); $LaunchArgs.Add($LoraTargetModules)
if ($ResolvedResumeCheckpoint) {
    $LaunchArgs.Add("--resume_from_checkpoint"); $LaunchArgs.Add($ResolvedResumeCheckpoint)
}

if (Get-BoolValue -Value $Config.train.save_only_model) { $LaunchArgs.Add("--save_only_model") }
if (Get-BoolValue -Value $Config.train.strict_no_truncation) { $LaunchArgs.Add("--strict_no_truncation") }
if (Get-BoolValue -Value $Config.train.bf16) { $LaunchArgs.Add("--bf16") }
if (Get-BoolValue -Value $Config.train.fp16) { $LaunchArgs.Add("--fp16") }
if (Get-BoolValue -Value $Config.train.gradient_checkpointing) { $LaunchArgs.Add("--gradient_checkpointing") }
if ($UseLora) { $LaunchArgs.Add("--use_lora") }
if ($LoadIn4Bit) { $LaunchArgs.Add("--load_in_4bit") }

if ($DryRun) {
    $Quoted = $LaunchArgs | ForEach-Object {
        if ($_ -match "\s") { '"' + $_ + '"' } else { $_ }
    }
    Write-Host "Dry run only. Command:"
    Write-Host ($PythonExe + " " + ($Quoted -join " "))
    return
}
if (-not (Test-Path -LiteralPath $RunRoot)) {
    New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $SourceSnapshotDir)) {
    New-Item -ItemType Directory -Path $SourceSnapshotDir -Force | Out-Null
}

$SnapshotTargets = [System.Collections.Generic.List[string]]::new()
foreach ($SourcePath in $SourceSnapshotInputs) {
    $DestinationPath = Join-Path $SourceSnapshotDir (Split-Path -Leaf $SourcePath)
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
    $SnapshotTargets.Add($DestinationPath)
}

$ExpectedBehaviorLines = @()
if ($RunMetadata -and $RunMetadata.PSObject.Properties.Name -contains "expected_behavior") {
    foreach ($Item in $RunMetadata.expected_behavior) {
        $Value = ([string]$Item).Trim()
        if ($Value) { $ExpectedBehaviorLines += "- $Value" }
    }
}
if (-not $ExpectedBehaviorLines) {
    $ExpectedBehaviorLines = @("- Produce a stronger finetuned checkpoint from the selected supervised dataset.")
}

$NotesLines = @()
if ($RunMetadata -and $RunMetadata.PSObject.Properties.Name -contains "notes") {
    foreach ($Item in $RunMetadata.notes) {
        $Value = ([string]$Item).Trim()
        if ($Value) { $NotesLines += "- $Value" }
    }
}
if (-not $NotesLines) {
    $NotesLines = @("- This run was launched through Finetune/run_training.ps1.")
}

$TrainingMode = if ($RunMetadata -and $RunMetadata.PSObject.Properties.Name -contains "training_mode") {
    [string]$RunMetadata.training_mode
} else {
    "SFT"
}
$Intent = if ($RunMetadata -and $RunMetadata.PSObject.Properties.Name -contains "intent") {
    [string]$RunMetadata.intent
} else {
    "Supervised finetune run launched from the canonical args file."
}
$Reason = if ($RunMetadata -and $RunMetadata.PSObject.Properties.Name -contains "reason_for_finetune") {
    [string]$RunMetadata.reason_for_finetune
} else {
    "Improve the selected base model using the configured supervised dataset."
}

$FinetuneCard = @"
# Finetune Card

## Expected Checkpoint

- Output directory: `$ResolvedOutputDir`
- Base model: `$ResolvedModelPath`
- Training mode: `$TrainingMode`
- Adapter: `$(if ($UseLora) { "Yes (LoRA)" } else { "No" })`

## Data

- Train file: `$ResolvedTrainFile`
- Args file: `$ResolvedArgsFile`
- Source snapshot directory: `$SourceSnapshotDir`

## Intent

$Intent

## Reason For Finetune

$Reason

## Expected Behavior

$(($ExpectedBehaviorLines -join [Environment]::NewLine))

## Notes

$(($NotesLines -join [Environment]::NewLine))
"@
$FinetuneCard | Set-Content -LiteralPath $FinetuneCardPath -Encoding UTF8

$RunMeta = [ordered]@{
    started_at = (Get-Date).ToString("o")
    run_name = $RunName
    args_file = $ResolvedArgsFile
    model = $ResolvedModelPath
    train_file = $ResolvedTrainFile
    output_dir = $ResolvedOutputDir
    transcript = $TranscriptPath
    finetune_card = $FinetuneCardPath
    source_snapshot_dir = $SourceSnapshotDir
    source_snapshots = $SnapshotTargets
    training_mode = $TrainingMode
    allow_cpu = [bool]$AllowCpu
    use_lora = $UseLora
    load_in_4bit = $LoadIn4Bit
    runtime = $RuntimeProbe
    resolved_expected_samples = $ResolvedExpectedSamples
}
$RunMeta | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $MetaPath -Encoding UTF8

Start-Transcript -Path $TranscriptPath -Force | Out-Null
try {
    Write-Host "training_meta=$MetaPath"
    Write-Host "training_log=$TranscriptPath"
    Write-Host "training_card=$FinetuneCardPath"
    if (-not $env:PYTORCH_CUDA_ALLOC_CONF) {
        $env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
    }
    & $PythonExe @LaunchArgs
}
finally {
    Stop-Transcript | Out-Null
}
