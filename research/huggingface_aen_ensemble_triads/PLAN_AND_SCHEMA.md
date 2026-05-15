# Hugging Face AEN Ensemble Triads: Plan And Schema

This document defines the first implementation target for `Neohm/AEN-Ensemble-Triads`.

The central claim is:

> AEN-Ensemble-Triads is a loadable inference-time agentic triad architecture. It does not introduce new base weights. It declares, downloads, configures, and orchestrates fixed base checkpoints through Athena, Artemis, and Aria.

This avoids the wrong framing where a leaderboard rewards only the underlying Qwen checkpoint. The submitted/cited object becomes the AEN architecture: controller, role contracts, runtime profile, boot/certification data boundary, answer extraction, and reproducibility manifest.

## Grounding Artifacts

Current local artifacts used to shape this plan:

- Current 96.7% diagnostic Colab export:
  `N:\Downloads Chrome\AENAIMO260_0_2_3_V34_NEXT_RUN.ipynb`
- Codeblock extraction for the V34 run:
  `N:\Research\AEN_paper\github_push\next_run_v34\codeblocks`
- Public Runtime-at-Boot v33 dataset payload:
  `N:\Research\runtimeatbootdataset`
- AEN paper / GitHub package:
  `N:\Research\AEN_paper\github_push`
- Target Hugging Face repo:
  `https://huggingface.co/Neohm/AEN-Ensemble-Triads`

Important claim boundary:

- `clean_aime2026` / answer-free profiles are eligible for blind benchmark claims.
- `v34_answer_aware_diagnostic` is a context-recall and repair diagnostic. It reached 29/30 on AIME-2026, but it is not a blind benchmark result.

## Product Shape

The Hugging Face repo should be a model-like module, not a weight dump.

Recommended public identity:

```text
Neohm/AEN-Ensemble-Triads
```

Recommended one-shot API:

```python
from aen_ensemble_triads import AEN

aen = AEN.from_pretrained(
    "Neohm/AEN-Ensemble-Triads",
    profile="clean_aime2026",
    long_context=True,
    download_base_models=True,
)

answer = aen.solve(problem)
print(answer.final_answer)
```

What happens behind that call:

1. Download the AEN metamodel repo.
2. Read `aen_manifest.yaml`.
3. Resolve the requested profile.
4. Download pinned base checkpoint snapshots for Athena, Artemis, and Aria.
5. Start or attach three model sessions.
6. Apply long-context profile if enabled and supported.
7. Load Runtime-at-Boot study rows and run certification if the profile requires it.
8. Run the controller loop.
9. Extract one final answer with an audit record.

## Repository Layout

Proposed HF repo tree:

```text
AEN-Ensemble-Triads/
  README.md
  LICENSE
  CITATION.cff
  config.json
  aen_manifest.yaml
  model_index.json
  requirements.txt

  aen_ensemble_triads/
    __init__.py
    configuration_aen.py
    modeling_aen.py
    manifest.py
    profiles.py
    downloader.py
    runtime_vllm.py
    runtime_transformers.py
    controller.py
    roles.py
    certification.py
    datasets.py
    answer_extractor.py
    claims.py
    telemetry.py

  roles/
    athena.md
    artemis.md
    aria.md

  profiles/
    clean_aime2026.yaml
    rab_v33_answer_free.yaml
    v34_answer_aware_diagnostic.yaml
    local_cpu_smoke.yaml
    kaggle_h100_yarn_1010k.yaml

  datasets/
    runtimeatboot.yaml
    voe_2026.yaml
    matharena_aime2026.yaml

  examples/
    quickstart.py
    solve_one_problem.py
    run_aime2026_matharena.py
    colab_quickstart.ipynb

  eval_results/
    aime2026_clean_answer_free.yaml
    aime2026_v34_answer_aware_diagnostic.yaml

  docs/
    architecture.md
    claim_boundaries.md
    runtime_profiles.md
    leaderboard_submission.md
```

## Core Manifest Schema

`aen_manifest.yaml` is the canonical database record for the architecture.

