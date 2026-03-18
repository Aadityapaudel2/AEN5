# Exclusive Athena vLLM Parity

## Scope

This note records the March 18, 2026 private-runtime hardening pass that moved the exclusive Athena desktop onto the same vLLM-backed serving path as the public portal.

## Final Private Runtime Shape

- Private launch remains `run_ui_private.ps1`.
- `run_ui_private.ps1` now bootstraps or reuses a private vLLM sidecar namespace before the Qt desktop starts.
- The exclusive desktop forces `ATHENA_RUNTIME_BACKEND=vllm_openai`.
- Exclusive prompt, config, logs, and transcript assets remain private under `exclusive/`.
- The private desktop still points tokenizer/config discovery at the exclusive model directory, but text generation now runs through the OpenAI-compatible vLLM server.

## What Changed

### Launcher behavior

`run_ui_private.ps1` no longer waits for a manually prepared vLLM environment file.

It now:

- sets private scope and vLLM runtime env explicitly
- requests the exclusive model directory as the desired served model
- invokes the vLLM bootstrap helper automatically in the `private` runtime namespace
- launches the Qt desktop only after the sidecar contract is established

### Managed model matching

`run_vllm.ps1` now checks whether the currently healthy managed endpoint is actually serving the requested model.

If the managed sidecar is serving another model, Athena restarts it for the requested one instead of silently reusing the wrong runtime.

That matters for the private path because the exclusive launcher may target `exclusive/AthenaV1` while the public path may target `models/Qwen3.5-4B`.

The matching logic now verifies more than the served model name.

For the private runtime, the launcher compares the requested exported model directory against:

- the managed runtime state file when it exists
- the `/v1/models` `root` path reported by vLLM when no state file exists

This closes the failure mode where a stale private sidecar could incorrectly advertise `AthenaV1` while actually serving the public base model.

If a stale unmanaged private sidecar is holding `8002`, the private restart path now evicts the local WSL listener on that private port before retrying. Public `8001` remains untouched.

### Private vLLM export step

The deeper issue turned out not to be only port collision.

`exclusive/AthenaV1` is a tuned text-only overlay checkpoint, not a standalone vLLM-loadable multimodal model directory. The local Transformers runtime handled that by loading the `Qwen3.5-4B` base model and overlaying `exclusive/AthenaV1/model.safetensors` on top of it at runtime.

vLLM could not do that directly from `exclusive/AthenaV1`, because the tuned checkpoint advertises `model_type = qwen3_5_text`, while the installed vLLM/Transformers stack expects the wrapped `qwen3_5` layout used by the base model.

So the private launcher now performs one extra private-only preparation step:

- keep `exclusive/AthenaV1` as the canonical tuned checkpoint
- export a merged vLLM-ready model under `.local/runtime/vllm_private_models/AthenaV1/`
- serve that exported model on the private endpoint

The exporter lives at:

- `exclusive/desktop_engine/export_vllm_ready_model.py`

The launch flow now becomes:

- resolve the canonical private checkpoint in `exclusive/AthenaV1`
- materialize or reuse the merged vLLM-ready export
- start/reuse the private vLLM sidecar on `8002`
- start the Qt desktop against that endpoint

## Operator Contract

- Public canonical command: `run_portal.ps1`
- Private canonical command: `run_ui_private.ps1`
- Manual `run_vllm.ps1` remains a helper/debug surface, not the normal operator flow.

## Important Limitation

The managed Athena vLLM helper now keeps separate public and private sidecar namespaces.

That means:

- one managed port/base URL
- one active served model at a time

If the public and private surfaces need different models simultaneously, the next architecture step is separate vLLM endpoints or separate ports, not a rollback to local Transformers.

## Why This Is Still The Right Direction

- Public and private now share one serving architecture.
- The latency and streaming fixes from the public vLLM pass now apply to the private path too.
- Prompt, identity, and desktop UX can diverge without requiring a second inference stack.

## Verification Target

The private desktop should now show a runtime snapshot with:

- `runtime_backend: vllm_openai`
- `runtime_scope: private`
- a remote base URL for the model endpoint

The launcher output should also log the resolved vLLM base URL and served model before the Qt app starts.

The private export step should create:

- `.local/runtime/vllm_private_models/AthenaV1/`

and that exported directory should contain the merged model weights plus the base multimodal config needed by vLLM.

## Verified Result

The private sidecar was verified end to end on March 18, 2026.

Observed final runtime:

- base URL: `http://127.0.0.1:8002/v1`
- served model: `AthenaV1`
- reported root: `.local/runtime/vllm_private_models/AthenaV1`

The exported private model now boots successfully through vLLM and answers chat requests through the OpenAI-compatible endpoint.

A direct verification request to `/v1/chat/completions` returned:

- `model: AthenaV1`
- `content: AthenaV1 private vLLM is active.`

Cold boot is materially slower than the public text-only portal path. On the verified run, the private multimodal export took roughly 5-7 minutes to become ready under WSL, so the private runtime manager now allows a longer boot wait for the `private` namespace.

## Multimodal Follow-Through

The private vLLM parity pass originally solved only text generation.

The desktop runtime still rejected attachments because the OpenAI-compatible adapter hardcoded:

- `supports_vision = false`
- `image_processor_loaded = false`
- `Image uploads are not configured for the vLLM backend yet.`

That is now aligned with the actual exported model.

The adapter detects vision support from the private exported runtime model under:

- `.local/runtime/vllm_private_models/AthenaV1/`

and it now serializes local desktop image attachments into OpenAI-style multimodal content blocks using:

- `type: image_url`
- `image_url.url: data:image/...;base64,...`

This keeps the private desktop on the same vLLM serving path while restoring multimodal inputs.

