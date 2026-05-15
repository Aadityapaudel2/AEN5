# Basic Details

## Title

Canon DSL v2.1 + Runtime-at-Boot: Auditable Math Data

## Subtitle

A metadata-first pipeline for math problem distillation, boot-memory records, certification gates, and VoE-2026 evaluation.

## Suggested URL Slug

canon-dsl-runtimeatboot-auditable-math-data

## One-Sentence Summary

This project turns solved mathematical problems into auditable metadata records, derives reusable Runtime-at-Boot reasoning memory from those records, and releases VoE-2026 as a reproducible exact-answer benchmark.

# Kaggle Writeup Draft

## Canon DSL v2.1 + Runtime-at-Boot: Auditable Math Data

Thank you to the Math Corpus Prize hosts for the careful questions. They identify exactly the issue that made the original last-minute submission hard to present cleanly: the early `math_corpus.csv` artifact mixed useful generated mathematics with processing mistakes and uneven difficulty. I do not want the community to treat that raw CSV as the benchmark-grade form of the work.

The stronger contribution is the system that came after it: **Canon DSL v2.1**, a metadata-first schema for distilling mathematical problem families; **Runtime-at-Boot**, a role-specific dataset of answer-key-free reasoning memory plus separate certification gates; and **VoE-2026**, a small public-answer exact-integer benchmark released for reproducibility.

The goal is not only to make more synthetic math problems. The goal is to make mathematical data easier to inspect, mutate, verify, package, and reuse.

## What This Submission Is

This submission is a dataset and methodology package for auditable mathematical data generation.

It has three layers:

1. **Canon DSL v2.1:** a metadata schema for converting solved source problems into structured records.
2. **Runtime-at-Boot:** a reusable memory dataset derived from mathematical route discipline and answer contracts.
3. **VoE-2026:** a public-answer exact-integer benchmark for reproducible testing.

The central idea is that a mathematical problem should not only be stored as a prompt and an answer. It should also carry a machine-readable description of:

- the objects in the problem,
- the givens and unknowns,
- parameter domains,
- invariants and theorem roles,
- route structure,
- answer normalization,
- known failure modes,
- and computational or symbolic checks.

That metadata becomes the stable object. Rendered problems, training rows, boot-memory rows, certification probes, and evaluation tables are projections from that object.

## Important Correction About The Original Submitted CSV

The reviewers correctly identified issues in the original `math_corpus.csv`.

For example, in the `nt20` row, the problem text itself gives the correct final answer as `243`, but the separate `answer` column was exported as `3`. That is a processing/export issue, not a mathematical solution issue. It means any analysis that directly trusted the raw `answer` column of that early CSV would be affected.

Similarly, examples such as `alg_08` are intentionally standard seed problems. They are useful for schema sanity, answer normalization, and family construction, but they should not be advertised as hard benchmark items.

So my answer to the concern is direct:

**Yes, the raw early CSV had contamination and processing issues. I would not ask the community to use it as the cleaned benchmark-grade release.**

That is exactly why the later work moved toward a stricter metadata-first pipeline, explicit release manifests, public row audits, study/certification boundary files, and separate benchmark packaging.

## What Canon DSL v2.1 Adds

Canon DSL v2.1 is different from many model-distillation datasets because it distills the **mathematical problem**, not the model's response.

Instead of asking, "How do we compress a model's reasoning?", Canon DSL asks:

> What structure must be preserved so that a mathematical problem family can be generated, mutated, checked, and audited?

The schema is designed to record the family-level contract behind a problem:

- identity and lineage,
- mathematical domain,
- declared objects,
- givens,
- target quantity,
- invariants,
- theorem/tool roles,
- parameter domains,
- solved-instance snapshots,
- answer contract,
- verification checks,
- mutation notes,
- and release/provenance metadata.

This makes the dataset useful beyond ordinary supervised fine-tuning. A row can be used to generate variants, audit difficulty changes, create certification probes, test route adherence, or build problem-family curricula.

Paper: https://zenodo.org/records/19694800

## Runtime-at-Boot Dataset

The cleaned Runtime-at-Boot dataset is published on Kaggle:

https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot

The active v33 package contains **600 canonical boot rows**:

| role | study rows | certification rows |
| --- | ---: | ---: |
| Athena | 100 | 100 |
| Aria | 100 | 100 |
| Artemis | 100 | 100 |
| total | 300 | 300 |

The most important design choice is the boundary between study rows and certification rows.

**Study rows are answer-key-free.** They can be converted into runtime memory. They teach route discipline, answer-contract discipline, checking habits, and common failure modes.

**Certification rows are answer-bearing MCQ gates.** They are used only to prove that the boot memory loaded correctly. They should not be injected into ordinary solve prompts.

This split matters because it lets the dataset support two different use cases:

1. load reusable mathematical operating discipline before solving;
2. certify that this memory was actually loaded without leaking final answers into solve-time prompts.

That boundary is now explicit in the dataset manifests and sanitize reports.

## Why This Helps The Community

The dataset is useful because it gives researchers a way to study the hidden middle layer between a raw math problem and a model answer.

The community can use it to:

