# Browser Config

This folder holds the public-facing browser runtime configuration.

Files:
- `gui_config.json`: public browser/default sampling settings.
- `system_prompt.json`: public browser/default system prompt.
- `portal_auth.env`: local production auth secrets for the browser adapter.
- `portal_auth.env.example`: non-secret template for the auth env file.
- `institutions.json`: institution registry for Canvas-backed school integrations.

Runtime backend env vars:
- Public browser runtime is `ATHENA_RUNTIME_BACKEND=vllm_openai`
- `ATHENA_PUBLIC_VLLM_ONLY=1`
- `ATHENA_VLLM_BASE_URL=http://127.0.0.1:8001/v1`
- `ATHENA_VLLM_MODEL=<served-model-name>` if you do not want auto-discovery from `/models`
- `ATHENA_VLLM_API_KEY=<token>` if your local vLLM server expects a bearer token
- `ATHENA_VLLM_MODEL_DIR=<local model directory>` to force the sidecar launcher model path
- `ATHENA_VLLM_TIMEOUT_SECONDS=300`
- `ATHENA_VLLM_MAX_CONTEXT_TOKENS=<hint>` for approximate token-budget reporting in the browser UI

Windows note:
- native Windows should treat `ATHENA_VLLM_BASE_URL` as an external or WSL/Linux vLLM endpoint
- the public launcher will not try to bootstrap a native Windows vLLM sidecar when no endpoint is reachable
- see `browser/WSL_VLLM_RUNBOOK.md` for the expected operator flow

MiamiOH pilot note:
- the current student pilot uses **Google identity**, not Canvas OAuth
- `institutions.json` still seeds MiamiOH for future Canvas integration
- the live course context for the pilot is generated under `institutions/miamioh/courses/250433/`
- `derived/` contains normalized bundle files from the Canvas export
- `pilot/` contains pilot-only overlays such as dates and role resolution
- `pilot_overrides.json` is the authoritative source for dates and key schedule facts
- `pilot_people.json` is the pilot role-resolution file for instructor identity and future roster-aware student records
- MiamiOH is detected automatically after Google sign-in; there is no separate MiamiOH-specific Google OAuth provider
