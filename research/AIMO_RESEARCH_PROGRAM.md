# AIMO Research Program

## Scope

This memo consolidates the strongest current research direction from these repo notes:

- `research.txt`
- `agentic_project_planning.txt`
- `aimo_win_plan.txt`
- `handoff.md`
- `desktop_engine/agentic/README.md`

It is intended to be the shortest accurate statement of what should be built next.

## Core Thesis

Winning or placing strongly on AIMO is unlikely to come from raw answer-style SFT alone.

The current evidence points to a different bottleneck:

- wrong initial structural assumptions
- premature commitment to weak plans
- weak verification
- arithmetic slips that go unchallenged
- open-ended multi-agent chatter that burns budget without improving correctness

Therefore the project should prioritize:

- deterministic reasoning structure
- visible tool traces
- bounded verification
- small, testable orchestration

before it scales toward bigger swarms or more tuning complexity.

## Canonical Build Order

### Phase 1: deterministic single-solver baseline

Build a solver that:

- uses deterministic decode
- emits strict structured output
- can call exact bounded tools
- produces one visible trace and one final answer

This baseline must be strong enough to deserve orchestration.

### Phase 2: deterministic verifier loop

Add one verifier pass that:

- challenges unsupported assumptions
- checks arithmetic and local reductions
- catches missing cases
- allows at most one repair cycle in the first version

This is the first place where real protocol lift should appear.

### Phase 3: small swarm only

Only after the verifier baseline is measured should the system move to:

- `N_scouts = 2` or `3`
- very small verifier count
- fixed token budget
- fixed wallclock budget

If a small swarm does not beat the verifier baseline under controlled conditions, scaling should stop there.

### Phase 4: diversity only if justified

Only if small-swarm lift is real should the project try:

- prompt-diversified scouts
- adapter-diversified scouts
- simultaneous multi-model loading

These are late-stage complexity multipliers, not the next step.

## Determinism Rules

The project should keep these as hard rules:

- fixed seeds
- deterministic decode
- fixed per-problem budgets
- explicit commit rules
- exact visible tool traces
- strict result schemas

And avoid:

- invisible reasoning requirements
- browser-owned orchestration logic
- time-dependent heuristics that break rerun stability
- large swarms before small-swarm lift is proven

## Role Model

The minimal conceptual role split remains:

- Router
- Scout
- Verifier
- Judge

But the first implementation does not need four simultaneously loaded models. One base model with role-specific prompting and deterministic policies is enough to test the architecture.

The headless math loop described in `desktop_engine/agentic/README.md` is already aligned with this direction. It gives a clean foundation for:

- solver/verifier sequencing
- artifact-driven reconstruction
- controlled evaluation

## Tool Policy

Tool use matters, but only in the right place.

Priority v1 tools:

- exact arithmetic
- polynomial identity checks
- modular arithmetic helpers
- bounded brute-force sanity checks

Tool traces must stay visible. The project should not rely on opaque model-native tool-calling conventions for core correctness.

The claim is not that tools replace reasoning. It is that exact, auditable tools should narrow the space of avoidable mistakes.

## Architecture Direction

Current repo-native target:

- `desktop_engine/` remains canonical
- desktop remains the canonical execution surface
- browser remains a thin adapter

New work should land under:

- `desktop_engine/agentic/orchestrator.py`
- `desktop_engine/agentic/policies.py`
- `desktop_engine/agentic/schemas.py`
- `desktop_engine/agentic/deterministic_tools.py`
- `desktop_engine/agentic/verifier.py`
- `desktop_engine/agentic/eval_harness.py`
- `desktop_engine/agentic/kaggle_entry.py`

This is consistent across the planning notes and avoids fragmenting the engine again.

## Training Direction

Future tuning should bias toward process supervision, not generic solved-problem imitation.

Higher-value future data types:

- plan extraction traces
- verifier questions
- revision traces
- rescue cases where protocol beats solo
- bounded tool-grounded correction traces

Lower-priority data types:

- more generic public solved math corpora with no protocol structure
- style-heavy answer imitation without verification behavior

This does not ban answer-style SFT. It means it should not dominate the next research loop.

## Benchmark Direction

The next evaluation pack should be small, fixed, and hard.

Include domains:

- algebra
- combinatorics
- geometry
- number theory
- logic

For each problem, compare:

- deterministic solo
- deterministic solver+verifier
- later, small swarm

Track:

- final answer
- correct/incorrect
- latency
- token budget
- first major error type
- whether verifier changed the outcome
- whether stop conditions behaved correctly

## Success Criterion

The next step is successful only if:

- repeated runs are stable
- verifier tools reject bad candidates more often than good ones
- visible traces remain intelligible
- the browser does not grow its own solver logic
- a small swarm beats the verifier baseline before larger orchestration is considered

## Final Research Position

The optimization target is not "more agents."

The optimization target is:

- more correctness per unit complexity

For this repo, that means the best immediate AIMO path is:

strong base model
+ deterministic scaffold
+ bounded verifier behavior
+ trace-visible exact tools
+ process-style data later

not a large free-form conversation system.