- build structured math problem-family corpora;
- generate same-family variants while preserving lineage;
- test whether route-level memory helps or hurts reasoning;
- build certification gates for prompt memory;
- study answer extraction and exact-integer answer contracts;
- compare answer-free boot memory against answer-bearing contamination;
- audit synthetic data quality before using it for training;
- and separate "the model solved it" from "the model recalled a key."

The last point is especially important. In later AEN experiments, Runtime-at-Boot showed both a failure mode and a success mode. A clean answer-free boot setup did not automatically improve AIME accuracy. A later answer-aware replay reached a very high score, but the transcript revealed context recall of exact answer anchors. That is not a blind benchmark result, but it is scientifically useful: it proves the architecture can detect when memory is genuinely being used.

## What Sets This Apart From Other DSL Submissions

Many DSL-style submissions are optimized for model training or formal problem rendering. Canon DSL is aimed at a different layer: **problem-family metadata**.

The distinction is:

| approach | primary object |
| --- | --- |
| model distillation | model response or reasoning trace |
| formalization | theorem/proof object |
| ordinary synthetic data | prompt and answer |
| Canon DSL v2.1 | metadata contract of the mathematical problem family |

The metadata contract is intended to survive rendering changes, prompt changes, and generated descendants. If a mutation changes the difficulty, the metadata should say what changed. If a solution depends on an invariant, the metadata should name it. If a row has an answer normalization rule, the metadata should expose that rule.

This makes the dataset easier to inspect than a plain pile of problem statements.

## VoE-2026 Evaluation Benchmark

I also released **Vault of Echoes 2026** as a reproducible exact-answer benchmark:

https://huggingface.co/datasets/Neohm/VoE-2026

VoE-2026 contains **25 exact-integer mathematical reasoning problems** with a public answer key and a DOI:

https://doi.org/10.57967/hf/8554

It is intentionally a public-answer benchmark. The purpose is reproducibility, sanity checking, and independent verification. Scores should disclose whether the system has seen the public key.

The released schema is simple:

```csv
id,problem,answer
```

The scoring contract is exact integer match. This makes it easy for others to test systems without needing hidden infrastructure.

## How To Use The Runtime-at-Boot Dataset

In Kaggle, the dataset is expected to mount at:

```text
/kaggle/input/runtimeatboot/runtimeatbootdataset
```

Example loading pattern:

```python
import json
from pathlib import Path

root = Path("/kaggle/input/runtimeatboot/runtimeatbootdataset")
athena_study = root / "boot/athena/Athena_epistemic_boot_100_final_hq.ndjson"

rows = []
with athena_study.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))

print(len(rows))  # 100
```

Recommended usage:

- Use `boot/*/*final*.ndjson` study files as answer-key-free memory.
- Use `*_certification*` or `*_mcq*` files only for certification.
- Do not place certification answers into ordinary solve prompts.
- Report whether an experiment is answer-free, answer-aware, or public-key exposed.

## Validation And Hygiene

The later dataset package includes:

- row counts,
- bad-JSON counts,
- answer-row counts,
- SHA256 checksums,
- study/certification boundary manifests,
- and sanitize reports.

For Runtime-at-Boot v33, the manifest reports:

- 3 roles,
- 300 answer-key-free study rows,
- 300 answer-bearing certification rows,
- 600 total rows,
- 0 bad JSON rows in canonical boot files,
- and balanced MCQ answer distribution in certification files.

This is the kind of hygiene the first raw CSV lacked. The project improved because the early flaws were exposed.

## Limitations

The project is not finished, and I want to state the limitations clearly:

- The original `math_corpus.csv` should be treated as a prototype artifact, not as the final cleaned release.
- Some early seed problems are standard and easy. They are useful for schema validation, not for difficulty claims.
- Canon DSL metadata is only as good as the solved source and the distillation pass.
- Runtime-at-Boot can help expose memory use, but memory can also contaminate evaluation if answer-bearing material crosses the prompt boundary.
- VoE-2026 has a public key, so it is reproducible but not hidden after release.

These limitations are not reasons to discard the work. They are exactly the reasons a metadata-first, audit-first dataset format is useful.

## Expected Outcome For Users

A user of this dataset should be able to:

1. inspect mathematical problem-family structure rather than only prompt text;
2. derive structured prompts, variants, and certification questions from metadata;
3. test whether reusable reasoning memory improves downstream solving;
4. evaluate exact-answer behavior on VoE-2026;
5. and audit whether a run is genuinely solving or merely recalling exposed answers.

## Links

- Runtime-at-Boot Kaggle dataset: https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot
- Canon DSL v2.1 paper: https://zenodo.org/records/19694800
- VoE-2026 benchmark: https://huggingface.co/datasets/Neohm/VoE-2026
- VoE-2026 DOI: https://doi.org/10.57967/hf/8554
- AEN revision ledger: https://github.com/Aadityapaudel2/AEN_Architecture/tree/main/revisions

## Closing

My original submission was too raw. The reviewers are right to ask about answer-column errors and easy seed items. The cleaned contribution is the methodology and release path that grew from that failure: Canon DSL v2.1 for metadata-first mathematical distillation, Runtime-at-Boot for certified reasoning memory, and VoE-2026 for reproducible exact-answer evaluation.

I hope this is useful to the community as a practical, inspectable way to build and audit synthetic mathematical datasets.
