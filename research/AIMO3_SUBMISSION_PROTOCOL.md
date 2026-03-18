# AIMO3 Submission Protocol

## Purpose

This note converts the current AIMO3 submission references into repo-local build rules.

## Hard Constraints

- Competition submission notebooks are headless.
- Internet access is disabled during final submission reruns.
- Direct `pip install` inside the final submission notebook is not the reliable path.
- Heavy dependencies should be preinstalled by a separate utility notebook into `/kaggle/working` and attached as an input.
- The inference surface is a Kaggle-provided `AIMO3InferenceServer` with a `predict(...)` function.
- The returned answer must be a single integer in the range `0..99999`.

## Implications For This Repo

- Local desktop and portal surfaces are not the submission surface.
- The canonical submission work should stay in `desktop_engine/agentic/`.
- We need a terminal-visible headless smoke path before notebook packaging, because notebook submission failures are too slow to debug blind.
- Local answer normalization must default to AIMO3-style plain integers instead of older mod-1000 padded formatting.

## Current Repo Surfaces

- Submission CSV builder: `desktop_engine/agentic/kaggle_entry.py`
- Terminal smoke runner: `desktop_engine/agentic/kaggle_smoke.py`
- PowerShell wrappers:
  - `run_kaggle_submission.ps1`
  - `run_kaggle_smoke.ps1`

## Recommended Build Order

1. Prove 4B can answer small headless CLI smokes coherently.
2. Compare 2B, 4B, and 9B on a fixed local smoke pack.
3. If 9B is materially better, move heavy submission experiments to H100.
4. Package the chosen model and dependencies for Kaggle utility-notebook use.
5. Only then build the final Kaggle inference notebook.

## Immediate Open Questions

- Whether the best first pass is deterministic baseline or a bounded solver-verifier loop.
- Whether 9B is worth the packaging/runtime cost on Kaggle versus 4B.
- Which dependency stack is strictly required if we move to a Kaggle utility notebook.
- Whether the final notebook should run one model or a tightly bounded role protocol on one shared runtime.
