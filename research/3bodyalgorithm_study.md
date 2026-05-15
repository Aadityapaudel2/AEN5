# 3-Body Algorithm Study 2026-04-05

## Abstract

This document formalizes a three-agent inference architecture for competition math reasoning on a single H100-class runtime. The goal is to preserve the currently stable dual-agent system while introducing a third model for memory-grounded arbitration. The study combines prior multi-agent reasoning results from the literature with serving constraints from vLLM, Qwen3.5 deployment guidance, and H100 hardware limits. The immediate strategy is conservative: start from low context, scale incrementally, and accept only configurations that pass strict runtime and correctness gates.

## 1. Problem Statement

We want a production-stable 3-body workflow:

- `Athena` (solver): high-recall derivation generation.
- `Artemis` (critic): adversarial verification and contradiction search.
- `Agent01` (arbiter): memory-grounded gatekeeper for consistency and final-answer acceptance.

The core optimization target is not raw context length. It is stable, repeatable closeout quality under fixed GPU budget.

## 2. Research Foundations

### 2.1 Multi-agent debate as a baseline coordination primitive

Multiagent Debate shows that exchanging candidate chains and critiques across rounds can improve mathematical reasoning and factuality versus single-pass decoding ([R1](https://proceedings.mlr.press/v235/du24e.html), [R2](https://arxiv.org/abs/2305.14325)).

### 2.2 Diversity and consensus

Self-Consistency demonstrates that sampling diverse reasoning trajectories and selecting a consensus answer improves reasoning accuracy over greedy decoding ([R3](https://arxiv.org/abs/2203.11171)).

### 2.3 Deliberate search over thoughts

Tree of Thoughts supports explicit branch exploration, self-evaluation, and backtracking, which directly informs multi-round agent orchestration ([R4](https://arxiv.org/abs/2305.10601)).

### 2.4 Episodic language memory

Reflexion motivates textual episodic memory buffers that improve subsequent decisions without weight updates, aligning with NDJSON memory logging for `Agent01` ([R5](https://arxiv.org/abs/2303.11366)).

## 3. Serving and Hardware Constraints

### 3.1 H100 envelope

NVIDIA lists H100 SXM with 80 GB memory and 3.35 TB/s memory bandwidth ([R6](https://www.nvidia.com/en-us/data-center/h100/)). This is the hard budget for model weights + activations + KV cache.

### 3.2 vLLM memory and context controls

vLLM defines:

- `--gpu-memory-utilization` as a per-instance fraction of GPU memory.
- `--kv-cache-memory-bytes` as an override that bypasses inferred cache sizing.
- `--max-model-len` as total prompt+output context.
- `--enforce-eager` to disable CUDA graph and force eager execution.
- `--language-model-only` to disable multimodal pathways and free memory.

These are explicitly documented in Engine Arguments and API docs ([R7](https://docs.vllm.ai/en/stable/configuration/engine_args/), [R8](https://docs.vllm.ai/en/latest/api/vllm/)).

### 3.3 Streaming and API behavior

vLLM OpenAI-compatible server supports completions/chat and stream-related parameters, including `stream_include_usage` and `max_completion_tokens` in current docs ([R9](https://docs.vllm.ai/en/v0.16.0/serving/openai_compatible_server/)).

### 3.4 Qwen3.5 deployment guidance

Qwen3.5-9B official card states:

- default context 262,144,
- recommendations to reduce context on OOM,
- practical output-length guidance (32,768 typical, 81,920 for complex math/programming benchmarks),
- direct vLLM serving examples including `--max-model-len` and `--language-model-only`.

Source: official Hugging Face model card ([R10](https://huggingface.co/Qwen/Qwen3.5-9B)).

## 4. Current Baseline (Empirical)

Known-good local baseline:

- backend: `vllm_openai`
- models: `9B + 9B`
- context: `64k / 64k`
- GPU util: `0.29 / 0.29`
- dtype: `bfloat16`
- behavior: stable boot and closed-out benchmark runs

This baseline is locked while 2-body benchmarking continues.

## 5. Proposed 3-Body Algorithm

### 5.1 Memory contract

Canonical writable memory file:

- `/kaggle/working/memory_agent01.ndjson`

Read-only dataset paths under `/kaggle/input/...` are never treated as active memory targets.

Record schema:

```json
{"ts": 0.0, "role": "athena|artemis|agent01", "kind": "turn|fact|constraint|final", "text": "..."}
```

### 5.2 Objective function

For configuration `theta = (contexts, gpu_utils, max_tokens, rounds)`:

`J(theta) = Acc(theta) - lambda1 * Fail(theta) - lambda2 * Latency(theta) - lambda3 * Inconsistency(theta)`

Where:

- `Acc`: final-answer correctness rate.
- `Fail`: boot/runtime failure indicator.
- `Latency`: wall-clock per problem.
- `Inconsistency`: arbiter-detected contradiction rate.

### 5.3 Algorithm 1: Triadic Debate with Memory Arbitration (TDMA)

```text
Input: problem p, models M_A (Athena), M_C (Artemis), M_R (Agent01), memory file F
Output: final integer or fail

1. initialize transcript T <- []
2. load memory tail H <- tail(F, k)
3. for round t in {1..T_max}:
4.     a_t <- Athena.generate(p, T, H)
5.     c_t <- Artemis.criticize(p, a_t, T, H)
6.     r_t <- Agent01.audit(p, a_t, c_t, T, H)
7.     append (a_t, c_t, r_t) to T
8.     append normalized facts/constraints from r_t to F
9.     if final_tag(a_t) and final_tag(c_t) and same_integer(a_t, c_t) and gate_pass(r_t):
10.        return integer(a_t)
11. return fail
```

Design rationale:

- Debate signal from [R1, R2].
- Consensus bias from [R3].
- Branch-and-revise behavior from [R4].
- Persistent textual memory from [R5].

## 6. Context/Memory Scaling Protocol

### 6.1 Stage ladder

Start low and scale only on clean pass:

1. `2k / 2k / 2k`
2. `8k / 8k / 4k`
3. `16k / 16k / 8k`
4. `32k / 32k / 16k`
5. `64k / 64k / X` (discover `X` empirically)

### 6.2 GPU-util ramp

Initial 3-body guess:

- `0.22 / 0.22 / 0.22`

Increase by `+0.01` only after full gate pass.

### 6.3 Gate criteria per stage

A stage passes only if all conditions hold:

- all three services boot
- no early vLLM process exits
- no KV/hybrid layout assertion failures
- one or more complete runs reach gated closeout
- answer consistency improves or remains stable
- latency remains acceptable for notebook execution

## 7. Immediate Implementation Plan

1. Freeze 2-body benchmark settings and finish evaluation.
2. Add third model profile:
   - `/kaggle/input/models/aadityapaudel/qwen-9b-agent01/transformers/agent01/1`
3. Implement memory append/tail functions against `/kaggle/working/memory_agent01.ndjson`.
4. Launch TDMA at stage `2k/2k/2k`.
5. Log each stage outcome in this document.

## 8. Open Risks

- 3x9B with high contexts can exceed practical KV budget even when weights fit.
- Latency can dominate quality gains if arbitration prompts are too long.
- Memory file drift can introduce stale contradictions if not normalized.

## 9. Experimental Protocol (Concrete)

### 9.1 Hypotheses

- `H1`: Triadic debate (`Athena+Artemis+Agent01`) improves final closeout accuracy over dual debate at matched per-turn token budget.
- `H2`: Persistent memory (`memory_agent01.ndjson`) reduces contradiction recurrence across sequential questions.
- `H3`: A context ramp from `2k` to `64k` with strict failure gates yields higher stable throughput than direct `64k` cold-start attempts.

### 9.2 Primary Metrics

- `CloseoutAcc`: fraction of questions with valid final integer and known-correct answer.
- `ConsensusRate`: fraction of rounds where Athena and Artemis emit the same `<final>`.
- `ArbiterRejectRate`: fraction of rounds where Agent01 returns reject.
- `TTFT`: time-to-first-token during streamed generation.
- `E2ELatency`: end-to-end runtime per question.
- `CrashRate`: fraction of runs with backend startup/runtime failure.

### 9.3 Ablation Matrix

1. `Dual-Base`: Athena + Artemis, no Agent01 memory.
2. `Dual+Memory`: Athena + Artemis with memory tail included.
3. `Triad-NoMemory`: Athena + Artemis + Agent01 arbitration only.
4. `Triad+Memory`: full TDMA configuration.

Run each row at context stages `{2k, 8k, 16k, 32k, 64k}` and identical `max_completion_tokens=4096` unless OOM requires fallback.

### 9.4 Acceptance Threshold for Promotion

A stage is promoted only if:

- `CloseoutAcc` does not regress by more than `1.5%` vs previous promoted stage.
- `CrashRate <= 2%` over at least `50` questions.
- `Median(E2ELatency)` is within notebook SLA.
- `ConsensusRate` is non-decreasing or `ArbiterRejectRate` decreases.

## 10. Operational Invariants

- Never write memory to `/kaggle/input/...`; write only to `/kaggle/working/...`.
- Require explicit `<final>INTEGER</final>` for acceptance.
- Reject closeout if Athena and Artemis disagree on integer output.
- Keep per-turn completion cap at `4096` during benchmark unless test explicitly targets truncation behavior.
- Log every round decision with timestamp and latency.

## 11. Next Notebook Step

1. Keep current stable dual profile active for benchmark continuity.
2. Add third runtime profile at:
   - `/kaggle/input/models/aadityapaudel/qwen-9b-agent01/transformers/agent01/1`
3. Use TDMA scaffold with:
   - `memory_path=/kaggle/working/memory_agent01.ndjson`
   - `max_completion_tokens=4096`
   - `max_rounds=8`
4. Publish one table per stage:
   - startup time, TTFT, E2E latency, consensus, rejects, final accuracy.

## 12. Research Pass II (Streaming + Debate Robustness)

### 12.1 New findings from current literature and docs

1. Controlled debate evidence (2025) indicates that intrinsic model strength and team diversity dominate gains, while order/confidence visibility contribute less ([R11](https://arxiv.org/abs/2511.07784)).
2. vLLM Qwen3/Qwen3.5 reasoning parser documents that when thinking is enabled and `</think>` is missing, output is treated as truncated reasoning rather than final content ([R12](https://docs.vllm.ai/en/stable/api/vllm/reasoning/qwen3_reasoning_parser/)).
3. vLLM bench/engine docs expose explicit latency knobs relevant to notebook UX:
   - `--stream-interval`: `1` streams token-by-token; larger values batch tokens and can improve throughput at the cost of perceived responsiveness ([R13](https://docs.vllm.ai/en/stable/cli/bench/latency/)).
   - `--optimization-level`: startup-time vs runtime-performance tradeoff (`-O0` fastest startup, `-O3` best performance) and `--performance-mode` (`balanced|interactivity|throughput`) ([R13](https://docs.vllm.ai/en/stable/cli/bench/latency/), [R7](https://docs.vllm.ai/en/stable/configuration/engine_args/)).
4. OpenAI-compatible server supports `stream_include_usage`, `max_completion_tokens`, and request tracing (`X-Request-Id`, `request_id`) for per-turn observability ([R9](https://docs.vllm.ai/en/stable/serving/openai_compatible_server/)).

### 12.2 Consequences for this 3-body plan

- If Athena/Artemis are same-family 9B checkpoints, enforce role diversity through strict prompt contracts and disagreement obligations; diversity is a first-class variable, not optional.
- Treat apparent “silent” or truncated outputs as a parser-state problem before assuming model failure:
  - For stable visible content benchmarking, prefer `enable_thinking=False`.
  - Keep `max_completion_tokens=4096` and detect missing `<final>` as hard reject.
- For notebook interactivity during iteration:
  - prefer `--stream-interval 1`
  - prefer latency-oriented runtime mode (`interactivity`) while developing
  - switch to `balanced/throughput` only for bulk scoring.
- Add request IDs on every turn for traceability across Athena/Artemis/Agent01.

### 12.3 Revised promotion gate (added)

In addition to existing gates, require:

- `FinalTagRate >= 98%` (fraction of turns with parseable `<final>INTEGER</final>`),
- `TraceCoverage = 100%` (all requests carry request IDs),
- `StreamingLiveness`: at least one streamed delta arrives within SLA window on each turn.

## 13. AIMOAEN12 -> AIMOAEN13 Minimal Transition Plan

### 13.1 Migration principle

`AIMOAEN12` is a known-good two-model snapshot. Do not edit its core logic directly.
Create `AIMOAEN13` as a forked profile with additive changes only:

1. keep solver/clerk code path intact,
2. add third model load path behind a feature flag,
3. add third role prompts only after triple-load is stable.

This follows SOP-style role specialization from multi-agent literature ([R14](https://arxiv.org/abs/2303.17760), [R15](https://arxiv.org/abs/2308.00352), [R16](https://arxiv.org/abs/2308.08155), [R17](https://arxiv.org/abs/2411.04468)).

### 13.2 Minimal code-diff strategy (kernel-safe)

Implement the smallest possible additive change set:

- Keep existing `start_solver_clerk_runtime()` unchanged.
- Add a new optional loader:
  - `start_solver_clerk_agent_runtime(load_agent01: bool = False)`
- When `load_agent01=False`, behavior must be byte-for-byte equivalent to `AIMOAEN12`.
- When `load_agent01=True`, execute:
  1. solver load (existing),
  2. clerk load (existing),
  3. agent01 load (new, port `8002`).

No behavior-routing or triadic debate loop changes in this step.
This step is strictly a **triple-load harness**.

### 13.3 Initial `AIMOAEN13` runtime profile (bootstrap only)

Use conservative bootstrap values for first triple boot:

- profile: `kaggle_h100_vllm_text_triple_9b_bootstrap_2k`
- contexts: `2048 / 2048 / 2048`
- GPU util: `0.22 / 0.22 / 0.22`
- dtype: `bfloat16`
- enforce eager: `true` on all three
- kv cache dtype: `null`
- reasoning parser: `null`
- attention backend: `TRITON_ATTN`
- language model only: `true`

Candidate third model:

- `/kaggle/input/models/aadityapaudel/qwen-9b-agent01/transformers/agent01/1`

### 13.4 Third-role schema (personality contract)

Start with strict, short contracts to force role diversity:

- `Athena` (Solver):
  - task: derive solution paths, produce candidate final integer
  - style: concise derivation, explicit equations
- `Artemis` (Critic):
  - task: invalidate weak steps, locate contradiction or confirm proof
  - style: adversarial audit, no restatement unless needed
- `Agent01` (Archivist-Arbiter):
  - task: enforce output contract + memory normalization
  - output: `APPROVE <final>n</final>` or `REJECT: reason`
  - memory write target: `/kaggle/working/memory_agent01.ndjson`

### 13.5 Harness acceptance checklist (before behavior changes)

`AIMOAEN13` is accepted as “load-stable” only if:

- all 3 servers start in one kernel without restart,
- all 3 respond to health/model-list check,
- each serves one short probe completion,
- no early core exit, no KV layout assertions,
- request IDs present on all probes.

Only after this passes should CB10-style triadic conversation logic be enabled.

### 13.6 Minimal pseudo-flow for first enablement

```text
if PROFILE == AIMOAEN13:
    runtime12 = start_solver_clerk_runtime()         # unchanged path
    if ENABLE_AGENT01:
        agent01_session = load_vllm_openai_session(agent01_spec)
    return {solver, clerk, agent01?}
```

### 13.7 Why this is the minimal-risk path

- Preserves working `AIMOAEN12` by default.
- Isolates risk to one additive block (third session load).
- Separates infrastructure risk (boot/memory/stream) from reasoning-policy risk (new role behavior).
- Makes rollback trivial: disable `ENABLE_AGENT01`.

## References

- [R1] Du et al., "Improving Factuality and Reasoning in Language Models through Multiagent Debate," ICML 2024 (PMLR): https://proceedings.mlr.press/v235/du24e.html
- [R2] Du et al., arXiv version: https://arxiv.org/abs/2305.14325
- [R3] Wang et al., "Self-Consistency Improves Chain of Thought Reasoning in Language Models," arXiv: https://arxiv.org/abs/2203.11171
- [R4] Yao et al., "Tree of Thoughts," arXiv: https://arxiv.org/abs/2305.10601
- [R5] Shinn et al., "Reflexion," arXiv: https://arxiv.org/abs/2303.11366
- [R6] NVIDIA H100 product specifications: https://www.nvidia.com/en-us/data-center/h100/
- [R7] vLLM Engine Arguments (stable): https://docs.vllm.ai/en/stable/configuration/engine_args/
- [R8] vLLM API reference (memory/execution params): https://docs.vllm.ai/en/latest/api/vllm/
- [R9] vLLM OpenAI-compatible server (streaming/openai params): https://docs.vllm.ai/en/stable/serving/openai_compatible_server/
- [R10] Qwen3.5-9B official model card (serving and context guidance): https://huggingface.co/Qwen/Qwen3.5-9B
- [R11] Wu et al., "Can LLM Agents Really Debate? A Controlled Study of Multi-Agent Debate in Logical Reasoning," arXiv: https://arxiv.org/abs/2511.07784
- [R12] vLLM `Qwen3ReasoningParser` API reference: https://docs.vllm.ai/en/stable/api/vllm/reasoning/qwen3_reasoning_parser/
- [R13] vLLM `bench latency` CLI reference (`stream-interval`, async scheduling): https://docs.vllm.ai/en/stable/cli/bench/latency/
- [R14] CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society, arXiv: https://arxiv.org/abs/2303.17760
- [R15] MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework, arXiv: https://arxiv.org/abs/2308.00352
- [R16] AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation, arXiv: https://arxiv.org/abs/2308.08155
- [R17] Magentic-One: A Generalist Multi-Agent System for Solving Complex Tasks, arXiv: https://arxiv.org/abs/2411.04468
