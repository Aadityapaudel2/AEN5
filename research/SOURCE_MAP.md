# Research Source Map

This file maps the main research and planning documents already present in the repo.

Use it to decide where to extend an idea instead of creating duplicate notes.

## Canonical New Research Folder

- `research/README.md`
  - entry point for current research work

- `research/LINUX_H100_PROTOCOL_REPORT.md`
  - Linux/H100 migration and structured two-model protocol report

- `research/AIMO_RESEARCH_PROGRAM.md`
  - consolidated next-step research program

- `research/CLEANUP_CANONICALIZATION_REPORT.md`
  - report for the March 2026 cleanup/canonicalization pass

- `research/CANONICAL_REPO_LAYOUT.md`
  - compact definition of the retained active surfaces

- `research/ARCHIVE_INDEX.md`
  - index of the main archive buckets

- `research/CODEBASE_HEALTH_REPORT.md`
  - retained-code inventory and repo hygiene report for the March 2026 health-cleanup pass

- `research/PUBLIC_MEMORY_ARCHITECTURE_NOTES.md`
  - layered public memory and curriculum-controller design note for the browser portal

- `research/PERSISTENT_MEMORY_VALIDATION_LOG.md`
  - implementation and validation log for the public persistent-memory rollout

- `research/CURRICULUM_EMBEDDING_BLUEPRINT.md`
  - V4-to-V5 translation note for turning the public portal into a university-scale learning partner

- `research/EXCLUSIVE_DESKTOP_TEXT_ATTACHMENTS.md`
  - private-only note for the exclusive desktop `.txt` attachment path and inline prompt injection model

- `research/PRIVATE_QWEN4B_INFERENCE_TUNING.md`
  - private-only note for the current working anti-repeat/coherence inference profile on exclusive Athena

- `research/PUBLIC_PORTAL_RELEASE_SURFACE.md`
  - note for the public landing redesign, separate legal pages, and AEN/Athena/SWARM release framing

## Source Notes

- [codexcontextlinux.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/codexcontextlinux.txt)
  - long Linux session narrative
  - includes migration, UI stabilization, evaluator upgrades, and the shift toward a bounded solver/verifier protocol

- [research.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/research.txt)
  - deterministic solver thesis arguing against premature swarm scaling

- [agentic_project_planning.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/agentic_project_planning.txt)
  - execution-biased build order after the desktop-first rebuild

- [aimo_win_plan.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/aimo_win_plan.txt)
  - strongest direct AIMO strategy memo

- [report.md](/d:/AthenaPlayground/AthenaV5/research/source_notes/report.md)
  - historical repository snapshot

- [codexcontext.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/codexcontext.txt)
  - earlier Windows/local context log

- [coherence_ablation_set.md](/d:/AthenaPlayground/AthenaV5/research/source_notes/coherence_ablation_set.md)
  - compact manual evaluation set for identity/coherence checks

- [coherence_ablation_set.yaml](/d:/AthenaPlayground/AthenaV5/research/source_notes/coherence_ablation_set.yaml)
  - prompt-set source paired with the coherence ablation note

- [tool_call_math_probe.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/tool_call_math_probe.txt)
  - narrow tool-discipline probe

- [system.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/system.txt)
  - older structured system/persona specification

- [TRANSCRIPT.txt](/d:/AthenaPlayground/AthenaV5/research/source_notes/TRANSCRIPT.txt)
  - Linux single-model transcript from the Qwen3.5-9B phase

## Runtime / Evaluator Notes

- [desktop_engine/agentic/README.md](/d:/AthenaPlayground/AthenaV5/desktop_engine/agentic/README.md)
  - operational note for the headless solver+verifier math loop

- [apps/two_model_dialogue_evaluator/README.md](/d:/AthenaPlayground/AthenaV5/apps/two_model_dialogue_evaluator/README.md)
  - active standalone evaluator app context

## Training / Finetune Reports

- [CANONICAL_RUN_REPORT.md](/d:/AthenaPlayground/AthenaV5/exclusive/AthenaV1/CANONICAL_RUN_REPORT.md)
  - verifiable report for the current canonical 4B SFT baseline

- [Finetune/README.md](/d:/AthenaPlayground/AthenaV5/Finetune/README.md)
  - trainer/pipeline usage notes

## Practical Reading Order

If the task is architectural:

1. `handoff.md`
2. `research/source_notes/agentic_project_planning.txt`
3. `research/source_notes/research.txt`

If the task is AIMO strategy:

1. `research/source_notes/aimo_win_plan.txt`
2. `research/AIMO_RESEARCH_PROGRAM.md`
3. `desktop_engine/agentic/README.md`

If the task is Linux migration or H100 reasoning history:

1. `research/source_notes/codexcontextlinux.txt`
2. `research/LINUX_H100_PROTOCOL_REPORT.md`

If the task is future tuning comparison:

1. `models/tuned/.../CANONICAL_RUN_REPORT.md`
2. `Finetune/README.md`

If the task is public curriculum tutoring:

1. `research/CURRICULUM_EMBEDDING_BLUEPRINT.md`
2. `research/PUBLIC_MEMORY_ARCHITECTURE_NOTES.md`
3. `research/PERSISTENT_MEMORY_VALIDATION_LOG.md`

## Maintenance Rule

When adding a new research note:
- put the new file in `research/`
- add one line here describing what it is for
- if it supersedes an older note, say so explicitly

- `research/AIMO3_SUBMISSION_PROTOCOL.md` 
  - repo-local summary of Kaggle AIMO3 headless submission constraints, answer format, and build order
- `research/AIMO3_SMOKE_LOG.md`
  - first terminal-visible 2B and 4B smoke results for the headless Kaggle submission surface