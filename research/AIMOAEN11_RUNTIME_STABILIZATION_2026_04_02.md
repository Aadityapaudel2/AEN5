# AIMOAEN11 Runtime Stabilization 2026-04-02

## Scope

This note records the current state of the `AIMOAEN11` Kaggle notebook after the vLLM pivot and the first serious stabilization pass on the in-process `transformers + accelerate` runtime.

It is intended to answer four questions:

1. What is already working?
2. What failed and why?
3. What do the official Qwen and Hugging Face sources imply about the correct architecture?
4. What is the next coherent path instead of random notebook iteration?

## Executive Summary

The project is past the model-load crisis and is now in the behavior-coherence phase.

The main architectural facts are:

- the original dual-vLLM Kaggle design failed for memory reasons, not because the Qwen checkpoints were bad
- the `AIMOAEN11` pivot to in-process `transformers + accelerate` was the correct move
- the Qwen3.5 fast path is now genuinely active on Kaggle when the canonical wheel stack is preserved
- both the 35B A3B solver and the 4B clerk can load together on one Kaggle H100 under the current direct runtime
- the remaining failures are mostly notebook/runtime-contract problems rather than raw serving or package failures

The most important coherence lesson is this:

- runtime validation must be separated from Athena/Artemis roleplay behavior

The probe harness originally mixed:

- cache validation
- memory validation
- direct-answer validation
- collaborative persona behavior

That created confusing failures where the runtime was healthy but the probes still failed because the models were behaving like Athena and Artemis instead of like minimal validation agents.

## Current Known-Good Runtime Facts

### Canonical `CB2` stack

The known-good Kaggle fast-path tuple is:

- Python `cp312`
- Torch `2.9.0`
- CUDA tag `cu12`
- ABI `cxx11abiTRUE`
- platform `linux_x86_64`

Canonical pinned artifacts:

- `transformers` source ref:
  - `git+https://github.com/huggingface/transformers.git@5c1c72be5f864d10d0efe8ece0768d9ed6ee4fdd`
- `causal-conv1d` wheel:
  - `causal_conv1d-1.6.1+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl`

Important operational lesson:

- `CB2` must not allow pip to re-resolve core dependencies, or Kaggle can drift from `torch 2.9.0 / cu12` to `torch 2.11.0 / cu13`, which breaks the canonical fast-path wheel match

### Fast path

The current notebook now treats Qwen fast-path readiness as:

- `fla-core` importable
- `flash-linear-attention` importable
- `causal_conv1d` importable
- Qwen-specific FLA symbols importable:
  - `FusedRMSNormGated`
  - `chunk_gated_delta_rule`
  - `fused_recurrent_gated_delta_rule`

This matters because `find_spec("fla")` alone was not enough. A prior false-positive state existed where `fla` imported but the Qwen MoE path still failed at `from fla.modules import FusedRMSNormGated`.

### Direct runtime load

Under the AEN11 direct runtime, the following has already succeeded on Kaggle:

- solver session load at context limit `196608`
- clerk session load at context limit `131072`
- combined post-load GPU allocation around `72.39 GiB`

This is strong evidence that:

- the notebook can now load both models together
- the remaining work is not primarily about package bootstrapping

## What Failed and Why

### Phase 1: dual-vLLM failure

The original AEN6/AEN11 dual-vLLM idea failed because the second resident engine could not allocate KV cache after the large solver was already live.

That was a serving-architecture failure, not a checkpoint failure.

### Phase 2: model recognition and fast-path issues

Early direct-runtime failures included:

- `qwen3_5_moe` not recognized by the installed `transformers` wheel
- missing `fla.modules`
- missing `causal-conv1d`

These were corrected by:

- pinning the working `transformers` git revision
- installing the exact Kaggle `causal-conv1d` wheel
- validating the actual Qwen MoE fast-path symbols

### Phase 3: chat-template bootstrap bug

Once the solver finally loaded, the session layer failed on:

- `TemplateError: No user query found in messages.`

Root cause:

- the session bootstrap called Qwen's chat template on an empty message list

The official Qwen template does in fact raise on that condition.

### Phase 4: cache misuse

After the empty-message bug was fixed, the notebook still failed because it was manually constructing a generic `DynamicCache` and then re-feeding the full prompt into generation.

