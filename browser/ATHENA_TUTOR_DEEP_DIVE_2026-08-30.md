# Athena V5 Public Tutor Deep-Dive

Date: 2026-08-30
Scope: local working tree only
Runtime target: Qwen3.5-4B base through vLLM

## Outcome

Athena now has one explicit public tutoring contract spanning prompt compilation, turn routing, learner-memory boundaries, controller enforcement, interface boot state, runtime metadata, and behavior evaluation. The implementation is locally validated and ready for human review. It has not been committed, pushed, restarted, deployed, tunneled, or published.

The already-running public portal process was intentionally left untouched. Because the portal loads its prompt and Python code at process start, the live web process may continue serving its prior behavior until an explicitly authorized restart. The live behavior evaluation below called the existing Qwen3.5-4B model endpoint with the new prompt and controller code from a fresh local evaluator process; it is evidence for the candidate, not a claim that the published portal has already changed.

## Completed checklist

- [x] Traced the public boot path from configuration through prompt assembly, memory overlay, turn routing, model request, controller normalization, and rendered response.
- [x] Replaced duplicate prompt loaders with one shared, strict prompt compiler.
- [x] Added a named, versioned, hashed public tutor profile that fails closed when required sections are missing or unsafe markers appear.
- [x] Defined boot confidence, act-before-asking, tutoring, educator, memory, mathematics, integrity, formatting, and default-mode doctrine.
- [x] Added explicit routes for greeting, broad help, study planning, guided tutoring, solution checking, educator artifacts, direct help, and visible image/document work.
- [x] Prevented generic intake behavior when Athena can make a useful first move.
- [x] Added verdict-consistency repair and independent-verification rules for check-my-work turns.
- [x] Prevented Athena from inventing an unseen subtraction, division, sign, or arithmetic error when the learner supplied only a final answer.
- [x] Framed recalled turns and summaries as untrusted reference data rather than instructions.
- [x] Established memory precedence: current user, verified identity/course facts, current session, durable learner profile, retrieved course context, recalled conversation.
- [x] Removed email and authentication source from the model-facing memory overlay.
- [x] Made New Thread clear recent/session continuity while preserving durable learner preferences.
- [x] Added user-visible memory status, JSON export, and confirmed Forget learner memory controls.
- [x] Added a confident authenticated boot card and four starter actions without silently spending a guest prompt.
- [x] Added prompt identity metadata to health/config output without exposing prompt text or filesystem paths.
- [x] Added native and guarded YaRN context profiles with the upstream Qwen3.5 override represented once in configuration.
- [x] Kept native 128000 as the practical default and required an explicit experimental flag for YaRN 1010000.
- [x] Added unit, contract, routing, memory, shell, launcher, and live tutor-behavior checks.
- [x] Wrote a bounded next-session implementation prompt with measurable release gates.
- [x] Preserved all unrelated working-tree changes.

## Candidate architecture

### One prompt shell

`desktop_engine/prompt_config.py` is now the shared loader for desktop and portal runtimes. It compiles sections in a deterministic order, validates the public profile strictly, computes its SHA-256 digest, and exposes only safe identity metadata. The public portal no longer has a silent one-line fallback persona.

The candidate prompt identity is:

- name: `public_athena_tutor_v1`
- version: `2.0`
- SHA-256: `5946a3bd187e87a6c7ac6b63ae97992083898e5833f382fc8508d5005022b3c3`
- strict validation: true

### Tutor routing and controller boundaries

Every model turn receives a compact current-turn route with an explicit clarification budget. Educator artifacts must be drafted before questions. Study requests begin with a concrete 25-minute cycle. Visible attachments are inspected directly. Check-work turns must adjudicate the learner's submission, compute independently, and distinguish observable work from guessed intermediate work.

Controller transformations remain narrow and tested: exact course-code preservation, domain-neutral exit-ticket fallback, contradictory-verdict repair, zero-question enforcement for solution adjudication, and removal of unsupported intermediate-error attribution.

