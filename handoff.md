# Athena V5 Handoff

This is the current-state handoff for the next engineer or next chat window.

## 1. Executive Summary

### Current canonical product shape
- Active public default model: `Qwen3.5-4B`
- Active private Athena model: `exclusive/AthenaV1` (fallback `models/tuned/AthenaV1`)
- Active behavior path: `desktop_engine/`
- Active desktop wrapper launcher: `run_ui.ps1`
- Active private desktop launcher: `run_ui_private.ps1`
- Active desktop UX: private Qt app bootstrapped from `exclusive/` with tracked seed fallback
- Active browser launcher: `run_portal.ps1`
- Active browser dev launcher: `run_dev.ps1`
- Active browser role: thin FastAPI adapter over the shared engine
- Active standalone evaluator: `apps/two_model_dialogue_evaluator/`
- Active public-facing UI surface: browser only
- Active public prompt source: `browser/config/system_prompt.json`
- Active private prompt source: `exclusive/config/system_prompt.json`
- Active tool behavior primer: `desktop_engine/config/tool_behavior_primer.txt`
- Active public runtime parameter file: `browser/config/gui_config.json`
- Active private runtime parameter file: `exclusive/config/gui_config.json`
- Active private desktop log root: `exclusive/logs/desktop/*.ndjson`

### Hard behavioral rules
- No chain-of-thought or meta-reasoning should be rendered to the user.
- No chain-of-thought or meta-reasoning should be persisted to session history.
- No polluted assistant history should be replayed back into the model.
- Tool use should stay visible and transparent when it happens.
- Exact calculator requests sent to the tool environment should remain visible to the user.
- Desktop and browser must stay on the same engine contract.

### Current architecture decision
Do not restore a second independent inference runtime.

The intended architecture is:
- one canonical engine package
- one canonical private desktop product
- one optional browser adapter over the same engine
- one separate standalone evaluator app for solver/verifier dialogue experiments

## 2. Canonical Active Files

### Configuration and paths
- `athena_paths.py`

Key defaults:
- `CHAT_MODEL_DIR = D:\AthenaPlayground\AthenaV5\models\Qwen3.5-4B`
- `ATHENA_CHAT_MODEL_DIR` can override the public default and is used by `run_ui_private.ps1` to route the private Athena instance to `exclusive\AthenaV1` (fallback `models\tuned\AthenaV1`)
- `GUI_CONFIG_PATH = browser/config/gui_config.json`
- `SYSTEM_PROMPT_FILE = browser/config/system_prompt.json`
- `TOOL_BEHAVIOR_PRIMER_FILE = desktop_engine/config/tool_behavior_primer.txt`
- `PORTAL_PATH_PREFIX = /AEN5`
- `PORTAL_PORT = 8000`
- `PORTAL_HOSTS = {"dev": "127.0.0.1", "prod": "0.0.0.0"}`
- `AUTH_REQUIRED = {"dev": False, "prod": True}`

### Shared engine
- `desktop_engine/events.py`
- `desktop_engine/tools.py`
- `desktop_engine/runtime.py`
- `desktop_engine/session.py`
- `desktop_engine/agentic/`

### Private desktop seed and local tree
- `archive/shared_archives/private_desktop_seed_2026-03/desktop/qt_ui.py`
- `archive/shared_archives/private_desktop_seed_2026-03/desktop_app/`
- local-only runtime copies under `exclusive/desktop/` and `exclusive/desktop_app/`
- private logs under `exclusive/logs/desktop/*.ndjson`

### Browser adapter
- `browser/portal_server.py`
- `browser/render.py`
- `browser/portal/templates/index.html`
- `browser/portal/templates/login.html`
- `browser/portal/static/portal.css`
- `browser/portal/static/portal.js`
- `browser/cloudflared_athenav5.ps1`

### Standalone evaluator
- `apps/two_model_dialogue_evaluator/app.py`
- `apps/two_model_dialogue_evaluator/runtime/`
- `apps/two_model_dialogue_evaluator/config/`
- `apps/two_model_dialogue_evaluator/run.ps1`

## 3. Launch Matrix

### Private Athena desktop launch

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_ui.ps1
```

### Direct private Athena launcher

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_ui_private.ps1
```

### Headless agentic math loop

```powershell
.\run_math_loop.ps1 -Problem "What is 7 + 8?"
.\evaluate_math_loop.ps1 -Limit 25
```

### Browser adapter

```powershell
.\run_dev.ps1
.\run_portal.ps1
```

### Standalone two-model evaluator

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\apps\two_model_dialogue_evaluator
.\run.ps1
```

## 4. Validation Status

Cleanup-preserved active surfaces:
- private desktop runtime
- browser adapter
- standalone evaluator
- headless math loop
- canonical 4B sprint model path
- training surface and active datasets

Current caution:
- private desktop launch still depends on the selected Python environment having `PySide6` and `QtWebEngine`

## 5. Non-Canonical / Historical Areas

Historical and secondary material now lives under:
- `archive/`
- `research/source_notes/`

Examples:
- `archive/legacy_desktop/`
- `archive/adapter_experiments/`
- `archive/cleanup_2026-03/`

The standalone evaluator is active. It is not archive-only.

## 6. Immediate Next-Step Bias

If the next task is about architecture or product work:
- build on `desktop_engine/` first
- keep desktop private and direct
- add orchestration inside the shared engine, not in browser-only code
- keep the standalone evaluator usable as an experiment surface
- treat `research/` as the canonical place for strategic notes and cleanup/history reports
