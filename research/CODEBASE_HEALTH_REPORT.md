# Codebase Health Report

## Goal

This report records the retained code surfaces after the archive-first hygiene pass. The rule for the active repo is simple: keep only code that has a direct runtime, training, evaluation, or research purpose. Everything else should move to `archive/`, not remain ambiguous in the active tree.

## Retained Active Surfaces

### Shared engine
- `desktop_engine/runtime.py`
- `desktop_engine/session.py`
- `desktop_engine/tools.py`
- `desktop_engine/events.py`
- `desktop_engine/agentic/`

Why it stays:
- This is the single inference/runtime contract shared by the private desktop, browser adapter, and evaluation loop. Replacing it would fragment the repo. Amend it; do not fork it.

### Public browser surface
- `browser/portal_server.py`
- `browser/run_browser.ps1`
- `browser/portal/`
- `browser/config/`

Why it stays:
- This is the public-facing product path. It owns public prompt/config and browser auth routing without mixing with private Athena state.

### Private Athena surface
- `run_ui.ps1`
- `run_ui_private.ps1`
- `exclusive/AthenaV1/`
- `exclusive/config/`
- `exclusive/desktop/`
- `exclusive/desktop_app/`
- `exclusive/logs/desktop/*.ndjson`

Why it stays:
- This is the private-only desktop path. It owns local prompt/config, local NDJSON logs, and local image state. It should remain isolated from public browser work.

### Evaluation surface
- `evaluation/scripts/`
- `evaluation/testdata/`
- `evaluation/tests/`
- root wrappers `run_math_loop.ps1`, `evaluate_math_loop.ps1`, `run_math_loop_observer.ps1`

Why it stays:
- Evaluation must remain reproducible and separate from both public browser UX and private desktop UX.

### Finetune surface
- `Finetune/train.py`
- `Finetune/run_training.ps1`
- `Finetune/tooling/prepare/`
- `Finetune/tooling/builders/`
- `Finetune/recipes/`
- `Finetune/trainingdata/`

Why it stays:
- This is the active training pipeline. Dataset preparation, dataset builders, canonical datasets, and training configs are co-located and no longer scattered across the repo root.

### Standalone evaluator app
- `apps/two_model_dialogue_evaluator/`

Why it stays:
- It is an active separate experiment surface, not an archive. It remains first-class and independent from the browser adapter.

### Research surface
- `research/`
- `research/source_notes/`

Why it stays:
- Strategy, experiments, and source-note lineage now live outside the product root. This prevents architecture notes from competing with runtime code.

## Archive Principle

If a file does not directly support one of the retained surfaces above, it should be moved to `archive/`. The active tree should not carry dead wrappers, duplicate desktop implementations, retired prompts, or root-level historical notes.

## Current Hygiene Outcome

- Public config is no longer mixed into the root surface.
- Private config and logs are isolated under `exclusive/`.
- Evaluation has a dedicated top-level home.
- Finetune preparation/build scripts have dedicated subfolders.
- Historical notes and retired code are discoverable through `archive/` and `research/source_notes/`.

## Maintenance Rule

When adding new code, place it in exactly one active surface. If it is experimental and does not graduate, move it to `archive/`. If it becomes shared infrastructure, place it under the shared engine or the relevant dedicated surface instead of creating another root-level singleton.
