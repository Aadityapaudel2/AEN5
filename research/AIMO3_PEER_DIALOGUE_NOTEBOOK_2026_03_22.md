# AIMO3 Peer Dialogue Notebook

Date: 2026-03-22

## Purpose

This note records the architectural change made in `kaggle_aimo3/AIMOAEN5.ipynb`:

- visible notebook behavior is now a natural `Athena` / `Sentinel` dialogue
- controller logic is hidden
- answer extraction is done from natural prose instead of explicit footer contracts

This is not a generic style preference.
It is a corrective response to concrete failure modes in the earlier staged solver/verifier notebook.

## Project Target

Working assumption for this phase:

- the system should be built toward an AIMO3 score target of `44+`
- this means every architecture choice should be judged by correctness lift per unit of complexity
- elegance matters because operator readability and debugging speed matter during notebook iteration

The target is not "make the transcript look nice."
The target is:

- better model behavior
- faster diagnosis
- lower protocol drag
- higher probability of getting to a competitive score

## What Failed In The Old Notebook

The earlier notebook shape pushed the models into an unnatural staged protocol:

- planning rounds
- solver exchanges
- verifier exchanges
- final lock / final verifier phases
- visible fallback chatter
- strict footer markers such as `Verdict`, `Agreement`, and `Current answer`

Observed failure modes:

1. The verifier persona pushed Phi toward evaluator/disclaimer behavior instead of mathematical collaboration.
2. The visible transcript was polluted by controller scaffolding, making failures harder to inspect.
3. Footer-driven parsing became the visible objective, so protocol compliance could dominate real reasoning.
4. Retry and fallback events were visible, which made the transcript ugly and analytically noisy.
5. The controller was effectively writing part of the mathematical story through fallback injections.

The result was a notebook that was hard to trust, hard to read, and hard to debug.

## Current AEN5 Notebook Contract

The canonical AEN5 notebook surface is now:

1. One opening controller objective.
2. Athena opens the discussion naturally.
3. Sentinel replies naturally.
4. The controller alternates the dialogue under a hard round cap.
5. The visible notebook prints only:
   - the question
   - `Athena: ...`
   - `Sentinel: ...`
   - a compact final summary

The controller still exists, but it should be mostly invisible to the operator.

## Prompting Principles

### Athena

Athena should:

- act as a peer collaborator
- propose routes
- revise weak steps
- ask short clarifying questions when useful
- state candidate answers naturally

Athena should not:

- emit stage labels
- emit footer contracts
- speak to the controller
- roleplay a formal solver phase

### Sentinel

Sentinel should:

- act as a peer collaborator
- be slightly more analytical
- challenge weak reasoning plainly
- ask short clarifying questions if blocked
- state candidate answers naturally

Sentinel should not:

- roleplay a formal verifier
- emit `Verdict`, `Agreement`, or `Concrete error` fields
- produce policy boilerplate or disclaimers
- speak as if it were grading Athena

## Hidden Controller Rules

The controller should still do real work, but that work should stay off the visible transcript.

### Required hidden behavior

- natural-language candidate extraction
- agreement / contradiction detection
- bounded retry for low-signal turns
- convergence-based stop conditions
- stable fallback selection when convergence fails
- JSON diagnostics capture

### Forbidden visible behavior

- `Solver exchange X/Y`
- `Verifier exchange X/Y`
- `Planning`
- `Final verifier`
- fallback chatter
- injected controller-authored math prose

## Why This Is Not "Free-Form Swarm"

This update does not mean the project is now betting on unlimited open-ended multi-agent chatter.

The new notebook is still:

- two-model
- bounded
- controller-governed
- extraction-based
- evaluation-friendly

The change is specifically about the notebook surface and the prompt shape:

- natural visible dialogue
- hidden orchestration
- bounded stop logic

That is very different from an unbounded swarm.

## Relationship To Older AIMO Notes

### `AIMO3_VERIFIER_CONTRACT_2026_03_20.md`

Keep it as a historical note for the strict structured verifier experiment.
Do not treat it as the current AEN5 notebook contract.

### `AIMO3_QWEN9B_PHI15B_FLOWCHART_2026_03_20.md`

Keep it as the structured solver/verifier algorithm note.
It is still useful as an ablation or fallback design, but it is not the current visible AEN5 notebook surface.

## Immediate Research Implications

The next research loop should focus on whether this peer-dialogue surface improves actual math outcomes, not just readability.

Required checks:

1. Casual prompt smoke:
   - transcript should remain natural
   - identities should stay stable

2. Easy math smoke:
   - both models should converge naturally
   - controller should extract the answer without visible footers

3. Hard AIMO-style smoke:
   - transcript should remain clean even under failure
   - retries should remain silent
   - no controller-authored mathematical fallback should appear in visible output

4. Real fixed-pack evaluation:
   - compare the old structured solver/verifier notebook against the new peer-dialogue notebook
   - track exact score, stability, error type, and operator readability

## Research Position After This Change

For the notebook surface, the current repo position should be:

- bounded two-model peer dialogue is preferred over visible staged solver/verifier theater
- hidden answer extraction is preferred over footer-driven visible protocol contracts
- controller diagnostics should live in saved artifacts, not in the human-facing transcript
- all future notebook work should be judged against the `44+` target, not against protocol complexity for its own sake

## Short Version

The lesson is:

- keep the controller strong
- keep the transcript clean
- keep the models talking like collaborators
- keep the protocol bounded
- keep every design choice aligned with the competitive target
