# Kaggle Posting Checklist

## Basic Details

Title:

```text
Canon DSL v2.1 + Runtime-at-Boot: Auditable Math Data
```

Subtitle:

```text
A metadata-first pipeline for math problem distillation, boot-memory records, certification gates, and VoE-2026 evaluation.
```

Suggested slug:

```text
canon-dsl-runtimeatboot-auditable-math-data
```

## What To Paste First

Use `KAGGLE_CONTENT_READY_TO_PASTE.md` as the main Kaggle writeup body.

`BASIC_DETAILS_AND_KAGGLE_WRITEUP.md` remains an older planning draft.

Then, in the discussion thread where Philip and Sam asked questions, use `REVIEWER_RESPONSE_DRAFT.md` as the shorter reply.

Use `CANON_DSL_STUDY_SUMMARY.md` if you want to prepare a more detailed rebuttal-phase explanation of the Canon DSL paper.

## Tone Guardrails

- Be grateful and direct.
- Do not defend the raw `math_corpus.csv` as clean.
- Say clearly that the original CSV was a prototype artifact with processing issues.
- Emphasize that the cleaned contribution is Canon DSL v2.1 + Runtime-at-Boot + VoE-2026.
- Do not claim hidden benchmark performance for VoE-2026 because its key is public.
- Do not claim Runtime-at-Boot certification rows are safe to inject into solve prompts.

## Good One-Liner

```text
The early CSV exposed why metadata-first math data needs audit boundaries; the cleaned contribution is the Canon DSL / Runtime-at-Boot / VoE release path that grew from that failure.
```

## Links To Include

- Runtime-at-Boot dataset: https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot
- Canon DSL v2.1 paper: https://zenodo.org/records/19694800
- VoE-2026 benchmark: https://huggingface.co/datasets/Neohm/VoE-2026
- AEN revision ledger: https://github.com/Aadityapaudel2/AEN_Architecture/tree/main/revisions
