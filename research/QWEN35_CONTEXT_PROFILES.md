# Qwen3.5 Context Profiles for Athena V5

Date: 2026-08-30

## Decision

Athena's public runtime keeps the **native** practical profile as the default:

- configured maximum model length: 128000
- no RoPE override
- no experimental long-context environment flag
- compatible with the current local public runtime

The repository also contains a guarded **yarn_1010k** profile:

- configured maximum model length: 1010000
- YaRN factor: 4.0
- original maximum position embeddings: 262144
- Qwen3.5 multimodal RoPE fields preserved
- explicit experimental opt-in required
- intended for H100-class or equivalent hardware

The source of truth is browser/config/context_profiles.json. The launcher reads that file instead of maintaining a second copy of the RoPE object.

## Why YaRN is not memory

YaRN extends the token window used by the inference engine. It does not decide what should be remembered, distinguish user facts from prior assistant claims, retrieve relevant history, provide user controls, or protect private/public boundaries.

Athena's learner continuity remains a separate controller system:

- recent completed turns
- short-lived session focus
- durable learner profile
- query-aware older-turn recall
- verified curriculum context

A larger token window can carry more text, but it is not a substitute for selective, governed memory.

## Upstream basis

The official Qwen3.5-4B model card states that the model supports 262144 tokens natively and can be extended to 1010000. It recommends reducing the window when memory is constrained while retaining at least 128K when possible:

- https://huggingface.co/Qwen/Qwen3.5-4B

The same model card provides the exact Qwen3.5 YaRN override now represented in the local profile, including text_config.rope_parameters, partial_rotary_factor, the multimodal RoPE section, VLLM_ALLOW_LONG_MAX_MODEL_LEN=1, and max-model-len 1010000.

Current vLLM documentation uses hf-overrides with rope_parameters; the older rope-scaling flag is not the current route:

- https://github.com/vllm-project/vllm/blob/main/docs/features/context_extension.md

The installed WSL vLLM 0.17.1 command-line help was checked locally and exposes both hf-overrides and max-model-len.

## Safety gate

This command is intentionally insufficient:

~~~powershell
.\run_vllm.ps1 -ContextProfile yarn_1010k
~~~

It fails before launch because the explicit experimental acknowledgement is absent.

The full activation shape is:

~~~powershell
.\run_vllm.ps1 `
  -ContextProfile yarn_1010k `
  -AllowExperimentalUltraLongContext `
  -RuntimeName shared `
  -Restart
~~~

Do not run that command on the current 16 GB workstation as a routine portal configuration. The KV-cache requirement at 1.01M tokens is a hardware deployment decision, and static YaRN can reduce short-context quality. The current local public runtime should stay at native / 128000.

No runtime was restarted or modified while this profile was implemented.

## Non-mutating command preview

The launcher supports `-DryRun`. This mode validates and resolves the selected profile, emits a structured argument list with the API key replaced by `<redacted>`, and exits before endpoint probing, stale-state cleanup, warm-up, runtime-state writes, process start, or process stop.

Use native dry-run to verify the routine 128000 configuration. The `yarn_1010k` preview remains guarded by `-AllowExperimentalUltraLongContext`; even with that acknowledgement, dry-run only proves configuration and intact JSON forwarding through the WSL bash-script transport. It does not allocate a KV cache or claim that the present workstation can host the profile.

For any future 1.01M experiment, capacity planning must consider model weights, KV-cache dtype, active sequence length, concurrency, batch shape, and operational safety margin together. KV-cache demand grows with active context and concurrency, so H100-class or equivalent hardware is a planning baseline rather than a guarantee.