```yaml
schema_id: neohm.aen_ensemble_triads.manifest.v1
schema_version: 1

identity:
  repo_id: Neohm/AEN-Ensemble-Triads
  architecture_id: aen_ensemble_triads
  architecture_version: 0.1.0
  display_name: AEN-Ensemble-Triads
  architecture_type: inference_time_agentic_triad
  owner: Neohm
  author: Aaditya Paudel

claim_boundary:
  no_new_base_weights: true
  no_finetuning: true
  no_rlhf: true
  no_adapter_training: true
  no_weight_merge: true
  submitted_object: controller_plus_runtime_profile
  base_models_are_dependencies: true

roles:
  athena:
    runtime_key: solver
    display_name: Athena
    role_type: route_architect_finalizer
    prompt_file: roles/athena.md
    schema_family: distillator_dsl.math.v2.1
  artemis:
    runtime_key: clerk
    display_name: Artemis
    role_type: verifier_auditor
    prompt_file: roles/artemis.md
    schema_family: auditlineage_dsl.v2.3
  aria:
    runtime_key: agent
    display_name: Aria
    role_type: alternate_route_synthesizer
    prompt_file: roles/aria.md
    schema_family: prooflineage_dsl.v2.2

base_checkpoints:
  athena:
    repo_id: Qwen/Qwen3.5-9B
    revision: main
    local_subdir: Qwen3.5-9B-solver
    served_model_name: Qwen3.5-9B-solver
    role: Athena
  artemis:
    repo_id: Qwen/Qwen3.5-9B
    revision: main
    local_subdir: Qwen3.5-9B-clerk
    served_model_name: Qwen3.5-9B-clerk
    role: Artemis
  aria:
    repo_id: Qwen/Qwen3.5-9B
    revision: main
    local_subdir: Qwen3.5-9B-agent
    served_model_name: Qwen3.5-9B-agent
    role: Aria

default_profile: clean_aime2026

profiles:
  clean_aime2026: profiles/clean_aime2026.yaml
  rab_v33_answer_free: profiles/rab_v33_answer_free.yaml
  v34_answer_aware_diagnostic: profiles/v34_answer_aware_diagnostic.yaml
  local_cpu_smoke: profiles/local_cpu_smoke.yaml
  kaggle_h100_yarn_1010k: profiles/kaggle_h100_yarn_1010k.yaml

datasets:
  runtimeatboot: datasets/runtimeatboot.yaml
  voe_2026: datasets/voe_2026.yaml
  matharena_aime2026: datasets/matharena_aime2026.yaml

interfaces:
  python_import: aen_ensemble_triads.AEN
  one_shot_method: solve
  batch_method: solve_batch
  matharena_adapter: examples/run_aime2026_matharena.py
```

Implementation note: the `revision` fields should be pinned to exact commit hashes before DOI freeze. `main` is acceptable only during active development.

## Runtime Profile Schema

Each profile is a runnable mode.

```yaml
schema_id: neohm.aen_ensemble_triads.runtime_profile.v1
profile_id: kaggle_h100_yarn_1010k
profile_version: 0.1.0
profile_class: experimental_ultralong

claim_status:
  blind_benchmark_eligible: false
  answer_aware: true
  public_score_claim_allowed: diagnostic_only
  notes: >
    This profile reproduces the V34 context-recall/repair diagnostic discipline.
    It must not be used as a blind benchmark claim if answer-aware rows are loaded.

backend:
  preferred: vllm_openai
  fallback: transformers_local
  vllm_version: "0.18.1"
  trust_remote_code: true
  language_model_only: true

hardware:
  target: kaggle_h100_or_equivalent
  device: cuda
  tensor_parallel_size: 1

long_context:
  enabled: true
  method: yarn
  context_window_tokens_per_role: 1010000
  distributed_context_tokens: 3030000
  rope_parameters:
    rope_type: yarn
    factor: 4.0
    original_max_position_embeddings: 262144
    rope_theta: 10000000
    mrope_interleaved: true
    mrope_section: [11, 11, 10]
  env:
    VLLM_ALLOW_LONG_MAX_MODEL_LEN: "1"

roles:
  athena:
    runtime_key: solver
    port: 8000
    gpu_memory_utilization: "0.30"
    max_model_len: 1010000
  artemis:
    runtime_key: clerk
    port: 8001
    gpu_memory_utilization: "0.30"
    max_model_len: 1010000
  aria:
    runtime_key: agent
    port: 8002
    gpu_memory_utilization: "0.34"
    max_model_len: 1010000

generation:
  default_temperature: 0.2
  default_top_p: 0.95
  enable_thinking: false
  stop_sequences:
    - "\nSystem:"
    - "\nDeveloper:"
    - "\nUser:"

controller:
  max_big_loops: 3
  min_big_loop_for_closeout: 1
  inner_total_exchanges: 3
  inner_reasoning_exchanges: 3
  closeout_confidence_pct: 85
  athena_open_max_tokens: 5200
  aria_exchange_max_tokens: 3400
  artemis_exchange_max_tokens: 3400
  aria_report_max_tokens: 1500
  artemis_report_max_tokens: 1500
  athena_synthesis_max_tokens: 3800
  athena_final_max_tokens: 768
  reset_session_each_turn: false
  problem_boundary_reset_policy: before_problem_and_after_problem_only
  mandatory_finalization_turn: true

runtime_at_boot:
  enabled: true
  dataset_profile: runtimeatboot_v34_diagnostic
  require_certification: true
  preserve_boot_memory_across_problem_reset: true

telemetry:
  token_accounting: true
  per_turn_architecture_certificate: true
  transcript_export: true
```

