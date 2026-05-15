# Research

This folder is the working research base for the next AIMO-oriented phase.

It is intentionally separate from product code and training artifacts. The goal is to keep:

- current research direction
- experiment reports
- source maps to older notes
- next-step hypotheses

in one place that can keep growing without mixing with runtime files.

## Current Documents

- `AEN_TRANSCRIPT_REVIEW_INDEX_2026_04_29.md`
  - transcript-review index for the April 29 AEN/Athena runs
  - records packaged 3-question results, Q17 closeout diagnosis, a labeled mid-run Q1 observation, and the current strict-early-closeout guidance prompt

- `LINUX_H100_PROTOCOL_REPORT.md`
  - consolidated report from the Linux/H100 migration notes in `codexcontextlinux.txt`
  - focuses on the structured two-model math protocol, Linux stabilization, and why protocol quality became central

- `AIMO_RESEARCH_PROGRAM.md`
  - consolidated current thesis for AIMO work
  - pulls together the deterministic-engine direction, verifier-first reasoning, and the fixed-budget small-swarm plan

- `AIMOAEN11_RUNTIME_STABILIZATION_2026_04_02.md`
  - runtime memo for the AEN11 Kaggle notebook after the vLLM pivot
  - records the canonical fast-path stack, direct-runtime load success, probe failures, and the current coherence strategy

- `AIMOAEN11_TRANSFORMERS_SERVE_POSTMORTEM_AND_SGLANG_PIVOT_2026_04_03.md`
  - postmortem for the failed `transformers serve` branch in AEN11
  - records the mixed-backend failure mode and the rationale for the next SGLang pivot

- `SOURCE_MAP.md`
  - curated map of prior research/planning notes already present in the repo
  - use this before adding new files so new work lands in the right place

- `EXCLUSIVE_DESKTOP_TEXT_ATTACHMENTS.md`
  - private desktop note for local `.txt` file attachments and prompt injection behavior

- `PRIVATE_QWEN4B_INFERENCE_TUNING.md`
  - private inference note for the working anti-repeat/coherence profile on the exclusive Qwen 3.5 4B route

- `PUBLIC_PORTAL_RELEASE_SURFACE.md`
  - release note for the public portal landing redesign, legal-page split, and AEN/Athena/SWARM positioning

- `PUBLIC_VLLM_BOOT_AND_STREAM_FIX_2026_03_18.md`
  - runtime memo for the WSL-backed public vLLM launch path
  - covers the first-token stall root cause, Qwen thinking disablement, token-budget fix, and the final operator contract

- `EXCLUSIVE_VLLM_PARITY_2026_03_18.md`
  - private runtime memo for the exclusive Athena desktop on the shared vLLM serving path
  - covers launcher ownership, managed model matching, the one-sidecar/one-model operator contract, and the final multimodal image-upload follow-through on private vLLM

- `PRIVATE_PERSISTENT_MEMORY_ARCHITECTURE_2026_03_19.md`
  - private desktop memory note for local-only persistent continuity, episodic recall, reset controls, and logs-vs-memory semantics

- `AIMO3_SUBMISSION_PROTOCOL.md`
  - local protocol note for Kaggle AIMO3 submission constraints, headless smoke testing, and packaging order

- `AIMO3_SMOKE_LOG.md`
  - first headless CLI validation log for 2B baseline and 4B solver-verifier smoke runs

- `AIMO3_VERIFIER_CONTRACT_2026_03_20.md`
  - verifier-output contract and serving constraints for the canonical Qwen9B plus Phi15B text-only Kaggle runtime

- `AIMO3_PEER_DIALOGUE_NOTEBOOK_2026_03_22.md`
  - notebook-surface note for the Athena/Sentinel peer-dialogue refactor in AEN5
  - explains why the staged solver/verifier transcript was dropped in favor of hidden controller logic and clean visible dialogue

- `AIMO3_QWEN9B_PHI15B_FLOWCHART_2026_03_20.md`
  - working algorithm note for the bounded Qwen9B plus Phi15B solver-verifier flow, including the text-only verifier serving assumption

- `AIMO3_QWEN9B_PHI15B_PUBLICATION_FLOWCHART_2026_03_20.md`
  - publication-oriented summary of the same bounded Qwen9B plus Phi15B algorithm and its text-only verifier serving path

- `MIAMIOH_GOOGLE_PILOT_ARCHITECTURE.md`
  - current architecture memo for the MiamiOH Google pilot
  - covers identity, course-bundle retrieval, instructor-role resolution, and the remaining live ship gate

## Operating Principles

- Treat the shared engine as the canonical execution layer.
- Treat the browser surface as the public-facing product path.
- Treat the exclusive desktop as the private-only product path.
- Keep research claims tied to explicit artifacts, runs, or protocol changes.
- Label mid-run observations separately from packaged exports.
- Prefer deterministic, tool-visible, replayable reasoning over larger but less disciplined systems.
- Do not let future notes drift into a second independent architecture story.
- Keep public config under `browser/config/` and shared tool config under `desktop_engine/config/`.

## Suggested Use

When new research happens, add one of:

1. a report for a completed experiment
2. a direction memo for a new architecture decision
3. an ablation note with exact inputs, outputs, and verdict

If the note depends on an older document elsewhere in the repo, add that linkage to `SOURCE_MAP.md`.
