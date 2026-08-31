# Athena V5 Public Tutor: Continuation Implementation Prompt

Use this prompt for the next deep implementation session.

## Objective

Continue turning the public Athena V5 portal into one coherent, confident, evidence-tested tutoring system around Qwen3.5-4B base. The learner should experience a tutor that acts on available material immediately, teaches at the right depth, checks work independently, produces usable educator artifacts, remembers only what is governed and relevant, and never exposes private Athena continuity.

Do not commit, push, restart the published portal, alter the public tunnel, deploy, or publish without Aaditya's explicit approval in the active session.

## Ground truth at handoff

- Public inference model: Qwen3.5-4B base through vLLM.
- Current local runtime: 128000 configured context tokens, language-model-only, thinking disabled.
- Public prompt profile: public_athena_tutor_v1 version 2.0, strict and hashed.
- Shared prompt compiler: desktop_engine/prompt_config.py.
- Public prompt startup: fail closed; no generic one-line fallback.
- Turn router: greeting, broad help, guided tutoring, study plan, solution check, educator artifact, direct help, and image/document inspection.
- Public learner memory: recent + session + durable summary + lexical recall + curriculum.
- Memory precedence and untrusted-data boundaries are implemented.
- New Thread preserves durable learner preferences.
- Memory export and confirmed Forget learner memory controls are implemented.
- YaRN 1.01M profile exists but is dormant, guarded, and unsuitable for routine use on the current 16 GB workstation.
- No public process or model runtime was restarted by the August 30 implementation pass.

## First commands

Run these from the AthenaV5 repository root using the parent workspace's `.venv` Python interpreter:

~~~powershell
git status --short
& ..\.venv\Scripts\python.exe -B -m unittest discover -s browser\tests -v
node --check browser\portal\static\portal.js
$tokens=$null; $errors=$null
[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\run_vllm.ps1),[ref]$tokens,[ref]$errors) | Out-Null
$errors
& ..\.venv\Scripts\python.exe -B browser\public_runtime_preflight.py
& ..\.venv\Scripts\python.exe -B browser\tutor_behavior_eval.py
~~~

If an existing test fails, diagnose it before adding features. Preserve unrelated worktree changes.

## Workstream A: Tutor-behavior evaluation

- [ ] Expand browser/tutor_behavior_eval.py from 7 probes to at least 24.
- [ ] Cover: pure greeting, broad subject help, vague study request, direct explanation, guided hint, full solution request, correct work, incorrect work, internally contradictory model output, misconception diagnosis, educator opener, exit ticket, worksheet, answer key, rubric, differentiation, attached image instruction, unreadable image, returning-session continuation, memory conflict, prompt injection inside recalled text, academic-integrity constraint, unsupported high-stakes request, and exact course/date preservation.
- [ ] Store both raw model output and post-controller output in evaluation results.
- [ ] Separate model-quality failures from controller-contract failures.
- [ ] Add a rubric with five scored dimensions: correctness, initiative, pedagogical value, role fit, and mechanical compliance.
- [ ] Require at least 90 percent probe pass rate before release consideration.
- [ ] Require 100 percent on correctness-critical arithmetic checks, memory-injection boundaries, private/public boundaries, and educator no-blocking behavior.
- [ ] Add repeat mode for stochastic stability and report pass rate per probe across at least three runs.
- [ ] Do not game tests with brittle phrase matching when a structural predicate can be used.

## Workstream B: Controller quality

- [ ] Audit every route in _extract_turn_context against the expanded probe set.
- [ ] Add explicit direct-solution versus guided-hint discrimination.
- [ ] Add document/image routing that uses image presence and visible user language without guessing content.
- [ ] Replace any remaining subject-specific hardcoded fallback with domain-neutral or extracted-topic behavior.
- [ ] Generalize the contradictory-verdict repair so it fixes only high-confidence contradictions and never flips a consistent verdict.
- [ ] Add a response-level check for multi-question intake before useful work on broad-help and study routes.
- [ ] Keep controller transformations observable in local evaluation artifacts without exposing them in public status.
- [ ] Add regression tests for each transformation.

## Workstream C: Pedagogy

- [ ] Define concise response skeletons for Explain, Coach, Check work, Build practice, and Plan instruction.
- [ ] Ensure Explain connects example to concept and transfer.
- [ ] Ensure Coach reveals one hint at a time and preserves productive struggle.
- [ ] Ensure Check work gives the verdict on the learner's submission, earliest error, repair, and independent verification.
- [ ] Ensure Build practice progresses in difficulty and includes success criteria or an answer key when appropriate.
- [ ] Ensure Plan instruction separates student-facing material from teacher notes and identifies a misconception plus an evidence-of-learning check.
- [ ] Add learner-level calibration probes for elementary, secondary, undergraduate, and adult-returning learners.
- [ ] Add a no-shame language test: correct errors directly, praise specific reasoning, never belittle the learner.

