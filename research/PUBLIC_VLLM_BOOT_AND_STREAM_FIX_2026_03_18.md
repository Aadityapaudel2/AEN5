# Public vLLM Boot And Stream Fix

## Scope

This note records the March 18, 2026 hardening pass that made the public Athena V5 portal reliably generate through the WSL-backed vLLM path.

## Final Runtime Shape

- Public launch remains `run_portal.ps1`.
- `run_portal.ps1` bootstraps or reuses the shared vLLM sidecar.
- Windows hosts use WSL Ubuntu for the vLLM server.
- The stable Python environment for vLLM lives in the Linux home directory, not under `/mnt/d/...`.
- The public browser surface talks to vLLM through the OpenAI-compatible API.

## Root Cause Of The "Preparing The First Token" Stall

The model was loading successfully. The visible stall came from two separate issues:

1. Qwen chat-template reasoning leakage
- Raw vLLM output could enter a `Thinking` style mode.
- The runtime now sends `chat_template_kwargs = { enable_thinking: false }`.

2. Prompt budgeting failure
- The public browser route combined system prompt, curriculum retrieval, and user turn into a large request.
- The runtime attempted `4096` output tokens even when the prompt already consumed most of the `8192` context window.
- vLLM correctly rejected the request with a `400` validation error.
- The browser then looked frozen because no assistant delta arrived.

## Fixes Applied

### Runtime

In `desktop_engine/vllm_openai_runtime.py`:

- `warm_start()` now warms both:
  - remote model discovery
  - local tokenizer initialization
- token counting now works with Hugging Face `BatchEncoding`
- max output tokens are resolved against the actual prompt token count instead of always falling back to the GUI cap
- Qwen thinking mode is disabled explicitly for public runtime requests

The same logic was mirrored to the private/exclusive vLLM runtime copy for parity.

### Launch Path

- `run_vllm.ps1` remains an internal helper/debug surface.
- `run_portal.ps1` remains the canonical public command.
- WSL probing and `/v1/models` health checks now use authenticated requests and fail honestly.

## Verification

### Direct runtime verification

A direct `VllmOpenAIRuntime` smoke returned a normal greeting in about `1.3s` after the fixes landed.

### Browser end-to-end verification

A browser adapter smoke on a fresh local port emitted:

- `status: Preparing response...`
- `status: Generating...`
- `assistant_delta`
- `turn_done`

This confirmed that the public stream path was no longer dying before the first visible token.

## Operator Guidance

- Keep using `run_portal.ps1` as the canonical public command.
- Keep the WSL vLLM environment in `~/.athena_vllm` rather than a Windows-mounted path.
- If a future public request appears frozen, check `vllm_stderr.log` first for prompt-length validation errors before assuming the model failed to load.

## Repo Hygiene Follow-Up

The one failed experiment path `.wsl_venv/` should stay out of the repo and remain ignored. Runtime scratch files under `.local/` should also remain local-only.
