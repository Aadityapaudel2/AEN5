# AIMOAEN11 Transformers-Serve Postmortem And SGLang Pivot 2026-04-03

## Scope

This note records why the `AIMOAEN11` pivot from direct local `transformers + accelerate` to mixed `transformers serve --continuous-batching` plus local clerk should be treated as a failed branch, and why the next serving experiment should move to SGLang instead of further patching the current seam.

It answers four questions:

1. What actually failed in the `transformers serve` branch?
2. Why is the current mixed solver-server plus local-clerk architecture unhealthy?
3. What do the official Qwen and SGLang sources imply about a more coherent path?
4. What is the next experiment order for AEN11?

## Executive Verdict

The `transformers serve` branch should be discarded as an active AEN11 direction.

Not because the idea of continuous batching was wrong, but because the actual runtime surface proved too unstable and too expensive to normalize inside the notebook.

The practical verdict is:

- the notebook did achieve a successful `CB8` startup with a solver on `transformers serve`
- but `CB10` repeatedly failed on server/runtime edge cases before coherent interactive behavior was established
- the final system also became architecturally split:
  - solver on a patched OpenAI-compatible server
  - clerk on local `transformers`
- that split made the runtime contract harder to reason about, harder to debug, and harder to trust

The next coherent serving experiment is:

- keep `CB2` canonical and untouched
- stop investing in `transformers serve` hotfixes for AEN11
- pivot to SGLang as the next dedicated serving engine

## What Failed In Practice

### 1. `transformers serve` was not stable enough as a notebook-controlled engine

The branch encountered a long chain of server-side failures that were not ordinary prompt bugs:

- import-time crashes in `serve.py`
  - missing `TypeAdapter`
  - missing `ChoiceDeltaToolCall`
  - missing related OpenAI/Pydantic symbols
- endpoint mismatch during warmup
  - `/load_model` returned `404`
  - `/v1/models` returned `500`
- request-schema mismatches
  - unexpected `chat_template_kwargs`
  - missing required `model`
- continuous-batching implementation bugs
  - `'str' object has no attribute 'to'`
  - typed-content vs string-content handling failures
  - later `AttributeError: 'NoneType' object has no attribute 'generated_tokens'`

This is not a normal amount of notebook glue work. It is evidence that the specific `transformers serve` surface in the tested environment was not mature enough for this workflow.

### 2. The control path became too patch-heavy

To keep the server alive, AEN11 ended up carrying:

- import hotfixes into the installed `serve.py`
- request-format hotfixes
- content-shape normalization
- buffering and readiness fallback logic
- server log-tail diagnostics

At that point the notebook was no longer simply using a serving engine. It was effectively maintaining a private compatibility layer around that engine.

That is not a healthy submission notebook design.

### 3. The mixed-backend architecture was directionally wrong

The resulting architecture became:

- Athena / solver:
  - server-backed
  - OpenAI-compatible API
  - separate process
- Artemis / clerk:
  - local in-process `transformers`
  - different generation path
  - different streaming/render behavior

This meant the two agents were no longer running on one coherent serving contract.

Observed consequences:

- debugging became ambiguous because failures could be:
  - solver-server protocol bugs
  - local clerk generation bugs
  - notebook render bugs
  - controller bugs
- the two sides did not share the same request/response semantics
- interactive behavior became much harder to interpret

This matters because AEN11 is fundamentally a two-agent protocol notebook. A split backend should be treated as a temporary diagnostic trick, not a stable architecture.

### 4. The user-visible output still degraded

Even after startup stabilizations:

- Athena sometimes failed to surface cleanly in `CB10`
- Artemis produced corrupted multilingual garbage or repetition junk
- streaming/render behavior remained slow and operationally poor

So the branch did not merely fail on elegance. It also failed on the user-visible contract.

## Why SGLang Is A Better Next Pivot

### Qwen explicitly recommends dedicated serving engines for throughput

The official Qwen3.5 model cards state that inference efficiency varies significantly across frameworks and that for production or high-throughput workloads, dedicated serving engines such as:

- SGLang
- KTransformers
- vLLM

are strongly recommended.

This is a direct fit for the AEN11 problem, because the branch that failed was specifically the attempt to get a high-throughput serving surface out of `transformers serve`.

### SGLang exposes an OpenAI-compatible API directly

The official SGLang docs say:

