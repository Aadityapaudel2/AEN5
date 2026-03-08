# Athena V5 Handoff

This is the current-state handoff for the next engineer or next chat window.

It replaces the old portal-first handoff. The repo has been recentered around a native desktop-owned engine with the browser moved into an adapter role.

## 1. Executive Summary

### Current canonical product shape
- Active model: `NeohmIdentityV2_fast` (`Qwen3.5-2B` tuned)
- Active behavior path: `desktop_engine/`
- Active desktop launcher: `run_ui.ps1`
- Active desktop UX: native Qt app with a local `QWebEngineView` transcript
- Active browser launcher: `run_portal.ps1`
- Active browser dev launcher: `run_dev.ps1`
- Active browser role: thin FastAPI adapter over the shared engine
- Active prompt source: `system_prompt.json`
- Active tool behavior primer: `tool_behavior_primer.txt`
- Active runtime parameter file: `gui_config.json`
- Active tool switch: desktop UI toggle or explicit launcher override

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
- one canonical native desktop product
- one optional browser adapter over the same engine

The browser is no longer the runtime center.

## 2. Canonical Active Files

### Configuration and paths
- `athena_paths.py`

Responsibilities:
- canonical model path
- canonical GUI/runtime config path
- canonical prompt path
- canonical tool primer path
- canonical browser path prefix
- canonical browser port
- canonical log root
- auth defaults by mode
- tools default

Key defaults:
- `CHAT_MODEL_DIR = D:\AthenaPlayground\AthenaV5\models\tuned\NeohmIdentityV2_fast`
- `GUI_CONFIG_PATH = gui_config.json`
- `SYSTEM_PROMPT_FILE = system_prompt.json`
- `TOOL_BEHAVIOR_PRIMER_FILE = tool_behavior_primer.txt`
- `PORTAL_PATH_PREFIX = /AthenaV5`
- `PORTAL_PORT = 8000`
- `PORTAL_HOSTS = {"dev": "127.0.0.1", "prod": "0.0.0.0"}`
- `AUTH_REQUIRED = {"dev": False, "prod": True}`
- `TOOLS_ENABLED_DEFAULT = False`

### Shared engine
- `desktop_engine/events.py`
- `desktop_engine/tools.py`
- `desktop_engine/runtime.py`
- `desktop_engine/session.py`

Responsibilities:
- model bootstrap and warm start
- tokenizer/model setup
- prompt assembly
- multimodal message normalization
- no-CoT sanitation for stream, final answer, and replay
- tool execution and formatting
- turn lifecycle
- stable event contract for desktop and browser

### Desktop app
- `desktop_app/main.py`
- `desktop_app/assets/transcript.html`
- `desktop_app/assets/transcript.css`
- `desktop_app/assets/transcript.js`

Responsibilities:
- native window shell
- composer, attachments, transcript, runtime panel
- direct in-process engine session usage
- local transcript rendering with no localhost dependency

### Browser adapter
- `browser/portal_server.py`
- `browser/render.py`
- `browser/portal/templates/index.html`
- `browser/portal/templates/login.html`
- `browser/portal/static/portal.css`
- `browser/portal/static/portal.js`
- `browser/cloudflared_athenav5.ps1`

Responsibilities:
- FastAPI app lifecycle
- browser auth/session behavior
- SSE translation of engine events
- transcript rendering
- per-user logging and uploads

### Root compatibility shims
- `athena_runtime.py`
- `athena_tools.py`
- `portal_server.py`
- `portal_render.py`
- `qt_ui.py`
- `cloudflared_athenav5.ps1`

These exist for continuity and import stability. They are not the main implementation anymore.

## 3. Engine Contract

### Session interface
`desktop_engine.session.EngineSession` exposes:
- `submit_turn`
- `cancel_turn`
- `reset_conversation`
- `restore_history`
- `history_snapshot`
- `runtime_snapshot`

### Event stream
`desktop_engine.events.EngineEvent` currently supports:
- `status`
- `assistant_delta`
- `tool_request`
- `tool_result`
- `turn_done`
- `turn_error`

Current payload rules:
- `tool_request` carries exact code, language, and provenance
- `tool_result` carries `ok`, `result_text`, `stdout`, `stderr`, and `duration_ms`
- `turn_done` carries final visible assistant text, visible transcript messages, metrics, and model-loaded state
- hidden reasoning is not part of the contract

## 4. Launch Matrix

### Canonical desktop launch

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_ui.ps1
```

Desktop with tools:

```powershell
.\run_ui.ps1 -Tools
```

### Browser adapter launch
Dev, no auth:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_dev.ps1
```

Dev with tools:

```powershell
.\run_dev.ps1 -Tools
```

Prod/auth path:

```powershell
.\run_portal.ps1
```

Browser launchers:
- `run_dev.ps1`
- `run_portal.ps1`

## 5. Current UX and Product Intent

- Desktop should feel like the primary Athena product, not a wrapped website.
- Browser should remain supported, but minimal and secondary.
- Tool calling must remain transparent and exact.
- The model must not visibly emit CoT scaffolding such as `Thinking Process`, `Analyze the Request`, `Draft`, or `Refine`.
- The runtime panel is secondary; the main interaction is the chat surface.
- The current engine is single-worker chat-first, but the architecture is intentionally ready for later router/scout/verifier/judge expansion.

## 6. Validation Status

Verified after the desktop-first rebuild:
- `python -m py_compile` passed for new engine modules, desktop app, browser adapter, and root shims
- `node --check browser\portal\static\portal.js` passed
- PowerShell parse passed for `run_ui.ps1`, `run_portal.ps1`, and `cloudflared_athenav5.ps1`
- import smoke passed for `browser.portal_server`
- engine snapshot smoke passed for `DesktopEngine`

Current limitation:
- live desktop launch was not fully runtime-verified in this environment because the active Python interpreter does not have `PySide6` plus `QtWebEngine` installed
- static validation passed, but no actual Qt window was launched in this pass

## 7. Non-Canonical / Historical Areas

These are not the active runtime path:
- `archive/legacy_desktop/`
- `archive/adapter_experiments/`
- old portal-first docs and notes
- older files named in historical research such as `tk_chat.py`, `wrap.py`, `ui.py`, and `system_prompt.json`

`report.md` should now be treated as a historical snapshot unless it is rewritten.

## 8. Immediate Next-Step Bias

If the next task is about architecture or product work:
- build on `desktop_engine/` first
- keep desktop native and direct
- add agentic orchestration inside the engine, not inside browser code
- keep browser changes adapter-thin unless the task is explicitly browser-facing
