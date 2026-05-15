# Source Audit Notes

These notes summarize the local evidence used for the Kaggle writeup draft.

## Original Downloaded Submission Files

Found in:

```text
N:\Downloads Chrome
```

Files:

- `main.pdf`
- `nonmathmath.jsonl`
- `seeds.zip`

Observed facts:

- `nonmathmath.jsonl` has 50 JSONL rows.
- `seeds.zip` contains seed files such as `nt_20.txt`, `alg_08.txt`, `comb_*`, `geom_*`, TeX files `p01.tex` through `p25.tex`, reports, and `main.pdf`.
- `nt_20.txt` contains a worked solution with final answer `243`.
- `alg_08.txt` is the AM-GM example with final answer `8`.

Local search note:

- `math_corpus.csv` was not found under the searched locations:
  - `N:\Research`
  - `D:\AthenaPlayground`
  - `N:\Downloads Chrome`

This does not mean the CSV never existed. It only means the local file was not found in the currently searched workspace and download paths.

## Canon DSL v2.1

Found in:

```text
N:\Research\Canon_DSL_v2.1
```

Key files:

- `README.md`
- `paper\Canon_DSL_v2.1.pdf`
- `source_candidate\main.tex`
- `metadata\zenodo_record.json`

Key claim from local README:

Canon DSL v2.1 is a metadata-first YAML schema for distilling solved mathematics problems into structured, machine-readable records that can support synthetic problem generation.

DOI / record:

```text
https://zenodo.org/records/19694800
```

## Runtime-at-Boot Dataset

Found in:

```text
N:\Research\runtimeatbootdataset
```

Public dataset:

```text
https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot
```

Important local files:

- `README_RUNTIMEATBOOT.txt`
- `runtimeatboot_manifest.json`
- `SANITIZED_BOOT_MEMORY_BOUNDARY.json`
- `V33_SANITIZE_REPORT.md`
- `V33_ROLE_FILE_AUDIT.csv`

Observed manifest facts:

- dataset version: `v33`
- roles: 3
- study rows total: 300
- certification rows total: 300
- rows total: 600
- study rows are answer-key-free
- certification rows contain MCQ answer keys
- certification rows must not be injected into ordinary solve prompts

Canonical boot row counts:

| role | study rows | certification rows |
| --- | ---: | ---: |
| Athena | 100 | 100 |
| Aria | 100 | 100 |
| Artemis | 100 | 100 |

## VoE-2026

Found in:

```text
N:\Research\datasets\VoE_2026_hf_repo
```

Public dataset:

```text
https://huggingface.co/datasets/Neohm/VoE-2026
```

DOI:

```text
10.57967/hf/8554
```

Observed facts:

- row count: 25
- schema: `id, problem, answer`
- answer contract: exact decimal integer string
- public key is included for reproducible scoring
- users must disclose exposure to public key before reporting benchmark scores

## Suggested Framing

The safest and strongest Kaggle framing is:

1. Acknowledge the raw original `math_corpus.csv` had answer-column and difficulty issues.
2. Do not ask reviewers to treat that raw CSV as the final cleaned artifact.
3. Present Canon DSL v2.1 as the real methodological contribution.
4. Present Runtime-at-Boot v33 as the cleaned Kaggle dataset release.
5. Present VoE-2026 as the reproducible public-answer evaluation surface.
