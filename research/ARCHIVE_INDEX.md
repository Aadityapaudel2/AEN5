# Archive Index

The main cleanup archive root is:

- `archive/cleanup_2026-03/`

## Main Buckets

- `models/`
  - non-canonical tuned models moved out of the active surface

- `finetune/`
  - archived run folders and non-canonical finetune outputs

- `evaluation/`
  - unpublished dataset tree and legacy dataset material

- `runtime_state/`
  - archived local data state such as user logs, compare runs, and staged images

- `tools/`
  - secondary compare/smoke utilities removed from the root surface

- `logs/`
  - archived root and evaluator log output

- `apps/`
  - reserved bucket for any future app-surface archival

## Reading Rule

If a file or directory is needed for:

- runtime launch
- canonical model loading
- current training
- current evaluator use
- published testdata

it should not live only in the archive.

If it is historical, superseded, unpublished, or generated, the archive is the correct home.