For the default public profile, use a safer claim boundary:

```yaml
profile_id: clean_aime2026
profile_class: answer_free_benchmark
claim_status:
  blind_benchmark_eligible: true
  answer_aware: false
  public_score_claim_allowed: true
runtime_at_boot:
  enabled: false
  require_certification: false
```

## Dataset Registry Schema

Runtime-at-Boot should be automatically resolvable, but not silently mutable.

Recommended rule:

- Default is pinned.
- `latest` is allowed only when the user explicitly asks for it.
- A run record must save the exact dataset revision and file hashes actually used.

```yaml
schema_id: neohm.aen_ensemble_triads.dataset_registry.v1
dataset_id: runtimeatboot
default_revision_policy: pinned

sources:
  kaggle:
    id: aadityapaudel/runtimeatboot
    version: v33
    role: public_answer_free_boot_and_certification
  local_reference:
    path: N:\Research\runtimeatbootdataset
    version: v33

contract:
  study_rows_are_answer_key_free: true
  certification_rows_are_answer_bearing: true
  certification_rows_are_dataset_components: true
  certification_rows_must_not_enter_ordinary_solve_prompt: true

files:
  athena_study:
    path: boot/athena/Athena_epistemic_boot_100_final_hq.ndjson
    rows: 100
    answer_rows: 0
  athena_certification:
    path: boot/athena/Athena_epistemic_boot_100_final_certification_hq.ndjson
    rows: 100
    answer_rows: 100
  artemis_study:
    path: boot/artemis/Artemis_problem_proof_boot_100_final_hq.ndjson
    rows: 100
    answer_rows: 0
  artemis_certification:
    path: boot/artemis/Artemis_problem_proof_boot_100_final_hq_mcq.ndjson
    rows: 100
    answer_rows: 100
  aria_study:
    path: boot/aria/Aria_problem_proof_boot_100_final.ndjson
    rows: 100
    answer_rows: 0
  aria_certification:
    path: boot/aria/Aria_problem_proof_boot_100_final_mcq_2q.ndjson
    rows: 100
    answer_rows: 100

boot_mechanics:
  sequence:
    - load_answer_free_study_rows
    - ask_certification_mcqs
    - score_certification_gate
    - capture_certified_boot_memory_baseline
    - reset_problem_boundary_preserving_boot_memory
    - begin_solve
  fail_policy: fail_closed
```

## Controller Schema

The controller is the heart of the AEN architecture.

```yaml
schema_id: neohm.aen_ensemble_triads.controller.v1
controller_id: aen_triads_math_v0_2_3

roles:
  - Athena
  - Artemis
  - Aria

turn_order:
  - phase: athena_open
    speaker: Athena
    contract:
      - Canon DSL style problem breakdown
      - given/ask/route map
      - questions for Aria
      - questions for Artemis
      - no final answer
  - phase: aria_exchange_1
    speaker: Aria
    contract:
      - alternate route construction
      - answer Athena
      - ask Artemis for checks
  - phase: artemis_exchange_1
    speaker: Artemis
    contract:
      - audit route hinge
      - answer Athena and Aria
      - name blockers
  - phase: peer_exchanges
    speakers: [Aria, Artemis]
    repeat: inner_total_exchanges
  - phase: peer_reports
    speakers: [Aria, Artemis]
    contract:
      - candidate exact integer if validated
      - confidence
      - unresolved blocker status
      - no boxed final answer block
  - phase: athena_synthesis
    speaker: Athena
    contract:
      - selected candidate only
      - no final_answer_block
  - phase: athena_finalization
    speaker: Athena
    contract:
      - mandatory final answer turn
      - only this phase emits final_answer_block

closeout_gate:
  requires_peer_alignment: true
  requires_trio_alignment: true
  requires_distinct_peer_reports: true
  requires_no_open_blocker: true
  requires_confidence_at_least: 85
  final_answer_format: "\\boxed{<integer>}_confidence:<0-100 integer>"

answer_contract:
  aime_integer:
    min: 0
    max: 999
    normalize: integer_string
```

