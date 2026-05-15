---
license: cc-by-4.0
language:
  - en
tags:
  - agent-ensemble
  - reasoning
  - mathematics
  - aime
  - runtime-architecture
  - qwen
base_model:
  - Qwen/Qwen3.5-9B
library_name: transformers
pipeline_tag: text-generation
---

<p align="center">
  <img src="./assets/neohm-logo.svg" width="96" alt="Neohm Labs logo">
</p>

# AEN-Ensemble-Triads

`Neohm/AEN-Ensemble-Triads` is a model-like inference architecture rather than a new checkpoint.

It composes three fixed open-weight base model sessions through role-specialized reasoning:

- **Athena** routes, evaluates, synthesizes, and finalizes.
- **Artemis** audits proof, arithmetic, enumeration, boundary conditions, and normalization.
- **Aria** constructs alternate routes and preserves disagreement state.

The repo is the callable AEN module: it declares base checkpoints, runtime profiles, controller logic, certification boundaries, and reproducible evaluation artifacts.

## What This Is

AEN-Ensemble-Triads is an inference-time agentic triad over fixed base checkpoints.

It does **not** introduce new pretrained weights. It does **not** finetune, merge, train adapters, or apply RLHF. The base model checkpoints are dependencies. The citable contribution is the AEN runtime architecture: roles, controller, long-context profile, Runtime-at-Boot boundary, certification gate, and answer extraction.

## Current Status

This repository scaffold is being prepared for the first runnable release.

The current local implementation exists as a Colab/notebook codebase and AEN GitHub artifact. This Hugging Face repo is the transition from notebook artifact to loadable metamodel.

## Intended API

```python
from aen_ensemble_triads import AEN

aen = AEN.from_pretrained(
    "Neohm/AEN-Ensemble-Triads",
    profile="clean_aime2026",
    long_context="auto",
    download_base_models=True,
)

result = aen.solve("Find the number of ...")
print(result.final_answer)
print(result.claim_status)
```

## Profiles

| profile | purpose | blind benchmark eligible |
| --- | --- | --- |
| `clean_aime2026` | answer-free AIME-style run profile | yes |
| `rab_v33_answer_free` | Runtime-at-Boot v33 study/certification experiment | yes, if no answer-bearing certification rows enter solve prompt |
| `v34_answer_aware_diagnostic` | answer-aware context-recall and repair diagnostic | no |
| `local_cpu_smoke` | small local wiring test | no leaderboard claim |
| `kaggle_h100_yarn_1010k` | ultralong vLLM/YaRN runtime profile | profile-dependent |

## Claim Boundary

The evaluated object should be cited as:

```text
Neohm/AEN-Ensemble-Triads
```

The underlying base checkpoints must also be credited. In the first scaffold, the base checkpoint dependency is:

```text
Qwen/Qwen3.5-9B
```

For official benchmark claims, use an answer-free profile. The V34 diagnostic replay reached 29/30 on AIME-2026, but it is answer-aware and should be reported only as a context-recall/repair diagnostic, not as blind benchmark generalization.

## Runtime-at-Boot Boundary

Runtime-at-Boot v33 contains both study rows and certification rows. Both are dataset components, but they have different prompt-boundary semantics:

- Study rows are answer-key-free role memory.
- Certification rows are answer-bearing MCQ gates used to verify memory loading.
- Certification answers must not be injected into ordinary solve prompts.

## Files

- `aen_manifest.yaml`: canonical AEN architecture manifest.
- `profiles/*.yaml`: runtime profiles.
- `datasets/*.yaml`: dataset registries and prompt-boundary contracts.
- `roles/*.md`: role prompts.
- `aen_ensemble_triads/`: Python package surface.
- `docs/claim_boundaries.md`: benchmark and diagnostic claim rules.

## References

- AEN GitHub revision ledger: https://github.com/Aadityapaudel2/AEN_Architecture/tree/main/revisions
- Runtime-at-Boot dataset: https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot
- Canon DSL v2.1 paper: https://zenodo.org/records/19694800
- VoE-2026 benchmark: https://huggingface.co/datasets/Neohm/VoE-2026
