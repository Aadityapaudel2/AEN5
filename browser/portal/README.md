# AEN Browser Portal

This folder contains the browser adapter UI for AEN (Artificial Evaluation Network). It is the public-facing product surface over the shared engine.

AthenaV5 remains an internal legacy/runtime label in compatibility paths and model identifiers. AEN is the public-facing platform name.

## Current Role
- Browser is a thin FastAPI adapter over `desktop_engine/`
- Browser does not own the model implementation anymore
- Desktop and browser share the same engine events and no-CoT guarantees
- Public Athena V5 is now **vLLM-only**
- `browser/run_browser.ps1` is the canonical sidecar launcher: it starts or reuses a local OpenAI-compatible vLLM server, waits for `/v1/models`, then starts the portal
- The public portal should fail fast if the vLLM server is unavailable or no served model is reported

## MiamiOH Pilot
- Today's live pilot path is **Google-only** for MiamiOH users.
- Students should sign in with their `@miamioh.edu` Google account.
- MiamiOH Google users are automatically attached to the MTH025C pilot course bundle (`250433`).
- `institutions/miamioh/courses/250433/pilot/pilot_overrides.json` is the authoritative source for quizzes, exams, final-week timing, and key semester dates.
- `institutions/miamioh/courses/250433/pilot/pilot_people.json` is the pilot identity layer for instructor and future roster-aware role resolution.
- The Canvas export bundle remains the broader source for course structure, modules, policies, and assignment context.
- The pilot does **not** claim live Canvas sync or personal gradebook awareness.
- Schedule answers should copy dates exactly as written in the course guide.

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
- `http://127.0.0.1:8000/AEN5`

Enable tools in dev:

```powershell
.\run_dev.ps1 -Tools
```

Prod mode:

```powershell
.\run_portal.ps1
```

This now boots the public vLLM sidecar path through `browser/run_browser.ps1`.

## Curriculum Memory
- Public portal memory is now layered: recent turns + learner profile summary + session focus + relevant recall
- Optional per-user curriculum hook: `data/users/<user>/memory/curriculum_context.json`
- Example schema: `browser/config/curriculum_context.template.json`
- `data/users/<user>/memory/canvas_state.json` now holds normalized live Canvas course state when institution auth is enabled
- `browser/config/institutions.json` defines institution registry entries such as MiamiOH Canvas
- This allows LMS-backed context without changing the tutoring runtime

## Behavior
- Dev mode: auth off
- Prod mode: auth on
- Auth provider is selected with `ATHENA_AUTH_PROVIDER=google|github`
- Guest sign-in can stay enabled with `ATHENA_GUEST_LOGIN_ENABLED=1`
- Optional guest prompt caps use `ATHENA_GUEST_PROMPT_LIMIT`
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
- `GET /AEN5`
- `GET /AEN5/api/me`
- `GET /AEN5/api/config`
- `GET /AEN5/api/uploads/{path}`
- `POST /AEN5/api/chat/stream`
- `POST /AEN5/api/chat/stop`
- `POST /AEN5/api/chat/reset`
- `POST /AEN5/auth/logout`
- `GET /AEN5/auth/login`
- `GET /AEN5/auth/callback`

## Runtime Notes
- `Stop` in the browser now sends a real backend cancel request for the active turn.
- `New Thread` now clears recent transcript continuity and short-lived summary/session memory on the server.
- Profile, curriculum context, and MiamiOH course context remain available after `New Thread`.
- Public runtime env:
  - `ATHENA_RUNTIME_BACKEND=vllm_openai`
  - `ATHENA_PUBLIC_VLLM_ONLY=1`
  - `ATHENA_VLLM_BASE_URL`
  - optionally `ATHENA_VLLM_MODEL`
  - optionally `ATHENA_VLLM_API_KEY`
  - optionally `ATHENA_VLLM_MODEL_DIR` or `ATHENA_CHAT_MODEL_DIR`

## Auth Setup
- For today's MiamiOH pilot:
  - configure `ATHENA_GOOGLE_CLIENT_ID`
  - configure `ATHENA_GOOGLE_CLIENT_SECRET`
  - set `ATHENA_DEFAULT_INSTITUTION=miamioh`
  - restart the portal
  - users should use the `Continue with Google` button
  - MiamiOH is detected automatically after Google sign-in
  - the first live smoke should be a full sign-out/sign-in so the latest pilot role context is bootstrapped
- For institution Canvas OAuth:
  - configure `browser/config/institutions.json`
  - set `ATHENA_DEFAULT_INSTITUTION`
  - set the institution-specific env vars referenced by `oauth_client_id_env`, `oauth_client_secret_env`, and `redirect_uri_env`
  - for MiamiOH, the seeded env vars are:
    - `ATHENA_CANVAS_MIAMIOH_CLIENT_ID`
    - `ATHENA_CANVAS_MIAMIOH_CLIENT_SECRET`
    - `ATHENA_CANVAS_MIAMIOH_REDIRECT_URI`
- Legacy GitHub and Google OAuth can still be configured if needed:
  - set `ATHENA_AUTH_PROVIDER=github|google`
  - set `ATHENA_GITHUB_CLIENT_ID` / `ATHENA_GITHUB_CLIENT_SECRET`
  - set `ATHENA_GOOGLE_CLIENT_ID` / `ATHENA_GOOGLE_CLIENT_SECRET`
- For guest sign-in:
  - set `ATHENA_GUEST_LOGIN_ENABLED=1`
  - optionally set `ATHENA_GUEST_PROMPT_LIMIT` to cap guest prompts per browser session