That was wrong for two reasons:

1. Qwen3.5 MoE can use model-specific cache behavior
2. incremental generation with cache reuse must only feed the uncached suffix, not the entire cached prefix again

### Phase 5: probe contamination by persona and thinking mode

After the cache path became operational, `CB08.5` still produced strange outputs such as:

- reasoning headers
- greetings to Artemis
- refusals to "memorize" tokens

These were not runtime-load failures. They were probe-design failures.

The validation suite was reusing:

- the Athena/Artemis system prompts
- thinking-enabled sessions
- very small answer budgets

So the probes were measuring persona behavior and reasoning overhead instead of direct memory/math correctness.

## Research-Backed Coherence Findings

### 1. Qwen3.5 thinks by default

The official Qwen3.5 model card says the model emits thinking content by default and recommends explicit disabling for direct-response mode.

Implication for AEN11:

- validation probes should default to non-thinking mode
- collaborative notebook runs may later choose to enable thinking again, but that should be an explicit ablation, not the default assumption

### 2. `enable_thinking=False` still affects the template surface

The official `chat_template.jinja` for Qwen3.5-35B-A3B shows that when `add_generation_prompt=True`, the assistant preamble is always inserted, and if `enable_thinking=False`, the template still emits an empty `<think>\n\n</think>\n\n` block before the visible answer.

Implication for AEN11:

- "non-thinking mode" is not the same as "no think tags exist in the raw prompt text"
- visible-history cleaning must continue stripping leading think blocks

### 3. Empty-message chat-template calls are invalid

The official Qwen template raises `"No user query found in messages."` when there is no valid user query in the message list.

Implication for AEN11:

- empty sessions must not call the chat template at all
- prompt-fit checks must be safe on zero-message state

### 4. Hugging Face chat-template rules matter operationally

The Hugging Face chat-template docs make two relevant points:

- chat templates already include the needed special tokens
- `add_generation_prompt=True` is what marks that the assistant should answer next

Implication for AEN11:

- use `apply_chat_template(..., tokenize=True, add_generation_prompt=...)` as the canonical formatting path
- do not hand-roll special tokens around the template output

### 5. Cache reuse must respect model-specific cache behavior

The Hugging Face cache guide says `DynamicCache` is only the default for most models and explicitly notes that model-specific cache classes also exist.

Implication for AEN11:

- do not force a generic cache object for Qwen3.5 MoE
- let the model construct its own `past_key_values` representation during prefill

### 6. Context folding is not a hack; Qwen already recommends it in practice

The official Qwen3.5 model card notes that many search-agent setups using this model prune earlier tool responses once cumulative context crosses a threshold.

Implication for AEN11:

- visible-history trimming and rebase are directionally consistent with Qwen's own long-context practice
- the notebook should not treat pruning as a failure mode by default

### 7. Thinking mode and context ambitions should not be conflated

The Qwen3.5 model card recommends maintaining at least `128K` context when preserving thinking capability, but this is specifically about thinking-mode behavior.

Implication for AEN11:

- if the notebook runs in non-thinking mode, it does not need to justify every runtime setting against "preserve thinking" guidance
- context and thinking should be ablated independently

## Architectural Lessons

### Separate three layers that were previously mixed

The notebook needs three explicit operating modes:

1. **runtime validity**
   - can the models load
   - is fast path active
   - does cache reuse work
2. **behavioral contract**
   - can one session remember something across turns
   - are solver and clerk isolated
   - does the model obey the exact `<final>INTEGER</final>` contract on a direct prompt
3. **collaborative math quality**
   - does the Athena/Artemis protocol improve correctness on real AIMO-style questions

These should not be tested with the same prompts or the same system prompts.

### Keep validation prompts minimal

`CB08.5` should use probe-specific prompts and probe-specific system prompts.

It should not inherit:

- the Athena teaching prompt
- the Artemis student/reviewer prompt
- long-format collaborative tone

because those prompts are optimized for discussion, not for exact-answer probes.

### Keep visible-only history

The notebook's current visible-only carry rule remains directionally correct.

It aligns with the fact that:

- Qwen thinks by default
- raw think material should not contaminate carried history
- validation and exact-final parsing should operate on visible content only

