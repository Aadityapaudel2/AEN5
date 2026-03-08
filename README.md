# Athena V5

Athena V5 is now desktop-first.

## Canonical Runtime
- Canonical product surface: native desktop app
- Shared engine: `desktop_engine/`
- Browser surface: thin adapter in `browser/`
- Active model: `NeohmIdentityV2_fast` (`Qwen3.5-2B` tuned)
- Prompt source: `system_prompt.json`
- Tool behavior primer: `tool_behavior_primer.txt`
- Canonical runtime parameters: `gui_config.json`

## Repository Shape
- `desktop_engine/`: source of truth for model loading, prompt/history assembly, no-CoT sanitation, tool execution, turn lifecycle, and engine events
- `desktop_app/`: native Qt app with a local `QWebEngineView` transcript renderer
- `browser/`: FastAPI browser adapter, static assets, templates, auth, and cloudflared helpers
- `archive/`: legacy desktop runtime, adapter experiments, and old assets kept for reference only

Root shims still exist for continuity:
- `athena_runtime.py`
- `athena_tools.py`
- `portal_server.py`
- `portal_render.py`
- `qt_ui.py`
- `cloudflared_athenav5.ps1`

## Canonical Entrypoints
Desktop:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_ui.ps1
```

Desktop with tools:

```powershell
.\run_ui.ps1 -Tools
```

Side-by-side model compare:

```powershell
.\run_compare.ps1
```

Compare prompt sets:
- Load a YAML prompt set in the compare UI
- Step prompts one at a time with `Prev` / `Next`
- Each compared prompt appends a row to `data/compare_runs/*.csv`

Browser adapter, dev mode:

```powershell
.\run_dev.ps1
```

Browser adapter, dev mode with tools:

```powershell
.\run_dev.ps1 -Tools
```

Browser adapter, prod mode:

```powershell
.\run_portal.ps1
```

Browser launchers:
- `run_dev.ps1`
- `run_portal.ps1`
- `run_compare.ps1`

## Source of Truth
- Paths and defaults: `athena_paths.py`
- Canonical runtime config: `gui_config.json`
- Engine session/events: `desktop_engine/session.py`, `desktop_engine/events.py`
- Engine runtime: `desktop_engine/runtime.py`
- Tool execution: `desktop_engine/tools.py`
- Desktop app: `desktop_app/main.py`
- Browser adapter: `browser/portal_server.py`
- Transcript rendering: `browser/render.py`

## Tuning Storage
- Existing tuned checkpoints stay where they are.
- Future finetune outputs that target `models/tuned/...` are redirected by `Finetune/run_training.ps1` to the canonical tuned-model root:
  - `N:\AthenaModels\tuned`
- Override that root if needed with `ATHENA_TUNED_MODELS_ROOT`.

## Runtime Rules
- No chain-of-thought is rendered, persisted, or replayed. This is enforced in the engine.
- Tool traces stay visible. Tool request cards show the exact calculator request and provenance.
- Desktop and browser use the same engine contract.
- Browser is optional and secondary. It is not the runtime center anymore.

## Auth
Browser prod mode expects:
- `ATHENA_GOOGLE_CLIENT_ID`
- `ATHENA_GOOGLE_CLIENT_SECRET`
- `ATHENA_AUTH_REDIRECT_URI`
- `ATHENA_PORTAL_SESSION_SECRET`

The browser auth example lives at `browser/portal_auth.env.example`. A root compatibility copy is also present.

## Logging
Per-user browser data lives under:
- `data/users/<user_key>/profile.json`
- `data/users/<user_key>/sessions/YYYY-MM-DD.ndjson`
- `data/users/<user_key>/errors/YYYY-MM-DD.ndjson`
- `data/users/<user_key>/uploads/YYYY-MM-DD/*`

Desktop image staging lives under:
- `data/desktop_images/`

## Notes
- `report.md` is a historical snapshot from before the desktop-first rebuild. Read `handoff.md` for the current architecture summary.
- Live desktop launch still requires `PySide6` plus `QtWebEngine` in the selected Python environment.
