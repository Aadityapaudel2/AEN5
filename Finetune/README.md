# Athena V5 Finetune

This directory contains the active finetuning utilities for the shared Athena codebase.

## Active files
- `train.py`: canonical supervised finetuning entrypoint using `transformers.Trainer`
- `run_training.ps1`: canonical PowerShell launcher for active finetune args
- `tooling/prepare/prepare_data.py`: raw-dialogue conversion utility
- `tooling/builders/`: dataset-construction scripts
- `recipes/`: non-canonical fast-pass wrappers and recipe args
- `trainingdata/`: active datasets, manifests, and retained source snapshots

Archived adapter experiments remain under `archive/adapter_experiments/` and are not part of the active runtime path.

## Prepare data
Example:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\Finetune
python tooling/prepare/prepare_data.py --input trainingdata\bhagavadgita\bhagavaggitatrainingdata.jsonl --output trainingdata\bhagavadgita\bhagavaggitatrainingdata_train.jsonl --assistant_role teacher
```

Useful switches:
- `--artifact_style dialogue|assistant_turn`
- `--max_context_messages N`
- `--merge_consecutive_same_role`
- `--strip_role_prefixes`

## Train
Example:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\Finetune
python train.py --model_name_or_path D:\AthenaPlayground\AthenaV5\models\Qwen3.5-4B --train_file .\trainingdata\source_snapshots\aimo_sft_final.jsonl --output_dir .\output\athena_sft --max_seq_length 2048 --per_device_train_batch_size 1 --gradient_accumulation_steps 8 --learning_rate 2e-5 --num_train_epochs 1 --bf16
```

The trainer:
- uses the tokenizer chat template
- labels only assistant spans
- prints token length stats before training
- supports both older `tokenizer=` and newer `processing_class=` trainer signatures

## Scope
- Canonical runtime: `train.py`, `run_training.ps1`, `finetune_args.json`, active datasets in `trainingdata/`
- Tooling: dataset preparation and builder scripts under `tooling/`
- Recipes: optional fast-pass wrappers and non-canonical arg presets under `recipes/`
- Shared target: checkpoints consumed by browser, evaluation, and private desktop through the shared engine
- Archived: LoRA adapter experiments, legacy launchers, and retired desktop/public shims

## Orchestrator Dataset V1

The repo now includes a role-pure orchestration seed pipeline under `trainingdata/orchestrator_v1/`.

- Canonical source: `trainingdata/orchestrator_v1/scenario_cards.yaml`
- Compiled outputs:
  - `trainingdata/orchestrator_v1/orchestrator_seed.jsonl`
  - `trainingdata/orchestrator_v1/solver_a_seed.jsonl`
  - `trainingdata/orchestrator_v1/solver_b_seed.jsonl`
- Curator prompt: `prompts/orchestrator_v1_curator_prompt.md`
- Builder: `tooling/builders/build_orchestrator_dataset.py`

Example rebuild:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
python .\Finetune\tooling\builders\build_orchestrator_dataset.py --bootstrap --write --validate --token-stats
```

## Fast Pass Training

For a first fast-pass orchestrator run on `Qwen3.5-4B`, use:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\Finetune\recipes\train_orchestrator_fast.ps1
```

That wrapper:
- uses `recipes/orchestrator_v1_fast.json`
- trains on `trainingdata/orchestrator_v1/orchestrator_seed.jsonl`
- writes the checkpoint to the tuned-models root
- writes `FINETUNE_CARD.md` plus a `_finetune_source/` snapshot into the expected output model directory
- saves a transcript and metadata JSON under `Finetune/runs/orchestrator_v1_fast/`
