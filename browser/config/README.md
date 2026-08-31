# Browser configuration

This folder holds public browser-runtime configuration.

## Files

- `gui_config.json`: public sampling and rendering settings
- `system_prompt.json`: sanitized public assistant behavior
- `context_profiles.json`: native and guarded YaRN context-window profiles
- `portal_auth.env`: ignored local production secrets
- `portal_auth.env.example`: non-secret auth template
- `institutions.json`: dormant or active institution integration definitions

## Public runtime

- `ATHENA_RUNTIME_BACKEND=vllm_openai`
- `ATHENA_PUBLIC_VLLM_ONLY=1`
- `ATHENA_VLLM_BASE_URL=http://127.0.0.1:8001/v1`
- `ATHENA_VLLM_MODEL=<served-model-name>` when model discovery is not desired
- `ATHENA_VLLM_API_KEY=<token>` when the local server requires one
- `ATHENA_VLLM_MODEL_DIR=<local model directory>` to select launcher weights
- `ATHENA_PUBLIC_MODEL_DISPLAY_NAME=Qwen3.5-4B (base)`
- `ATHENA_PUBLIC_MODEL_EXPECTED_ID=Qwen3.5-4B`

The public prompt is a strict, named tutor profile. Production startup fails if required boot, routing, tutoring, educator, memory, mathematics, formatting, or default-mode sections are absent. Public status exposes only the profile name, version, hash, and validation state—not the prompt text or its path.

The default runtime context profile is `native` at 128000 configured tokens. `yarn_1010k` is present for H100-class or equivalent deployments and requires both `-ContextProfile yarn_1010k` and `-AllowExperimentalUltraLongContext`. It is not enabled on the current local public runtime.

Native Windows should use a healthy WSL/Linux vLLM endpoint. See `browser/WSL_VLLM_RUNBOOK.md`.

## Auth truthfulness

The portal advertises a provider only when it is usable:

- Google requires both Google OAuth values.
- GitHub requires both GitHub OAuth values.
- Guest requires `ATHENA_GUEST_LOGIN_ENABLED=1`.
- An institution requires its client ID, client secret, and redirect URI.

Set `ATHENA_DEFAULT_INSTITUTION` only when a configured institution should be preferred. Leave it blank for the general public portal.

`ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH` defaults to `0`. Turning it on is a deliberate deployment decision because it permits verified Google domains to activate preconfigured institution context.

Registry entries and stored course bundles are not public participation claims. Unconfigured entries remain absent from the sign-in page and from the browser-facing config response.