### Governed learner memory

Recent turns, session focus, durable summaries, lexical older-turn recall, authenticated profile facts, and curriculum context remain separate layers. Summarization receives framed JSON marked as untrusted turn data. Prior assistant claims do not become user facts. New Thread and Forget now have deliberately different semantics, and users can inspect or remove their learner continuity without receiving internal paths, credentials, or hidden prompt data.

### Context profiles

The launcher reads `browser/config/context_profiles.json`:

- `native`: 128000, no RoPE override, default
- `yarn_1010k`: 1010000, exact Qwen3.5 YaRN-shaped override, experimental opt-in required

YaRN extends inference context; it is not Athena's memory system. The 1.01M profile was not started on the current 16 GB workstation.

## Validation evidence

### Automated regression

- Python unit and contract suite: **72/72 passed**
- Live tutor-behavior rubric: **7/7 passed**
- Stochastic greeting repetition after budget enforcement: **3/3 passed**
- JavaScript syntax: passed (`node --check`)
- PowerShell launcher AST parse: passed
- Modified Python entrypoint in-memory compilation: passed
- Scoped `git diff --check`: passed
- Public-template/private-marker scan: no banned public-surface markers found

### Runtime preflight

The candidate preflight passed with:

- endpoint reachable: true
- served model: `Qwen3.5-4B`
- advertised sign-in routes: Google, GitHub, guest
- dormant institution auto-attach: false
- prompt strict validation: true
- context profiles: native, yarn_1010k
- public identity files sanitized: true

The only warning was expected: native Windows cannot import vLLM because the model service runs in WSL/Linux.

### Live behavior probes

The seven candidate probes covered:

1. confident greeting and tutoring choices
2. broad mathematics help without an intake questionnaire
3. vague study request with an immediate study cycle
4. incorrect solution adjudication and independent verification
5. guided factoring with a calibrated hint
6. classroom-ready educator exit ticket
7. factual Athena/AEN identity and tutor capabilities

## Material files

### Runtime and policy

- `desktop_engine/prompt_config.py`
- `desktop_engine/runtime.py`
- `browser/config/system_prompt.json`
- `browser/portal_server.py`
- `browser/public_runtime_preflight.py`

### Learner interface

- `browser/portal/templates/index.html`
- `browser/portal/static/portal.css`
- `browser/portal/static/portal.js`
- `browser/portal/README.md`

### Context configuration

- `browser/config/context_profiles.json`
- `run_vllm.ps1`
- `research/QWEN35_CONTEXT_PROFILES.md`

### Tests and handoff

- `browser/tests/test_public_tutor_contract.py`
- `browser/tests/test_portal_pilot_roles.py`
- `browser/tutor_behavior_eval.py`
- `browser/ATHENA_TUTOR_IMPLEMENTATION_PROMPT_2026-08-31.md`

## Deliberately unperformed

- [ ] No commit or push.
- [ ] No portal, vLLM, tunnel, service, or public host restart.
- [ ] No deployment or publication.
- [ ] No Google/GitHub live OAuth callback was exercised.
- [ ] No authenticated browser visual/accessibility pass was performed against a locally restarted candidate.
- [ ] No YaRN 1.01M inference launch or memory-pressure benchmark was performed.
- [ ] The live behavior evaluator has seven high-value probes, not yet the planned 24-plus multi-run release suite.
- [ ] Full CSRF, upload traversal, and adversarial memory-injection threat-model work remains for the next pass.

These are not hidden omissions. They are the explicit next gates before any claim that the candidate has been exercised end-to-end as a deployed public release.

## Next-session objective

Use `ATHENA_TUTOR_IMPLEMENTATION_PROMPT_2026-08-31.md`. Its primary goals are to expand the behavior suite to at least 24 probes with repeat stability, test the complete memory lifecycle and adversarial boundaries, add launcher dry-run evidence for context profiles, complete authenticated visual/accessibility QA, finish the security review, and append release evidence without publishing prematurely.