## Workstream D: Memory

- [ ] Test a full lifecycle: first turn, recent history, session refresh, durable-summary refresh, older-turn recall, New Thread, export, Forget learner memory.
- [ ] Verify summary source_turn_count resets correctly after New Thread.
- [ ] Verify Forget learner memory cannot be bypassed without the exact confirmation.
- [ ] Verify exports contain no filesystem paths, credentials, tokens, or other users' data.
- [ ] Add maximum-size controls for export payloads and recalled excerpts.
- [ ] Add adversarial memory text that says to ignore policy; prove it remains inert reference data.
- [ ] Evaluate whether lexical recall needs a cached index before introducing embeddings.
- [ ] If adding embeddings, keep a dependency-light fallback and document deletion/index rebuild semantics.
- [ ] Never copy private Athena memory into the public learner store.

## Workstream E: Interface and accessibility

- [ ] Start the candidate locally only when authorized; do not touch the published process.
- [ ] Inspect the authenticated empty state, starter actions, streaming state, error state, restored thread, New Thread state, export, and forget confirmation.
- [ ] Test desktop wide view, 1280px, tablet, and 390px mobile.
- [ ] Verify keyboard-only operation, visible focus, screen-reader labels, contrast, reduced motion, and textarea behavior.
- [ ] Ensure the Memory menu does not overflow or hide behind the composer.
- [ ] Ensure starter actions fill the composer without silently spending a guest prompt.
- [ ] Ensure no mojibake or stale institution-specific text appears.
- [ ] Capture screenshots only for local evidence; do not publish them automatically.

## Workstream F: Runtime and context profiles

- [ ] Keep native / 128000 as the default on the current workstation.
- [ ] Validate browser/config/context_profiles.json in tests and preflight.
- [ ] Add a launcher dry-run or command-preview mode so context-profile arguments can be inspected without starting or stopping vLLM.
- [ ] Confirm dry-run output never prints API keys.
- [ ] Confirm yarn_1010k cannot activate without AllowExperimentalUltraLongContext.
- [ ] Confirm hf-overrides reaches WSL with intact JSON quoting.
- [ ] Do not actually start the 1.01M profile on the current 16 GB GPU.
- [ ] Document expected KV-cache and hardware planning before any H100-class experiment.

## Workstream G: Security and privacy

- [ ] Threat-model prompt injection through user text, retrieved course excerpts, recalled assistant text, imported curriculum, image OCR, and exported/reimported memory.
- [ ] Confirm the current user message cannot cause the portal to reveal the system prompt, prompt path, backend URL, API key, log root, OAuth values, or another user's state.
- [ ] Add tests for path traversal on upload and export routes.
- [ ] Review CSRF posture for reset and memory deletion endpoints.
- [ ] Add cache-control and content-disposition headers for memory export if direct download replaces the current JSON response.
- [ ] Keep public status limited to prompt name, version, hash, and validation state.
- [ ] Re-run the stale/private marker scan across public templates, scripts, prompt, docs, and rendered pages.

## Workstream H: Release evidence

- [ ] Update PORTAL_RELEASE_READINESS_2026-08-30.md with the tutor pass as a new dated section; do not erase the earlier sanitization evidence.
- [ ] Record exact test counts and exact behavior-probe counts.
- [ ] Record what was not tested and why.
- [ ] Record the active model ID, prompt name/version/hash, configured context profile, and whether the portal/model process was restarted.
- [ ] Run git diff --check.
- [ ] Produce a scoped changed-file inventory.
- [ ] Separate release blockers from later enhancements.

## Definition of done

- [ ] All unit tests pass.
- [ ] JavaScript and PowerShell parse checks pass.
- [ ] Production preflight passes without exposing secrets.
- [ ] Expanded tutor behavior suite meets the threshold.
- [ ] Every correctness-critical probe passes.
- [ ] Broad help and vague study prompts perform useful work before asking at most one focused clarification.
- [ ] Educator artifact prompts return usable drafts without blocking questions.
- [ ] Check-work responses are internally consistent.
- [ ] Memory precedence, export, New Thread, and Forget semantics pass lifecycle tests.
- [ ] Local visual and accessibility QA is complete or explicitly listed as unperformed.
- [ ] Public/private scan is clean.
- [ ] No commit, push, restart, deployment, tunnel change, or publication occurred without fresh approval.
- [ ] Final report links every material claim to a test, local artifact, or exact file.

## Final response format for the next session

Lead with the outcome. Then provide:

1. completed checklist count
2. exact test and behavior-eval results
3. release blockers, if any
4. files the user should review
5. explicit confirmation that no unauthorized commit, push, restart, deployment, or publication occurred

Do not claim exhaustive completion if a live account callback, local visual inspection, or public-domain verification was not actually performed.
