# Athena identity and memory freshness hotfix

Date: 2026-08-31

Candidate: Athena public tutor profile v2.1

Status: rolled out and verified on the public portal

## Incident addressed

The previous public candidate exposed internal implementation identity in visible copy and allowed old learner context to reappear during greetings and purpose questions. That combination made Athena feel like an infrastructure wrapper with unreliable continuity instead of one coherent tutor.

## Remediation completed

- Removed implementation identity from served pages, browser configuration, readiness responses, and Athena identity answers.
- Kept the implementation boundary internal. Public identity questions now resolve directly to Athena's AEN tutoring purpose without announcing a nondisclosure rule.
- Archived two affected account stores intact (15 files total) rather than deleting them.
- Verified both archived stores are absent from their former active paths, so the next authenticated interaction begins from a fresh active learner store.
- Removed course codes, institution identity, assessment names, dates, deadlines, and upcoming-assessment claims from durable public learner-memory schemas.
- Suppressed summaries, recall, course material, and open loops on greetings, purpose questions, identity questions, and new threads.
- Added stale-date handling so a verified historical assessment cannot silently become an upcoming assessment.
- Strengthened Athena's persona around truth over agreement, evidence over performance, decisive teaching judgment, warm precision, independent checking, and correction without shame.
- Added deterministic identity, purpose, greeting, stale-context, and implementation-leak controllers while preserving general teaching about machine-learning concepts.
- Reworked the signed-out and authenticated entry surfaces with clearer Athena-first copy, visible tutoring principles, focused starter actions, and accessible memory controls.
- Added bounded parallel execution to the live behavior harness so repeated release evaluations remain practical without weakening any gate.

## Release evidence

- Unit tests: **109/109 passed**.
- Live tutor behavior: **35 probes x 3 repetitions = 105/105 passed**.
- Overall behavior pass rate: **100%**; required minimum: 90%.
- Controller regressions: **0**.
- Correctness critical gate: **39/39 passed**.
- Privacy critical gate: **15/15 passed**.
- Memory-injection critical gate: **12/12 passed**.
- Educator no-blocking critical gate: **18/18 passed**.
- Prompt profile: strict v2.1 profile, hash matched between preflight and live evaluation.
- Static gates: prompt JSON parse, Python compile, JavaScript syntax, PowerShell AST, privacy-marker scan, and `git diff --check` passed.
- Runtime preflight: passed against the existing healthy internal inference service; no inference-service restart was required.
- Archive verification: 2 stores, 15 files, former active paths absent.

## Rollout evidence

- Implementation commit `87deaec` was pushed to `origin/main`.
- The verified AthenaV5 portal process and named public tunnel were launched through the repository launcher; the existing healthy inference service was left unchanged.
- The local listener is owned by the expected portal process chain, and the public tunnel process matches the configured Athena portal tunnel.
- Public HTTPS smoke checks returned `200` for `/healthz`, `/AEN5`, and `/AEN5/runtime`.
- The public readiness response exposes only Athena service readiness fields.
- A public-page scan found no implementation identity or stale course/date markers on the landing, readiness, or service surfaces.
- Public authentication configuration exposes Google and GitHub, with Guest enabled; no institution choice is shown without a configured institution.
- An authenticated Guest session completed fresh greeting, identity, check-my-work, and educator-mode probes without implementation or stale-context leakage.
- New Thread cleared recent conversation state. Memory export returned a private, non-cacheable attachment. Confirmed Forget cleared recent pairs, summary state, and session state.
- The four tutor starter actions were present and mapped to learn, check-work, practice-building, and instruction-planning modes.
- Static accessibility contracts passed for the labeled composer, polite live regions, keyboard-visible focus, reduced-motion support, responsive layouts, and explicit memory controls.
- A connected browser was unavailable for the final screenshot-level visual pass. This is recorded as a verification limitation rather than represented as completed; functional public UI and lifecycle checks passed over the live internet surface.