## Knob Registry

These are the knobs that should be exposed in code, CLI, and YAML.

```yaml
schema_id: neohm.aen_ensemble_triads.knobs.v1

model_loading:
  base_repo_id:
    default: Qwen/Qwen3.5-9B
    per_role_override: true
  revision:
    default: pinned_commit_required_for_release
  download_base_models:
    default: true
  local_model_root:
    default: ~/.cache/neohm/aen/models

runtime:
  backend:
    values: [vllm_openai, transformers_local]
    default: vllm_openai
  long_context:
    values: [true, false, auto]
    default: auto
  context_profile:
    values: [safe_32k, yarn_240k, yarn_1010k]
    default: safe_32k
  trust_remote_code:
    default: true

controller:
  max_big_loops:
    default: 3
    min: 1
  inner_total_exchanges:
    default: 3
    min: 1
  closeout_confidence_pct:
    default: 85
    min: 0
    max: 100
  mandatory_finalization_turn:
    default: true
  reset_policy:
    default: before_problem_and_after_problem_only

runtime_at_boot:
  enabled:
    default: false
  dataset:
    default: aadityapaudel/runtimeatboot
  dataset_revision:
    default: pinned
  require_certification:
    default: true
  inject_certification_answers_into_solve:
    default: false
    hard_forbidden: true

output:
  transcript_export:
    default: true
  telemetry_export:
    default: true
  answer_format:
    default: integer
```

## One-Shot Executable Plan

CLI target:

```bash
python -m aen_ensemble_triads.run \
  --profile clean_aime2026 \
  --long-context auto \
  --problem-file problem.txt \
  --out runs/one_problem
```

Python target:

```python
from aen_ensemble_triads import AEN

aen = AEN.from_pretrained(
    "Neohm/AEN-Ensemble-Triads",
    profile="clean_aime2026",
    long_context="auto",
)

result = aen.solve("Find the number of ...")
print(result.final_answer)
print(result.claim_status)
print(result.telemetry.total_tokens)
```

MathArena adapter target:

```bash
python examples/run_aime2026_matharena.py \
  --profile clean_aime2026 \
  --n 4 \
  --output eval_results/aime2026_clean_answer_free.yaml
```

The adapter should make the benchmarked object `Neohm/AEN-Ensemble-Triads`, with base checkpoints listed as dependencies.

## Loader Flow

Implementation pseudocode:

```python
class AEN:
    @classmethod
    def from_pretrained(
        cls,
        repo_id: str,
        profile: str = "clean_aime2026",
        long_context: bool | str = "auto",
        download_base_models: bool = True,
        dataset_revision: str = "pinned",
        **overrides,
    ) -> "AEN":
        manifest = load_manifest(repo_id)
        profile_cfg = load_profile(manifest, profile)
        profile_cfg = apply_overrides(profile_cfg, long_context=long_context, **overrides)
        validate_claim_boundary(profile_cfg)
        base_paths = resolve_base_checkpoints(manifest, profile_cfg, download=download_base_models)
        runtime = build_runtime(base_paths, profile_cfg)
        datasets = resolve_datasets(manifest, profile_cfg, revision=dataset_revision)
        controller = build_controller(manifest, profile_cfg, runtime, datasets)
        return cls(manifest=manifest, profile=profile_cfg, runtime=runtime, controller=controller)

    def solve(self, problem: str) -> AENResult:
        if self.profile.runtime_at_boot.enabled:
            self.controller.certify_or_fail()
        return self.controller.solve(problem)
```

## Claim Registry

Every profile/run must emit a machine-readable claim boundary.

```yaml
schema_id: neohm.aen_ensemble_triads.claim_record.v1
run_id: <generated>
profile_id: clean_aime2026
base_models:
  - Qwen/Qwen3.5-9B@<commit>
architecture:
  repo_id: Neohm/AEN-Ensemble-Triads
  version: 0.1.0
runtime:
  backend: vllm_openai
  long_context: auto
datasets:
  runtimeatboot:
    used: false
claim_boundary:
  blind_benchmark_eligible: true
  answer_aware: false
  no_finetuning: true
  no_rlhf: true
  no_new_base_weights: true
```

For V34:

```yaml
profile_id: v34_answer_aware_diagnostic
claim_boundary:
  blind_benchmark_eligible: false
  answer_aware: true
  score_interpretation: context_recall_and_repair_diagnostic
```

