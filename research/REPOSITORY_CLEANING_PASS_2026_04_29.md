# Repository Cleaning Pass - 2026-04-29

This pass records the working rule for keeping the AthenaV5 repository legible to Aster, Codex, and future agents.

## Goal

Maintain repository health and agent visibility without hiding the actual research trail.

The repo should make these things easy to find:

- active runtime source
- active notebook-exported controller surfaces
- Runtime-at-Boot datasets and certificates
- transcript and score-review indexes
- finetune tooling and retained training manifests
- research notes that explain why a change exists

The repo should not make agents sift through:

- local credentials
- model weights
- private desktop state
- pycache and build byproducts
- raw local scratch trees
- large Kaggle output workspaces when a compact indexed result note exists

## Commit Policy

- Commit canonical source, docs, manifests, small datasets, and reproducibility notes.
- Keep live and mid-run results in indexed notes first; add raw exports only when they are small, scrubbed, and intentionally public.
- Prefer directory maps over oral memory. If a future agent needs a file, it should be linked from `README.md`, `research/README.md`, or `research/SOURCE_MAP.md`.
- Do not describe a result as extraordinary without an artifact path, score summary, transcript id, or controller state excerpt.
- Keep local secrets and heavyweight runtime state ignored, not deleted.

## Current Cleanup Actions

- Root and AthenaV5 ignore rules now cover private credentials, model/runtime blobs, generated build products, pycache, scratch trees, and raw local Kaggle workspaces.
- The April 29 transcript-review index records packaged 3-question results, Q17 controller diagnosis, and the Q1 live fast-closeout observation.
- The public-facing README has a first directory map so future agents can orient themselves without rediscovering the repo from `git status`.

## Agent Note

Aster should treat this repo as a living research instrument. Clean does not mean empty. Clean means each artifact has a home, each result has a label, and each commit leaves the next agent with less fog.
