# Athena V5 Finetune

This directory contains the active finetuning utilities for the shared Athena codebase.

## Active files
- `prepare_data.py`: convert turn-level JSONL into chat-format training artifacts
- `train.py`: supervised finetuning entrypoint using `transformers.Trainer`
- `aimo_sft_final.jsonl`: current active SFT dataset

Archived adapter experiments remain under `archive/adapter_experiments/` and are not part of the active runtime path.

## Prepare data
Example:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\Finetune
python prepare_data.py --input trainingdata\bhagavadgita\bhagavaggitatrainingdata.jsonl --output trainingdata\bhagavadgita\bhagavaggitatrainingdata_train.jsonl --assistant_role teacher
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
python train.py --model_name_or_path D:\AthenaPlayground\AthenaV5\models\Qwen3.5-4B --train_file .\aimo_sft_final.jsonl --output_dir .\output\athena_sft --max_seq_length 2048 --per_device_train_batch_size 1 --gradient_accumulation_steps 8 --learning_rate 2e-5 --num_train_epochs 1 --bf16
```

The trainer:
- uses the tokenizer chat template
- labels only assistant spans
- prints token length stats before training
- supports both older `tokenizer=` and newer `processing_class=` trainer signatures

## Scope
- Active: supervised finetune preparation and training
- Shared target: checkpoints consumed by both desktop and browser through `desktop_engine/`
- Archived: LoRA adapter experiments, legacy launchers, and old UI-related files
