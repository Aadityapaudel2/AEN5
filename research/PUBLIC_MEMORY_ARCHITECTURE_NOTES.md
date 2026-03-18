# Public Memory Architecture Notes

## Summary

The public portal now uses a layered curriculum-memory design instead of replaying the full NDJSON conversation log on every prompt.

Active memory mode:
- `recent + summary + session + recall + curriculum`

This is intentionally bounded:
- recent turns keep immediate continuity
- a durable learner profile captures long-lived preferences, misconceptions, goals, and course signals
- a short-lived session memory captures the active teaching task
- query-aware recall pulls only relevant older turn pairs from NDJSON history
- optional curriculum context lets the controller inject institution/course policy without retraining

## Why This Direction

Recent literature and framework guidance converges on the same pattern: useful assistant memory should be layered and selective, not a naive replay of the full transcript.

Influences:
- LangGraph memory guidance: short-term and long-term memory should be separated, then selectively injected into context.
  - https://docs.langchain.com/oss/python/langgraph/memory
- Mem0 memory model: user memory, session memory, and retrieval over stored memories are more scalable than monolithic chat replay.
  - https://docs.mem0.ai/components/memory
- Generative Agents: retrieval should balance relevance, recency, and importance rather than using raw chronological replay alone.
  - https://arxiv.org/abs/2304.03442
- MemGPT: long-lived memory should be externalized and managed explicitly rather than assumed to fit inside the active context window.
  - https://arxiv.org/abs/2310.08560
- Alignment drift findings in interactive tutoring suggest prompting alone is brittle over longer conversations, which strengthens the case for controller-side curriculum anchoring.
  - https://aclanthology.org/2025.bea-1.6/

## V4-to-V5 Translation

The older V4 chapter argued for:
- a tutor that behaves more like a patient teaching assistant than an answer key
- persistent learner profiles rather than raw transcript replay
- modular controller policy split across system policy, course policy, and retrieved student context
- eventual LMS and grade-calculation integration

The public AthenaV5 portal now implements the first half of that design directly in production-style code.

## Current Public Implementation

Files:
- `browser/portal_server.py`
- `browser/config/system_prompt.json`
- `browser/config/curriculum_context.template.json`
- `browser/portal/templates/index.html`
- `browser/portal/static/portal.js`

### 1. Recent Turn Window

The portal restores only the latest `8` completed user/assistant turn pairs into live chat history.

Why:
- preserves local continuity
- bounds context growth
- avoids the old failure mode where conversation quality degrades after a few prompts because raw history becomes too large

### 2. Durable Learner Profile

Per-user durable memory file:
- `data/users/<user>/memory/summary.json`

Current schema:
- `summary`
- `role`
- `preferences`
- `goals`
- `institution_context`
- `teaching_preferences`
- `active_subjects`
- `active_courses`
- `misconceptions`
- `support_needs`
- `assessment_timeline`
- `updated_at`
- `source_turn_count`

This profile is refreshed in bounded batches over older completed turns that have already fallen outside the recent live context.

### 3. Short-Lived Session Memory

Per-user short-lived session file:
- `data/users/<user>/memory/session.json`

Current schema:
- `current_focus`
- `current_objective`
- `teaching_preferences`
- `open_loops`
- `next_best_action`
- `recommended_assessment`
- `updated_at`
- `source_turn_count`

This layer is meant to hold the active instructional task rather than the long arc of the user profile.

### 4. Curriculum Context Hook

Optional per-user curriculum file:
- `data/users/<user>/memory/curriculum_context.json`

Normalized fields:
- `institution_name`
- `role_context`
- `current_course`
- `current_unit`
- `allowed_methods`
- `restricted_help`
- `assessment_style`
- `notes`
- `updated_at`

This is the bridge to later LMS or admin-side provisioning. For now it can be written manually or generated from future Canvas ingestion.

### 5. Query-Aware Recall Over NDJSON Logs

Older turns are retrieved from the existing NDJSON session logs using a lightweight local scoring pass.

Signals used:
- query/token overlap
- query phrase overlap
- recency weighting
- importance hints such as teaching, exams, courses, goals, and explicit preferences

Design choice:
- this is intentionally lexical and dependency-light for now
- it works directly over the existing NDJSON source of truth
- it avoids introducing a heavier vector/embedding dependency before portal behavior is stable

### 6. Turn-Scoped Curriculum Guardrails

The controller now extracts explicit current-turn context from the prompt:
- course codes
- user role (`student` or `educator` when detectable)
- intent (`guided_tutoring` or `educator_artifact` when detectable)

That context is injected into the system override before generation.

A post-generation contract then normalizes:
- wrong alternate course codes
- low-level course ranges like `MTH 000-025`
- generic course placeholders like `MTH 0xx`
- duplicate malformed mentions like `MTH 025/025`

It also ensures that when the prompt asks for an exit ticket or quick check, the public output ends with one.

### 7. Public Teaching Style

The public system prompt was upgraded so Athena by AEN now:
- sounds warmer without becoming private or companion-like
- adapts teaching depth to the apparent level and role of the user
- supports both student-facing tutoring and educator-facing classroom artifacts
- uses scaffolding, hint ladders, and worked examples when appropriate
- stays curriculum-aware and asks clarifying questions instead of inventing course context

### 8. Public Privacy / Terms Position

The public UI and copy now say:
- data is not sold
- bounded continuity memory may be stored to improve follow-up help
- conversation data may be used to improve models and services
- users can request a copy of their data by emailing `neohm@neohmlabs.com`

## What Failed Earlier

Earlier in the rollout, the summary updater occasionally emitted malformed pseudo-JSON instead of strict JSON. The portal now uses a lenient extraction fallback before normalization so the memory pipeline is harder to break from imperfect summarizer output.

A later failure mode was course-context drift in educator prompts, where the model sometimes invented or generalized course labels. The controller now counteracts that with explicit turn-context injection and a curriculum-output contract.

## Current Limits

This is materially better than raw transcript replay, but it is not the end state.

Current limits:
- episodic recall is lexical, not embedding-based
- summary/session refresh still depends on the model itself
- there is no explicit user memory-control UI yet
- curriculum context is file-based rather than LMS-synced
- pedagogical quality is improved by prompt/controller policy, but not yet scored by an automated pedagogy evaluator

## Next Upgrade Path

If the public portal remains stable, the next memory upgrades should be:
- embedding-based episodic recall over older NDJSON history
- cached recall indices so very long histories do not require repeated rescoring
- user-visible memory reset/export controls
- LMS or admin-side provisioning into `curriculum_context.json`
- evaluation hooks aligned with pedagogical-quality benchmarks such as the BEA 2025 tutor-assessment tracks
  - https://aclanthology.org/2025.bea-1.77/
  - https://aclanthology.org/2025.bea-1.79/
