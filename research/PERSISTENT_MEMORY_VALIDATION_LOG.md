# Persistent Memory Validation Log

## Date

2026-03-14

## Scope

Validation for the public portal curriculum-memory upgrade in `browser/portal_server.py` and the related public UI/prompt changes.

## Checks That Passed

### Static / Parse Checks

Executed successfully:
- `python -m py_compile browser/portal_server.py`
- `python -m py_compile browser/render.py`
- `node --check browser/portal/static/portal.js`

### Public Portal Smoke (No Model Load)

Environment:
- `ATHENA_WEB_LOAD_MODEL=0`
- `ATHENA_AUTH_REQUIRED=0`

Checks:
- `GET /healthz` returned `ok=True`
- `GET /AEN5` returned `200`
- page rendered:
  - `Welcome to the portal`
  - `Athena by AEN`
  - `Curriculum memory`
- `GET /AEN5/api/config` returned `200`
- config returned:
  - `assistant_label = Athena by AEN`
  - `memory_mode = recent+summary+session+recall`
  - `recent_turn_pair_limit = 8`
  - `memory_schema_version = 2.0`
  - `curriculum_context_supported = true`

### Synthetic Curriculum-Memory Smoke

Synthetic user:
- `curriculum-upgrade-smoke-2@portal.local`

Constructed data:
- 10 completed turns written into NDJSON session logs
- durable summary written into `memory/summary.json`
- short-lived session memory written into `memory/session.json`
- curriculum context written into `memory/curriculum_context.json`

Checks:
- `load_recent_messages(...)` returned `16` messages = `8` turn pairs
- `relevant_recall_turns(...)` returned relevant older turn pairs
- `build_system_prompt_override(...)` contained:
  - curriculum context block
  - educator role signal
  - current course `MTH 025 College Algebra`
  - misconception/support signals
  - recommended assessment
- output contract normalized educator-course drift and low-level course aliases back to `MTH 025`

Synthetic validation user was moved into archive after the smoke:
- `archive/shared_archives/portal_validation_2026-03/`

### Live Public Model Validation (App Interpreter)

Validation used the same interpreter the browser launcher uses:
- `D:\AthenaPlayground\.venv\Scripts\python.exe`

#### Educator Artifact Prompt

Prompt:
- `I teach MTH 025. Draft a short lesson opener on factoring quadratics and include a 3-question exit ticket.`

Checks passed:
- response completed successfully
- `MTH 025` was preserved
- no alternate course drift survived in the final visible output
- an `Exit ticket` section was present in the final visible output

Observed issue during iteration:
- the raw model sometimes generalized the course label or produced malformed variants such as `MTH 025/025`

Mitigation now:
- explicit turn-context injection
- output-contract normalization for alternate course labels, low-level course ranges, generic placeholders, and duplicate malformed course mentions
- forced exit-ticket block when the prompt requires one and the model omits it

#### Student Tutoring Prompt

Prompt:
- `I am learning the chain rule. Teach me step by step, do not give the full answer immediately, and end with one quick check question.`

Checks passed:
- response completed successfully
- response stayed on the chain rule
- response used stepwise tutoring language
- response ended with a quick-check style question

## Earlier Failure Modes Addressed

### 1. Raw-History Truncation Pressure

Problem:
- replaying too much transcript history makes the context unstable and wastes tokens

Mitigation now:
- keep only the most recent `8` turn pairs live
- move older continuity into summary/session/recall layers

### 2. Malformed Summarizer JSON

Problem:
- memory summarizer occasionally emitted malformed pseudo-JSON

Mitigation now:
- lenient extraction fallback before normalization
- explicit stable schemas for summary/session memory files

### 3. Course-Context Drift in Educator Mode

Problem:
- educator prompts could drift into adjacent or fabricated course labels

Mitigation now:
- explicit per-turn course-code injection
- current-turn role/intent extraction
- post-generation curriculum-output contract

## Current Status

Public persistent memory is operational in a bounded layered form and now supports curriculum-aware tutoring behavior.

Current mode:
- `recent + summary + session + recall + curriculum`

This is a strong base for the next round of public memory work.
