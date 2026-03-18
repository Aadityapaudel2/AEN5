# Linux H100 Protocol Report

## Scope

This report is derived from the Linux migration and protocol-development notes captured in:

- `codexcontextlinux.txt`

It records the main technical findings from the Ubuntu/H100 phase and why that work matters for the next AIMO step.

## Executive Summary

The Linux/H100 phase was not just an infrastructure move. It changed the working research thesis.

The original immediate goal was to bootstrap the Windows-developed Athena/AEN stack on a remote Ubuntu machine, validate local model inference there, and recover a usable workflow for larger Qwen checkpoints. That part succeeded. But the more important result was architectural:

- raw model scale alone did not solve hard math reasoning reliably
- unstructured two-model chat was too slow and too noisy
- a bounded solver/verifier protocol materially improved the quality of mathematical reasoning

The main takeaway is that the strongest gains are coming from protocol discipline, not from simply demanding longer free-form outputs.

## Infrastructure Outcome

The project was migrated from a Windows-first workflow to an Ubuntu Linux environment on an NVIDIA H100. The practical reasons were:

- better inference stability
- cleaner GPU-oriented package management
- easier reproducibility for heavier local checkpoints
- a realistic environment for submission-grade experimentation

During that migration, the following paths were made workable:

- the single-model AEN/Athena path on Linux
- the two-model evaluator on Linux
- a headless benchmark-oriented workflow

Several Linux-specific failures had to be corrected:

- Qt/XRDP/WebEngine instability
- missing XCB-related packages
- fragile launcher assumptions
- streamer timeout behavior on slower first-token startup

The result was a usable Linux path for both single-model and two-model work.

## Single-Model Result

The single-model interface remained important as a baseline. It was adapted for Linux and stabilized in both Tk and Qt forms. The main research value of that work was not the UI alone, but the ability to compare:

- solo model behavior
- bounded two-model behavior

under a shared runtime context.

This matters because any claim that the protocol helps should be isolated from unrelated UI drift.

## Why the Two-Model Evaluator Changed

The original evaluator behaved too much like an open-ended chat demo. That created several failure modes:

- identity drift
- resume behavior that felt like a restart
- weak injection semantics
- verifier collapse into a second solver
- premature stop conditions
- useless post-success chatter

That made it a poor fit for competition-style mathematics, where the system needs to reason under structure and stop once the work is actually complete.

## Protocol Shift

The evaluator was upgraded into a bounded mathematical reasoning harness.

Core role split:

- Solver
- Verifier

Core phase progression:

1. plan
2. challenge
3. solve
4. verify
5. revise
6. reverify

This change enforced a crucial behavioral separation:

- the solver is responsible for advancing a solution
- the verifier is responsible for exposing weak assumptions, missing cases, invalid reductions, local arithmetic risks, and unsupported jumps

The verifier was also reframed as collaborative rather than purely adversarial. It is expected to:

- answer the solver's direct question
- provide short concrete suggestions
- help the solver obtain a correct result

That is a stronger research stance than a passive checker.

## Stop Condition

One of the most important protocol upgrades was the stop rule.

The system does not stop on the first apparent verification.

The strengthened condition requires:

1. the solver gives a concrete final answer
2. the verifier marks that answer `VERIFIED`
3. the solver later gives the same final answer again
4. the verifier marks that same final answer `VERIFIED` again

This two-pass verified-close rule is not a proof of correctness, but it is materially stricter than accepting the first plausible-looking answer.

## Continue Loop and Injection

The Linux work also clarified that a usable evaluator must be interactive, not disposable.

Two features became first-class:

- Continue Loop
- side-specific prompt injection

Continue Loop now preserves:

- transcript state
- role names
- side histories
- prior loop artifacts
- system prompts

Injection now behaves as evaluator-level steering rather than ordinary chat content. It is:

- side-specific
- queued for the next targeted turn
- resumable across completed loops
- visible in the UI through queued counts

This is operationally important because hard math evaluation often requires resuming a nearly complete loop to challenge one step or force a more careful check.

## Main Research Finding

The Linux notes support a strong claim:

For hard mathematical reasoning, protocol quality can matter at least as much as raw model scale.

The working evidence behind that claim was:

- a strong solo model can still fail due to local structural or arithmetic errors
- a bounded two-model protocol can recover the correct answer on the same base model
- the decisive improvement comes from enforced planning, challenge, verification, and bounded revision

This does not mean bigger models are irrelevant. It means the protocol is a primary lever rather than a decorative wrapper.

## Multimodal Retention Note

Another important observation from the local full-SFT work is about vision retention.

The tuned checkpoint folder for the canonical 4B run did not itself carry the full set of multimodal processor artifacts one might expect from a base multimodal model, such as `preprocessor_config.json`. Even so, the validated runtime still preserved image capability:

- `supports_vision = True`
- `image_processor_loaded = True`

The reason is architectural, not magical. The runtime resolved the vision-capable base `Qwen3.5-4B` path and overlaid the tuned language weights on top of that base. So the experiment does **not** show that vision can be invented for arbitrary text-only checkpoints. It shows something narrower and important:

- when the base model is already natively vision-capable
- and the runtime correctly reuses the base multimodal components
- full SFT on the language side did not erase vision capability in the resulting working system

This matters for later tuning decisions because folder contents alone can be misleading. A tuned export lacking explicit processor files does not necessarily mean that multimodal capability has been lost, provided the runtime is intentionally restoring the correct multimodal base context.

## Implications for AIMO

The next AIMO step should not begin with a large swarm.

The Linux/H100 work supports this order:

1. strong deterministic single-solver baseline
2. strong verifier loop
3. small swarm only if it beats the verifier baseline under a fixed budget
4. larger orchestration only if ablations show a real lift

In other words, the right question is not "how many agents can we add?" but "what is the smallest architecture that reliably improves correctness?"

## What This Report Changes

After the Linux/H100 phase, the project direction should be understood as:

- desktop/runtime stabilization was necessary groundwork
- but the core research contribution is now the reasoning protocol
- future tuning should focus more on process supervision than on generic answer imitation
- future experiments should compare architectures under fixed budgets, not just compare models informally

## Next Research Actions

The most defensible immediate follow-ups are:

1. build a fixed hard-case evaluation pack across algebra, combinatorics, geometry, number theory, and logic
2. compare solo vs bounded two-model behavior on the same base model
3. log outcome changes, error types, latency, and loop termination quality
4. convert successful rescue traces into process-style training assets later

## Verdict

The Linux/H100 migration succeeded technically, but its larger value was conceptual.

It established that the project should treat protocol design as a core research object. The relevant competition advantage is not just better prompting or larger checkpoints. It is a disciplined reasoning scaffold that forces better mathematical behavior from the same underlying models.