### Use no-thinking as the current baseline

For AEN11 specifically, the baseline should now be:

- `SOLVER_ENABLE_THINKING = False`
- `CLERK_ENABLE_THINKING = False`
- moderate low-variance sampling

Then thinking can be reintroduced only if:

- `CB08.5` is stable
- `CB10` works
- an ablation shows a meaningful lift on real math questions

## Current Working Theory For Coherence

The best current interpretation is:

- AEN11 can already load the models and maintain cache-backed continuity
- the remaining incoherence is prompt-layer and contract-layer incoherence, not hardware incoherence

That means the next lift should come from:

1. cleaner collaborative prompts
2. smaller and more explicit behavioral contracts
3. probe/runtime separation
4. targeted sampling ablations

It should not come from:

- adding more agents
- reintroducing dual-vLLM
- blindly increasing context

## Recommended Next Ablations

### Immediate

1. Keep `CB08.5` in non-thinking mode only.
2. Keep probe system prompts minimal and non-roleplay.
3. Measure whether the two-session relay still fails after the no-thinking probe prompt fix.
4. Raise the context-pressure probe only enough to guarantee one true trim event rather than arbitrary overflow.

### Short next step

1. Run one easy real math question through `CB10`.
2. Confirm:
   - no transcript contamination
   - no cross-session memory bleed
   - exact-final extraction still works

### Controlled sampling study

The current notebook-default move to `temperature=0.23` may improve determinism, but it is below Qwen's official non-thinking recommendations.

That is acceptable as an experiment, but it should be treated as a local ablation rather than an official best-practice assumption.

Recommended direct comparison:

- `temperature=0.23`
- `temperature=0.7`
- `temperature=1.0`

with the same:

- no-thinking mode
- exact-final prompt contract
- fixed question set

### Context study

Since model loading already succeeded at `196608 / 131072`, the context question should now be framed as:

- does the larger envelope improve actual math behavior enough to justify the extra latency and memory pressure?

Not:

- can the notebook technically ask for a huge number?

## Interactive Throughput Diagnosis

The next major issue discovered after runtime stabilization is not model loading but **interactive throughput**.

Observed behavior in Kaggle:

- the 35B solver and 4B clerk both load
- GPU memory remains heavily occupied after load
- during streamed manual runs, GPU utilization can appear near idle while CPU usage spikes to 100%
- the visible stream advances extremely slowly, to the point that the system feels CPU-bound despite running on an H100

This is a real systems problem. It should not be dismissed as prompt verbosity alone.

### What the official sources imply

The official Qwen3.5 model card explicitly says:

- inference efficiency and throughput vary significantly across frameworks
- for production or high-throughput workloads, dedicated serving engines such as SGLang, KTransformers, or vLLM are strongly recommended
- the Hugging Face Transformers serving path is a lightweight route for quick testing and moderate load deployment

The Hugging Face `TextIteratorStreamer` docs also make its design intent clear:

- it stores print-ready text in a queue
- it is intended for downstream interactive applications such as demos
- it decodes tokens to text on the host side
- it runs generation in a separate thread while the application drains the queue

That means the current AEN11 live stream is not a GPU-native streaming path. It is:

- GPU-backed generation
- plus CPU-side decode, queue handling, callback execution, and notebook rendering

The Hugging Face optimization docs add another important constraint:

- a dynamic KV cache blocks the main `torch.compile` acceleration path
- static cache plus `torch.compile` can yield up to roughly 4x speedups, but support is model-dependent

So even inside pure Transformers, the current notebook path is not on the most optimized generation route.

### What the local code is doing

The current notebook adds several local throughput penalties beyond baseline Transformers:

1. **Python-side streamer path**

   In `cb06_session_and_cache_helpers.py`, AEN11 uses:

   - `TextIteratorStreamer`
   - a Python thread
   - a callback that prints every chunk with `flush=True`

   This is a high-overhead path for a notebook environment.

2. **Notebook rendering in the hot loop**

   The stream callback prints directly into the Kaggle notebook cell output.
   That means interactive UI rendering is part of the critical path for visible progress.

3. **Post-turn cache rebuild**

   After each completed assistant turn, the notebook rebuilds the session cache from the updated visible dialogue history.
   This is architecturally coherent for the session model, but it increases wall-clock turn time beyond raw decode time.

