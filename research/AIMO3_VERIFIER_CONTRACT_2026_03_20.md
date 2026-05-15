# AIMO3 Verifier Contract

Date: 2026-03-20

Historical note:

- this document describes the strict structured verifier contract used in the earlier staged solver/verifier notebook design
- it should not be treated as the current visible AEN5 notebook surface after the 2026-03-22 Athena/Sentinel peer-dialogue refactor
- for the current notebook-surface contract, see `research/AIMO3_PEER_DIALOGUE_NOTEBOOK_2026_03_22.md`

## Purpose

This note pins down the verifier behavior for the canonical two-model notebook:

- Solver: `Qwen3.5-9B`
- Verifier: `Phi-4-reasoning-vision-15B`

Serving note:

- the verifier checkpoint is vision-capable in principle
- the canonical AIMO runtime serves it in `text-only` mode
- no image inputs or multimodal profiling are used anywhere in this harness
- the official `phi_4_rv_vllm_plugin` is retained only to register the Phi architecture with vLLM
- `--language-model-only` is the serving contract that keeps the verifier off the multimodal processor path

The verifier is allowed to think.
The verifier is not allowed to drift.

## Core Principle

The verifier is not a second free-form solver.
Its job is to:

1. check the current solver draft
2. identify one concrete flaw if a real flaw exists
3. provide the minimal actionable repair

If the verifier cannot do that, its feedback is weak and should not drive a full solver revision.

## Required Verifier Output Contract

The verifier may emit one leading `<think>...</think>` block.
After stripping that block, the final visible output must be exactly:

```text
VERDICT:
FINAL_ANSWER_CHECK:
CONCRETE_ERROR:
ERROR_LOCATION:
WHY_WRONG:
MINIMAL_FIX:
PROPOSED_INTEGER:
ASK_BACK:
```

## Field Definitions

- `VERDICT`
  - one of: `pass`, `revise`, `insufficient`
- `FINAL_ANSWER_CHECK`
  - one of: `correct`, `incorrect`, `unclear`
- `CONCRETE_ERROR`
  - one of: `yes`, `no`
- `ERROR_LOCATION`
  - one specific step, claim, case, or equation
  - otherwise `none`
- `WHY_WRONG`
  - one short explanation of the failure
  - otherwise `none`
- `MINIMAL_FIX`
  - one concrete next action for the solver
  - otherwise `none`
- `PROPOSED_INTEGER`
  - an integer only if the verifier has a concrete correction
  - otherwise `none`
- `ASK_BACK`
  - one short clarification question if needed
  - otherwise `none`

## Actionability Rule

Verifier feedback is actionable only if all of the following hold:

- `VERDICT = revise`
- `CONCRETE_ERROR = yes`
- `ERROR_LOCATION != none`
- `WHY_WRONG != none`
- `MINIMAL_FIX != none`

If any of these fail, the solver should not treat the verifier output as a strong correction signal.

## Anti-Drift Rule

The verifier must not:

- restart the full solution from scratch unless the solver draft is unusable
- give multiple vague critiques instead of one strongest issue
- suggest a new integer without a concrete contradiction or arithmetic fix
- wander into unrelated alternative approaches

## Preferred Verifier Behavior

The verifier should produce statements of the form:

- `You are right on X`
- `You are wrong on Y`
- `The exact failing step is Z`
- `Repair by doing W next`

This is the intended tone:

- objective
- local
- corrective
- short

## Exchange Policy

### Planning Stage

Fixed two-cycle planning negotiation:

1. solver planning draft A
2. verifier critique A
3. solver planning draft B
4. verifier critique B

The solver is not allowed to enter the solving stage until this second planning
back-and-forth has completed.

### Solving Stage

Bounded exchange loop:

- minimum full exchanges: `2`
- maximum full exchanges: `11`

One full exchange means:

1. solver draft
2. verifier structured critique

### Final Answer Stage

The system may report a final answer only after:

1. agreement check 1 passes on a specific integer
2. agreement check 2 also passes on the same integer

That is, final reporting requires two consecutive agreement checks.

## Tie-Break Policy

Use this priority:

1. prefer a stable integer that survives both agreement checks
2. if the verifier provides a concrete contradiction and corrected integer, prefer the verifier-backed correction
3. if verifier criticism is weak or vague, prefer the most stable solver answer

## Notebook Implication

The canonical two-body notebook must implement:

- stripping the leading `<think>` block
- strict structured parsing of the verifier output
- actionability gating before solver revision
- text-only verifier serving via `--language-model-only`
- two planning back-and-forth cycles before solving
- minimum 2 and maximum 11 solving exchanges
- double agreement before final report
