# AIMOAEN6 Local Two-Model Runtime Status

## Scope

This note records the first confirmed end-to-end local runtime boot for the
`AIMOAEN6_Local` notebook on the Windows + WSL development machine.

The purpose of this note is to separate:

- runtime facts that are now proven to work
- protocol and prompt issues that are still unresolved

No snapshot is taken at this stage because the first manual protocol run is
still failing at the controller/prompt-budget layer.

## Confirmed Working

### Local notebook environment

- Notebook kernel: `D:\AthenaPlayground\.venv\Scripts\python.exe`
- Shared repo `.venv` remains usable after recovery.
- `AIMOAEN6_Local` is isolated from the old destructive `cb02` installer path.

### Managed WSL runtime path

`AIMOAEN6_Local` now launches both models through the repo's canonical
`run_vllm.ps1` helper and WSL Ubuntu.

Confirmed runtime state:

- solver:
  - model: `models/Qwen3.5-4B`
  - served model: `Qwen3.5-4B`
  - base URL: `http://127.0.0.1:8000/v1`
  - launcher: `wsl`
- clerk:
  - model: `models/Qwen3.5-2B`
  - served model: `Qwen3.5-2B`
  - base URL: `http://127.0.0.1:8001/v1`
  - launcher: `wsl`

Both runtime state files exist and point at live endpoints:

- `.local/runtime/vllm_solver_runtime.json`
- `.local/runtime/vllm_clerk_runtime.json`

### Local runtime envelope that works

The current proven bootable local profile is:

- solver context window: `4096`
- clerk context window: `2048`
- solver GPU memory utilization: `0.66`
- clerk GPU memory utilization: `0.30`
- `kv_cache_dtype = fp8_e4m3`
- `attention_backend = TRITON_ATTN`
- `language_model_only = true`
- CPU offload disabled

### Important backend findings

- The local `Qwen3.5-4B` model is a multimodal
  `Qwen3_5ForConditionalGeneration`, not a plain text-only model.
- For local notebook use, forcing `language_model_only = true` is necessary.
- The earlier FlashInfer backend path was not viable on this WSL machine
  because it attempted JIT compilation requiring `nvcc`.
- Forcing `TRITON_ATTN` avoided that local toolchain failure.

### Launch-path fixes that are now validated

- managed WSL launcher output is visible in the notebook
- solver and clerk readiness are visible
- warmup failure now fails fast instead of degrading into a misleading notebook
  timeout
- local `cb08` no longer hangs after the solver becomes ready

## Confirmed Not Yet Working

The first local manual protocol run is still not acceptable.

### Prompt / correspondence problem

Athena produced visible role leakage such as:

- narrating the prompt mechanics
- talking about "the user wants me..."
- confusing Athena and Artemis roles

This means the current role and correspondence contract is still too loose for
the small local instruct models.

### Reviewer budget failure

The first local run failed at the strict fit check on the clerk side:

- clerk context limit: `2048`
- clerk prompt tokens: `3912`
- requested clerk max tokens: `512`
- available tokens: negative

So the failure is not silent truncation. The notebook correctly refused to send
an impossible request.

### Generation-shape issue

The visible Athena output ended mid-thought, which strongly suggests the first
solver turn hit its generation budget before the reasoning stabilized.

## Current Interpretation

At this point the local notebook has crossed the important infrastructure
threshold:

- two models load
- both vLLM servers come up
- both endpoints answer
- streaming/visible dialogue is inspectable

So the main work has now shifted from runtime boot to protocol design:

- better role discipline
- better explicit answer contract
- larger or cleaner reviewer envelope
- better budgeting between prompt size and generation size

## Next Reasonable Experiment

The next agreed experiment is:

- symmetric local context windows: `8192 / 8192`

This should be treated as a protocol-envelope experiment, not as proof that the
final Kaggle/H100 configuration is solved.