4. **Very large default answer budgets**

   In `cb06_5_sampling_parameters.py`, the current defaults still allow:

   - solver up to `8192` generated tokens per turn
   - clerk up to `4096` generated tokens per turn

   Those budgets do not by themselves explain the CPU bottleneck, but they magnify the cost of an already expensive streamed path.

### Practical conclusion

The most defensible diagnosis is:

- the model weights are resident on GPU
- but the visible streaming path is dominated by CPU-side work
- therefore the current manual surface does not behave like a proper H100 interactive inference stack

This means the main speed problem is probably **not**:

- GPU memory headroom
- context-window fit
- or prompt semantics alone

It is more likely:

- host-side streaming overhead
- notebook rendering overhead
- and the general limitation of using plain Transformers plus `TextIteratorStreamer` as the live interactive surface

### Coherent fix directions

Without changing prompts, the likely performance-improvement directions are:

1. **Measure decode separately from rendering**
   - first isolate whether generation itself is slow, or whether the notebook render path is slow

2. **Reduce host-side streaming overhead**
   - avoid printing every tiny chunk
   - batch UI updates more coarsely
   - keep the GPU busy while the host surface updates less often

3. **Reduce or defer post-turn rebuild cost**
   - if the cache rebuild happens after every turn, that should be measured separately from visible decode time

4. **Use a faster serving/runtime path for interactive streaming**
   - this is exactly why Qwen recommends dedicated serving engines for throughput
   - if interactive speed is a hard requirement, plain notebook-side Transformers streaming may simply be the wrong surface

5. **Investigate whether Qwen3.5 MoE supports more optimized cache/compile paths**
   - the HF optimization docs show why the current dynamic-cache route leaves performance on the table

### Research verdict on speed

The interactive slowness is a legitimate engineering issue, not a user illusion.

The current notebook proves:

- model loading works
- fast path libraries work
- cache continuity is directionally working

But it does **not** yet prove that AEN11 has a viable high-throughput interactive generation surface.

That should now be treated as a first-class systems problem.

## Practical Verdict

The runtime is no longer incoherent in the original sense.

The main instability has shifted from:

- package install
- architecture recognition
- fast-path libraries
- model load

to:

- validation design
- persona contamination
- exact-answer obedience

That is a much better problem to have.

The notebook is now close enough that the right strategy is disciplined ablation, not another architecture rewrite.

## Source Links

Primary external sources used for this note:

- Qwen3.5-35B-A3B model card:
  - https://huggingface.co/Qwen/Qwen3.5-35B-A3B
- Qwen3.5-35B-A3B chat template:
  - https://huggingface.co/Qwen/Qwen3.5-35B-A3B/blob/main/chat_template.jinja
- Hugging Face chat-template docs:
  - https://huggingface.co/docs/transformers/en/chat_templating
- Hugging Face cache guide:
  - https://huggingface.co/docs/transformers/v4.49.0/kv_cache
- Hugging Face generation streamer docs:
  - https://huggingface.co/docs/transformers/internal/generation_utils
- Hugging Face inference optimization docs:
  - https://huggingface.co/docs/transformers/main/llm_optims
- Hugging Face Accelerate big-model inference docs:
  - https://huggingface.co/docs/accelerate/main/en/package_reference/big_modeling

Local artifacts referenced:

- `kaggle_aimo3/AIMOAEN11/cb02_install_runtime_stack.py`
- `kaggle_aimo3/AIMOAEN11/cb04_runtime_identity.py`
- `kaggle_aimo3/AIMOAEN11/cb05_prompting_parsing_and_answer_normalization.py`
- `kaggle_aimo3/AIMOAEN11/cb06_session_and_cache_helpers.py`
- `kaggle_aimo3/AIMOAEN11/cb07_solver_clerk_controller_loop.py`
- `kaggle_aimo3/AIMOAEN11/cb08_load_local_solver_and_clerk_sessions.py`
- `kaggle_aimo3/AIMOAEN11/cb08_5_cache_and_memory_validation.py`
- `kaggle_aimo3/AIMOAEN11/cb02_canonical_snapshot_2026_04_01.md`
