# AEN / AthenaV5

This repo is the local runtime, training, evaluation, and research workspace for AthenaV5 inside the broader AEN architecture.

## Canonical Active Surfaces

- `desktop_engine/`
  - source of truth for model loading, prompt assembly, tool execution, event flow, and no-CoT sanitation
- `browser/`
  - thin browser adapter over the shared engine
- `apps/two_model_dialogue_evaluator/`
  - standalone local solver/verifier dialogue app
- `Finetune/`
  - training scripts, active datasets, manifests, and run configs
- `research/`
  - canonical research notes, reports, and source-note map
- `evaluation/`
  - canonical published/evaluation datasets

Historical and non-canonical material lives under `archive/`.

## Active Model State

- Public browser default model:
  - `models/Qwen3.5-4B`
- Private Athena desktop model:
  - `exclusive/AthenaV1` (fallback: `models/tuned/AthenaV1`)
- Base multimodal models kept active:
  - `models/Qwen3.5-2B`
  - `models/Qwen3.5-4B`
  - `models/Qwen3.5-9B`
- Public prompt/runtime defaults:
  - `browser/config/system_prompt.json`
  - `browser/config/gui_config.json`
- Private Athena prompt/runtime defaults:
  - `exclusive/config/system_prompt.json`
  - `exclusive/config/gui_config.json`
- Shared tool behavior primer:
  - `desktop_engine/config/tool_behavior_primer.txt`
- Private Athena local state:
  - `exclusive/logs/desktop/*.ndjson`
  - `exclusive/data/desktop_images/`
  - `exclusive/` is ignored by git

## Launchers

Private Athena desktop:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_ui.ps1
```

Direct private launcher:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_ui_private.ps1
```

Private Athena desktop with tools:

```powershell
.\run_ui.ps1 -Tools
```

Public-facing browser dev:

```powershell
.\run_dev.ps1
```

Browser prod:

```powershell
.\run_portal.ps1
```

Headless math loop:

```powershell
.\run_math_loop.ps1 -Problem "What is 7 + 8?"
```

Math loop evaluation:

```powershell
.\evaluate_math_loop.ps1 -Limit 25
```

Standalone two-model evaluator:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\apps\two_model_dialogue_evaluator
.\run.ps1
```

## Source of Truth

- Paths/defaults: `athena_paths.py`
- Engine runtime: `desktop_engine/runtime.py`
- Engine session/events: `desktop_engine/session.py`, `desktop_engine/events.py`
- Tool execution: `desktop_engine/tools.py`
- Agentic math loop: `desktop_engine/agentic/`
- Browser adapter: `browser/portal_server.py`
- Private desktop seed: `archive/shared_archives/private_desktop_seed_2026-03/`
- Evaluator app: `apps/two_model_dialogue_evaluator/app.py`
- Canonical 4B finetune report:
  - `exclusive/AthenaV1/CANONICAL_RUN_REPORT.md`

## Runtime Rules

- No chain-of-thought is rendered, persisted, or replayed.
- Tool traces stay visible when tools are used.
- Public-facing work happens in the browser adapter.
- Desktop UI is private-only and launches from the local `exclusive/` tree.
- Desktop and browser consume the same engine contract.
- The two-model evaluator stays active as a separate app surface.
- Research/history notes are kept under `research/`, not at the repo root.

## Research and Historical Notes

- Start at:
  - `research/README.md`
- Source-note map:
  - `research/SOURCE_MAP.md`
- Root history notes were moved to:
  - `research/source_notes/`

## Auth and Local Secrets

- Browser auth examples live in:
  - `browser/config/portal_auth.env.example`
- Local-only secrets and private auth materials should stay outside the canonical repo surface.

## Notes

- Canonical browser path prefix is `/AEN5`.
- `/AthenaV5` is retained only as a legacy compatibility label where still supported.
- Live desktop launch still requires `PySide6` and `QtWebEngine` in the selected Python environment.
- Secondary tools removed from the root surface are preserved under `archive/cleanup_2026-03/`.
