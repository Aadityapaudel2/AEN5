# AIMOAEN6 Two-Agent Mathematical Coherence Research

Date: 2026-03-26

## Scope

This note records a focused research pass on two-agent mathematical reasoning
pipelines, with special attention to what should transfer into the local
`AIMOAEN6_Local` Athena/Artemis notebook.

The practical question is not whether "multi-agent systems" sound impressive.
The practical question is:

- how to keep mathematical reasoning coherent
- how to stop the checker from turning into a second drifting solver
- how to improve correctness without exploding prompt size or overfitting to
  theatrical debate

## High-Confidence Findings

### 1. Step-level verification is more trustworthy than outcome-only judgment

The strongest repeated signal across the literature is that math reliability
improves when supervision or checking happens at the process level rather than
only at the final-answer level.

Implication:

- for the notebook, Athena should expose a compact process artifact each turn
- Artemis should check that artifact
- asking Artemis to merely "like or dislike the final answer" is too weak

Sources:

- OpenAI, *Improving mathematical reasoning with process supervision*:
  https://openai.com/research/improving-mathematical-reasoning-with-process-supervision
- Lightman et al., *Let's Verify Step by Step*:
  https://arxiv.org/abs/2305.20050
- Uesato et al., *Solving math word problems with process- and outcome-based feedback*:
  https://arxiv.org/abs/2211.14275

### 2. Verifiers are useful selectors, but not magic

Verifier-guided selection can improve math performance, especially when ranking
multiple candidate solutions or completions.

Implication:

- the verifier should mostly evaluate and filter
- the verifier should not be trusted as a fully autonomous second solver
- if multiple solver drafts exist, verifier-based selection is reasonable

Source:

- Cobbe et al., *Training Verifiers to Solve Math Word Problems*:
  https://arxiv.org/abs/2110.14168

### 3. Backward verification is a real pattern

Self-verification helps when a candidate answer is treated as a hypothesis and
then checked backward against the original problem conditions.

Implication:

- once Athena proposes a final answer, Artemis should verify it backward from
  the claimed integer and the stated equations
- this is better than asking Artemis for a fresh freeform opinion

Source:

- Weng et al., *Large Language Models are Better Reasoners with Self-Verification*:
  https://openreview.net/forum?id=s4xIeYimGQ

### 4. Freeform debate is not the same thing as coherent verification

Multi-agent debate can help, but the more recent controlled evidence says that
success depends mostly on intrinsic reasoning strength and diversity, while
majority pressure can suppress correction.

Implication:

- do not let Athena and Artemis become two equal-status debaters
- that structure invites drift, consensus theater, and repeated re-interpretation
- keep Athena as the main reasoner and Artemis as the bounded reviewer

Sources:

- Du et al., *Improving Factuality and Reasoning in Language Models through Multiagent Debate*:
  https://arxiv.org/abs/2305.14325
- Wu et al., *Can LLM Agents Really Debate? A Controlled Study of Multi-Agent Debate in Logical Reasoning*:
  https://arxiv.org/abs/2511.07784

### 5. Over-relying on verifiers can fail as scale increases

There is now explicit evidence that verifier-guided search can degrade as the
number of candidates grows, because imperfect verifiers mis-rank candidates and
prune valid paths.

Implication:

- do not let Artemis act as an overconfident gatekeeper on weak evidence
- approval should require explicit support from Athena's relay
- the verifier should not be treated as globally authoritative when the signal
  is weak or vague

Source:

- Yu et al., *Scaling Flaws of Verifier-guided Search in Mathematical Reasoning*:
  https://openreview.net/forum?id=9vFB91wspX

### 6. Intrinsic self-correction is real, but prompt style matters

Self-correction is more likely to work with fair prompts and low temperature
than with emotionally loaded or highly leading review prompts.

Implication:

- Artemis should sound calm and precise, not combative
- prompting should avoid theatrical pressure like "prove Athena wrong"
- low-temperature verification passes are likely the safer direction

Source:

- Liu et al., *Large Language Models have Intrinsic Self-Correction Ability*:
  https://arxiv.org/abs/2406.15673

### 7. Programmatic or executable checks are unusually valuable for math

When a natural-language solution can be translated into an executable check,
verification quality improves substantially compared with raw majority voting.

Implication:

- for arithmetic-heavy or equation-heavy problems, lightweight executable checks
  are likely worth adding later
- this is stronger than relying only on one model to judge another model

Source:

- Toh et al., *Not All Votes Count! Programs as Verifiers Improve Self-Consistency of Language Models for Math Reasoning*:
  https://arxiv.org/abs/2410.12608

## What This Means For Athena / Artemis

### Athena should remain the only true solver

Athena should:

- interpret the problem
- propose equations
- carry the derivation forward
- state the answer only when ready

Athena should not:

- narrate prompt mechanics
- restart from scratch every turn
- produce long diffuse self-commentary

### Artemis should be a verifier, not Solver 2

Artemis should:

- inspect a compact structured relay from Athena
- identify the earliest concrete weakness
- say what is already solid
- say what still needs strengthening
- approve only when final answer plus verification are both present and coherent

Artemis should not:

- launch an independent derivation
- reinterpret the whole problem from zero
- propose many alternative routes at once
- act as a majority-vote judge

### The relay should be process-shaped, not chat-shaped

The evidence points toward relaying a bounded proof state rather than raw free
dialogue.

The most promising relay shape is:

- `Turn Summary`
- `Current Equations`
- `Current Claim`
- `What changed this turn`
- `Next Step`
- `Verification` only when a final answer is proposed
- `Final Answer` only when the answer is actually ready

This is stronger than sending:

- full transcript replay
- vague prose summaries
- natural conversation without explicit mathematical state

## Recommended Design Direction

### Best near-term notebook direction

1. Keep Athena as the single derivation engine.
2. Keep Artemis natural-sounding, but bounded.
3. Make Athena expose structured mathematical state each turn.
4. Make Artemis evaluate only that structured state.
5. Reserve `Approved.` for the final-answer plus verification case only.

### Best final-turn design

When Athena is ready, it should provide:

- a compact `Verification:` line with concrete substitutions or checks
- an explicit `Final Answer: \boxed{...}` line

Then Artemis should do one of two things only:

- `Approved.`
- one short natural reviewer comment explaining the earliest remaining gap

### Best future extension

If later engineering time allows, add a tiny executable checker path for cases
where Athena's final turn contains arithmetic or equation substitutions that can
be mechanically validated.

That extension is much more aligned with the research than adding more
freeform debate turns.

## What Not To Do

- do not use two freeform solvers of equal status
- do not let the verifier improvise long alternate derivations
- do not rely on unbounded dialogue history as the main memory mechanism
- do not expect verifier-guided search alone to keep scaling cleanly
- do not use highly leading or aggressive reviewer prompts
- do not confuse natural tone with unstructured checking

## Bottom Line

The literature supports the following thesis:

- less debate theater
- more structured proof state
- one solver
- one bounded verifier
- explicit backward verification at closeout
- optional executable checking when available

That is the direction most likely to improve mathematical coherence in
`AIMOAEN6_Local`.