- SGLang provides OpenAI-compatible APIs
- the server automatically applies the Hugging Face chat template when available
- extra request fields can be passed through `chat_template_kwargs`

That is important because AEN11 already has an OpenAI-style request path for the solver side. The conceptual client surface can survive the pivot.

### SGLang has Qwen-specific reasoning support

The official SGLang docs list:

- `--reasoning-parser qwen3`
- `chat_template_kwargs.enable_thinking`

for Qwen3 standard models.

That means the notebook does not have to invent special reasoning controls for Qwen; the server has an explicit supported path for it.

### SGLang has the serving controls AEN11 actually needs

The official SGLang server-arguments docs expose controls directly relevant to Kaggle H100 experiments:

- `--context-length`
- `--served-model-name`
- `--sampling-defaults`
- `--mem-fraction-static`
- `--cpu-offload-gb`

This is much closer to the actual AEN11 operational problem than the unstable `transformers serve` path.

## Recommended AEN11 Pivot Strategy

### Architecture decision

For the next branch, treat the following as the target:

- one serving family for both models
- one OpenAI-compatible request contract
- no mixed server/local generation path in the main notebook loop

That does **not** mean both models must be live on SGLang immediately on the first experiment.

It does mean:

- the architectural target should be dual-SGLang or single-SGLang-first with an explicit follow-up path
- not solver-SGLang plus clerk-local as the intended end state

### Experiment order

#### Phase 0: rollback mental model

Treat the preserved known-good AEN11 snapshot as the rollback anchor.

The `transformers serve` branch should be treated as a failed exploratory branch, not as the new baseline.

#### Phase 1: single-server solver smoke via SGLang

Goal:

- prove that the 35B solver can launch under SGLang on Kaggle H100
- prove clean chat/completions requests with the canonical Athena prompt
- prove non-thinking mode first

Do **not** add live token streaming yet.

First success condition:

- one clean Athena response through SGLang with turn-level rendering only

#### Phase 2: second-server clerk experiment

Goal:

- determine whether the 4B clerk can run as a second SGLang endpoint under the same session budget
- if needed, use CPU offload and reduced static memory fraction on the clerk

First success condition:

- one clean Artemis response through the same OpenAI-compatible serving family

#### Phase 3: only then restore dialogue protocol

Once both servers can answer cleanly:

- reattach the Athena/Artemis controller loop
- keep turn-level rendering first
- reintroduce streaming only after coherent turn-level output exists

## Practical Runbook Implications

The notebook should stop trying to save the current `transformers serve` stack.

Instead, the next experiment surface should:

- install SGLang in a dedicated optional block or separate branch
- launch solver first with a local model path and explicit served model name
- use OpenAI-compatible chat/completions requests
- pass Qwen thinking control through `chat_template_kwargs` only if needed

The branch should also keep the earlier AEN11 lesson:

- runtime validity and transcript rendering must be separated

So the first SGLang version should default to:

- no notebook streaming
- turn-level display only
- exact request/response logging

## Source-Backed Evidence

Primary sources:

- Qwen3.5-35B-A3B model card:
  - https://huggingface.co/Qwen/Qwen3.5-35B-A3B
- Qwen3.5-4B model card:
  - https://huggingface.co/Qwen/Qwen3.5-4B
- SGLang OpenAI-compatible API docs:
  - https://docs.sglang.io/basic_usage/openai_api_completions.html
- SGLang server arguments:
  - https://docs.sglang.io/advanced_features/server_arguments.html
- SGLang documentation index:
  - https://docs.sglang.io/

## Local Artifacts Referenced

- `kaggle_aimo3/AIMOAEN11/cb02_canonical_snapshot_2026_04_01.md`
- `kaggle_aimo3/AIMOAEN11/cb02_5_install_serving_support.py`
- `kaggle_aimo3/AIMOAEN11/cb06_session_and_cache_helpers.py`
- `kaggle_aimo3/AIMOAEN11/cb07_solver_clerk_controller_loop.py`
- `kaggle_aimo3/AIMOAEN11/cb08_load_local_solver_and_clerk_sessions.py`
- `research/AIMOAEN11_RUNTIME_STABILIZATION_2026_04_02.md`

## Bottom Line

The right conclusion is not:

- "AEN11 serving is impossible."

The right conclusion is:

- "`transformers serve` plus notebook hotfixing plus mixed local/server backends is the wrong branch for AEN11."

The next disciplined step is a clean SGLang pivot.
