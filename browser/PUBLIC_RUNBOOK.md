# Public Athena V5 Runbook

This is the operator runbook for the public browser portal.

## Runtime contract

- Public Athena V5 is **vLLM-only**
- The browser portal should be launched through:
  - `run_portal.ps1`
  - which delegates to `browser/run_browser.ps1`
- `browser/run_browser.ps1` starts or reuses a local OpenAI-compatible vLLM server, waits for `/v1/models`, and then starts the FastAPI portal
- On native Windows, do **not** expect the launcher to boot vLLM directly. Use a healthy WSL/Linux vLLM server and point `ATHENA_VLLM_BASE_URL` to it.
- See [WSL_VLLM_RUNBOOK.md](/d:/AthenaPlayground/AthenaV5/browser/WSL_VLLM_RUNBOOK.md) for the Windows-hosted public setup.

## Required runtime pieces

- a Python environment with:
  - `authlib`
  - the portal/runtime dependencies
- local model weights
- Google OAuth secrets for the public MiamiOH pilot
- a reachable vLLM endpoint

If you are running the portal from native Windows, the vLLM endpoint should come from WSL or another Linux host.

## Important env/runtime values

- `ATHENA_RUNTIME_BACKEND=vllm_openai`
- `ATHENA_PUBLIC_VLLM_ONLY=1`
- `ATHENA_VLLM_BASE_URL`
- optional `ATHENA_VLLM_MODEL`
- optional `ATHENA_VLLM_MODEL_DIR`
- `ATHENA_GOOGLE_CLIENT_ID`
- `ATHENA_GOOGLE_CLIENT_SECRET`
- `ATHENA_PORTAL_SESSION_SECRET`
- `ATHENA_DEFAULT_INSTITUTION=miamioh`

## Start

Launch the public portal:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_portal.ps1
```

`run_portal.ps1` is the canonical public command. It will bootstrap or reuse the shared vLLM runtime as needed.

Optional preflight before launch:

```powershell
.\run_portal.ps1 -PreflightOnly
```

Optional vLLM operator/debug command:

```powershell
.\run_vllm.ps1 -Status
```

If preflight fails on imports, fix the portal venv first. For the public runtime, missing `vllm` or `authlib` is a real blocker, not a warning.

## Readiness

Check:

- `GET /healthz`
- `GET /AEN5/api/config`

Expected:

- `ok: true`
- `ready: true`
- `runtime_backend: vllm_openai`
- a non-empty active/configured model label

## Live smoke before announcement

1. Sign in with a real `@miamioh.edu` Google account.
2. Verify:
   - `What is this course about?`
   - `When is Exam 2?`
   - `When is the final?`
   - `What should I know about discussions?`
   - `Help me study for Quiz 6`
   - `What is my name and what is my position?`
3. Verify controls:
   - `Stop`
   - `New Thread`
4. Verify formatting:
   - bold
   - bullets
   - inline math

## Cleanup

To remove low-value generated runtime artifacts such as `__pycache__` folders and leftover temp files:

```powershell
.\browser\cleanup_runtime_artifacts.ps1
```

## Data layout

- institution/course data lives under `institutions/`
- MiamiOH pilot data is here:
  - `institutions/miamioh/courses/250433/derived/`
  - `institutions/miamioh/courses/250433/pilot/`

Do not use `miamioh/courses/250433/` as a live data path anymore.