## README Thesis

The model card should lead with this:

```text
AEN-Ensemble-Triads is a model-like inference architecture rather than a new checkpoint.
It composes three fixed open-weight base sessions through role-specialized reasoning:
Athena routes and finalizes, Artemis audits, and Aria constructs alternate routes.

The repo is the callable AEN module: it declares base checkpoints, runtime profiles,
controller logic, certification boundaries, and reproducible evaluation artifacts.
```

Do not lead with the 96.7% result. Put that in a clearly labeled diagnostic section.

Recommended result table:

| profile | AIME-2026 result | claim status |
| --- | ---: | --- |
| clean benchmarkgrade AEN | 21/30 | answer-free efficiency result |
| unrestricted reference | 22/30 | high-budget reference |
| Runtime-at-Boot v33 | 17/30 | negative answer-free diagnostic |
| V34 Runtime-at-Boot | 29/30 | answer-aware context-recall diagnostic |

## Implementation Phases

### Phase 1: Metamodel Card

- Create or update HF repo README.
- Add `aen_manifest.yaml`.
- Add profile YAMLs.
- Add claim boundary language.
- Add links to paper, GitHub, Runtime-at-Boot, and AEN revision ledger.

### Phase 2: Minimal Runnable Module

- Implement `AEN.from_pretrained`.
- Implement manifest/profile loading.
- Implement base checkpoint download.
- Implement local smoke mode with no huge context requirement.
- Implement single-problem solve wrapper.

### Phase 3: Runtime-At-Boot Integration

- Add Kaggle/HF/local dataset resolver.
- Load v33 study rows.
- Run certification MCQ gate.
- Capture certified boot-memory baseline.
- Enforce no certification answers in solve prompts.

### Phase 4: vLLM Long-Context Runtime

- Port vLLM server launch from current codeblocks.
- Add YaRN runtime profile.
- Add profile validation for H100-class hardware.
- Add fallback safe-context profile.

### Phase 5: Benchmark Adapters

- Add MathArena AIME-2026 adapter.
- Add internal AIME runner.
- Export HF-compatible eval results.
- Emit claim records and telemetry for every run.

### Phase 6: DOI Freeze

- Pin base checkpoint revisions.
- Pin dataset revisions / hashes.
- Freeze `v0.1.0`.
- Generate DOI only after repo name, visibility, and README are stable.

## Open Decisions For Aaditya

Recommended defaults are marked.

1. **Default public profile**
   - `clean_aime2026` recommended: safest for leaderboards.
   - `rab_v33_answer_free`: useful but current AIME result was lower.
   - `v34_answer_aware_diagnostic`: impressive but not blind.

2. **Base checkpoint policy**
   - Same Qwen3.5-9B checkpoint in three sessions recommended for first release.
   - Separate role checkpoints later if we actually train/modify role models.

3. **Context policy**
   - `long_context="auto"` recommended.
   - `yarn_1010k` available only as explicit ultralong profile.
   - safe default should not require H100.

4. **Runtime-at-Boot default**
   - Off for clean benchmark profile recommended.
   - On for RAB profiles only.
   - Certification answers must never enter ordinary solve prompt.

5. **Leaderboard identity**
   - Submit as `Neohm/AEN-Ensemble-Triads`.
   - Model card says base checkpoints are dependencies.
   - Result cards include claim boundary.

6. **HF repo type**
   - Model repo recommended for citation/leaderboard identity.
   - Optional Space later for demo.
   - Dataset repo remains separate for Runtime-at-Boot.

## Immediate Next Shot

The next implementation turn should create the HF-ready skeleton:

```text
hf_aen_ensemble_triads/
  README.md
  aen_manifest.yaml
  profiles/*.yaml
  datasets/*.yaml
  aen_ensemble_triads/*.py
```

Then port the current notebook in this order:

1. `cb05.py` role prompts and answer normalization.
2. `cb07.py` parser/controller invariants.
3. `cb07_5.py` turn discipline.
4. `cb08.py` Runtime-at-Boot and vLLM session specs.
5. `cb11.py` benchmark runner / dataset resolver.
6. `cb11_5.py` boot-memory preservation and architecture certificates.
7. `cb13.py` scoring/export.

The first pass should not try to reproduce V34 immediately. It should prove:

```text
from_pretrained -> download deps -> start smoke profile -> solve one problem -> export claim record
```

Once that is stable, we add the high-context H100/YaRN profile and benchmark adapters.
