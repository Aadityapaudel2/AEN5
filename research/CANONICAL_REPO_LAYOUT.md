# Canonical Repo Layout

This is the retained active layout after the cleanup pass.

## Active Runtime

- `desktop_engine/`
- `desktop_engine/config/`
- `browser/`
- `browser/config/`
- `exclusive/`
- `apps/two_model_dialogue_evaluator/`

## Active Launchers

- `run_ui.ps1`
- `run_ui_private.ps1`
- `run_dev.ps1`
- `run_portal.ps1`
- `evaluation/scripts/run_math_loop.ps1`
- `evaluation/scripts/evaluate_math_loop.ps1`
- `evaluation/scripts/run_math_loop_observer.ps1`
- `apps/two_model_dialogue_evaluator/run.ps1`

## Active Models

- `models/Qwen3.5-2B`
- `models/Qwen3.5-4B`
- `models/Qwen3.5-9B`
- `exclusive/AthenaV1` (fallback `models/tuned/AthenaV1`)

## Active Training Surface

- `Finetune/train.py`
- `Finetune/run_training.ps1`
- `Finetune/tooling/prepare/prepare_data.py`
- active builder scripts
- current training corpora under `Finetune/trainingdata/`

## Active Data and Research

- `evaluation/`
- `research/`

## Historical / Secondary Location

- `archive/`

Anything that is no longer part of the active runtime, data, or training surface should be moved there instead of being left ambiguous at the repo root.
