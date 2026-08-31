# Athena identity and memory freshness hotfix

Date: 2026-08-31

Candidate: Athena public tutor profile v2.1

Status: release gates passed; public rollout pending

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

Pending commit, push, process launch, public smoke, authenticated guest lifecycle checks, and visual/accessibility inspection.
