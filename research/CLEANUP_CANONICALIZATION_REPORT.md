# Cleanup Canonicalization Report

## Purpose

This report records the March 2026 cleanup pass that reduced the repo surface to the active runtime, training, evaluator, dataset, and research paths.

## What Stayed Active

- `desktop_engine/`
- `browser/`
- `apps/two_model_dialogue_evaluator/`
- `Finetune/`
- `models/`
- `research/`
- `evaluation/`
- root launchers for desktop, browser, and math loop workflows

## Canonical Model State

- Active private tuned model:
  - `exclusive/AthenaV1` (fallback `models/tuned/AthenaV1`)
- Active base models:
  - `models/Qwen3.5-2B`
  - `models/Qwen3.5-4B`
  - `models/Qwen3.5-9B`

## What Was Archived

- older tuned models and adapter outputs
- non-canonical finetune run folders
- unpublished dataset tree
- root-level historical notes
- root-level secondary compare/smoke tooling
- generated runtime logs and archived user/runtime state

Primary archive root:

- `archive/cleanup_2026-03/`

## Archive Rule

The health-cleanup pass treated removal as archival movement. Historical, secondary, and duplicated surfaces were moved into explicit archive buckets instead of being left on the active path.

## Important Path Repairs

- public browser config was moved under `browser/config/`
- shared tool-behavior config was moved under `desktop_engine/config/`
- coherence ablation file paths were moved from the root into `research/source_notes/`
- `athena_paths.py` was updated so those helper paths still resolve
- evaluation dataset references were normalized under `evaluation/testdata/`

## Why This Matters

Before cleanup, the repo mixed:

- active runtime code
- historical code
- local generated state
- staging outputs
- research notes
- unpublished data archives

After cleanup, the repo is organized around a smaller active surface, while preserving history inside explicit archive buckets and preserving research lineage inside `research/`.
