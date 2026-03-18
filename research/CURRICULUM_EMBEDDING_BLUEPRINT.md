# Curriculum Embedding Blueprint

## Purpose

This note translates the older AthenaV4 chapter into the current AthenaV5 public portal roadmap.

The goal is not to reproduce V4 literally. The goal is to carry forward the parts that matter for large-scale university tutoring:
- patient teaching-assistant behavior
- durable learner memory
- curriculum alignment
- educator-facing artifact generation
- future LMS and grade-integration hooks

## Source Frame

Primary local design source:
- `D:\V4 Chapter\main.tex`
- `D:\V4 Chapter\pedagogy.tex`
- `D:\V4 Chapter\design.tex`
- `D:\V4 Chapteruture.tex`

## V4 Commitments -> V5 Public Portal

### 1. Worked reasoning over final answers

V4 target:
- behave less like an answer key and more like a patient teaching assistant
- prefer plan -> steps -> concept invariant
- hint ladder before full solution when appropriate

V5 implementation:
- public system prompt now explicitly prefers guided explanation, staged reasoning, worked examples, and hint-ladder behavior
- current-turn intent detection distinguishes guided tutoring from educator artifact generation
- student-facing prompts are steered toward scaffolding and a brief comprehension check

Remaining gap:
- explicit per-course homework-policy controls are still file-based rather than instructor-managed in UI

### 2. Adaptive scaffolding and diagnostic feedback

V4 target:
- diagnose root causes and avoid repeating the same explanation style blindly

V5 implementation:
- durable learner profile stores `teaching_preferences`, `misconceptions`, `support_needs`, and `active_subjects`
- session memory stores the active objective, open loops, and next best action
- recall layer can bring back earlier misconceptions or user preferences when relevant

Remaining gap:
- no explicit misconception classifier yet
- pedagogical quality is still prompt/controller-driven, not evaluator-scored turn by turn

### 3. Formative assessment as first-class support

V4 target:
- generate micro-quizzes and short practice aligned to local curriculum

V5 implementation:
- educator prompts now preserve explicit course context
- session memory includes `recommended_assessment`
- output contract ensures exit tickets or quick-check questions remain present when requested

Remaining gap:
- there is no dedicated assessment generator module yet
- item difficulty and progression are not yet controlled by a course map

### 4. Persistent learning memory

V4 target:
- structured profile, not raw transcript replay
- write / read / merge / forget

V5 implementation:
- recent-turn window
- durable `summary.json`
- short-lived `session.json`
- query-aware recall over NDJSON logs
- optional `curriculum_context.json`

Remaining gap:
- no user-facing memory reset/export controls yet
- no embedding-based retrieval yet

### 5. Prompt architecture as policy

V4 target:
- system prompt + course prompt + retrieved profile context

V5 implementation:
- public system prompt
- current-turn course/role/intent injection
- retrieved learner/session/curriculum memory
- future curriculum hook file for LMS/admin provisioning

Remaining gap:
- no instructor dashboard yet for editing course policy directly

### 6. LMS and grade integration

V4 target:
- Canvas/LMS ingestion
- deterministic grade simulation

V5 implementation:
- architecture now has a clean insertion point: `curriculum_context.json`
- privacy/terms copy already anticipates institutional deployment

Remaining gap:
- LMS ingestion is not built yet
- grade simulation is not wired yet

## External Research Alignment

Useful public references for the next stage:
- LangGraph memory docs
  - https://docs.langchain.com/oss/python/langgraph/memory
- Mem0 memory docs
  - https://docs.mem0.ai/components/memory
- Generative Agents
  - https://arxiv.org/abs/2304.03442
- MemGPT
  - https://arxiv.org/abs/2310.08560
- BEA 2025 tutor-assessment findings
  - https://aclanthology.org/2025.bea-1.77/
- Educator perceptions of LLM tutors
  - https://aclanthology.org/2025.bea-1.28/
- Alignment drift in interactive tutoring
  - https://aclanthology.org/2025.bea-1.6/

## What Is Already Strong Enough for Real Pilot Use

The current public AthenaV5 portal is already credible for:
- warm public-facing tutoring
- educator-facing quick artifacts such as lesson openers and exit tickets
- bounded continuity across return visits
- persistent learner memory without replaying full history
- curriculum-aware prompting when course context is given explicitly

## What Still Needs to Exist Before Global Curriculum Rollout

1. LMS/admin-side provisioning into `curriculum_context.json`
2. Memory controls for export/reset/delete per user
3. Deterministic grade simulator separated from the language model
4. Pedagogical quality evaluator for mistake identification, guidance, and actionability
5. Instructor-side course-policy editing surface
6. Embedding-based recall or cached retrieval for longer histories

## Deployment View

The clean architectural split now looks like this:
- policy: public system prompt + terms/privacy stance
- controller: recent memory + learner profile + session memory + recall + curriculum hook
- model: public Athena by AEN inference backend
- future integrations: LMS ingestion, grade calculator, pedagogy evaluator

That is the right direction for turning AthenaV5 into a university-scale learning partner rather than a generic chat surface.
