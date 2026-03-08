# Athena V5 Browser

This folder contains the browser adapter UI. It is intentionally secondary to the native desktop app.

## Current Role
- Browser is a thin FastAPI adapter over `desktop_engine/`
- Browser does not own the runtime anymore
- Desktop and browser share the same engine events and no-CoT guarantees

## Active Files
- `../portal_server.py`: FastAPI server, auth, SSE, logging, and engine bridge
- `../render.py`: transcript markdown/html rendering
- `templates/index.html`
- `templates/login.html`
- `static/portal.js`
- `static/portal.css`

## Launch
From the repo root:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_dev.ps1
```

Open:
- `http://127.0.0.1:8000/AthenaV5`

Enable tools in dev:

```powershell
.\run_dev.ps1 -Tools
```

Prod mode:

```powershell
.\run_portal.ps1
```

## Behavior
- Dev mode: auth off
- Prod mode: auth on
- Tool mode: one switch
- Browser consumes the shared engine event stream:
  - `status`
  - `assistant_delta`
  - `tool_request`
  - `tool_result`
  - `turn_done`
  - `turn_error`
- No CoT is shown in the transcript or stored in history
- Image uploads remain supported for the active multimodal model

## API Surface
- `GET /healthz`
- `GET /AthenaV5`
- `GET /AthenaV5/api/me`
- `GET /AthenaV5/api/config`
- `GET /AthenaV5/api/uploads/{path}`
- `POST /AthenaV5/api/chat/stream`
- `POST /AthenaV5/auth/logout`
- `GET /AthenaV5/auth/login`
- `GET /AthenaV5/auth/callback`
