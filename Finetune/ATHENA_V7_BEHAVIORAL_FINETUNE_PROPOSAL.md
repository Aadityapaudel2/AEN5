# Athena V7 Behavioral Finetuning Proposal (Qwen3-1.7B)

## 1) Objective
Optimize **behavioral quality** (persona consistency + math reasoning format + controllability) for `Qwen3-1.7B` using small, high-quality datasets, with experiments designed to answer:
- Is `100 persona + 100 math` better than a mixed `200`?
- Is two-stage tuning better than one-stage tuning?
- Does smaller model size imply fewer examples are better?

This plan intentionally ignores throughput/cost optimization and focuses on quality/validation.

## 2) Current Training Launcher Status
`Finetune/run_training.ps1` already includes explicit accelerate runtime args:
- `--num_processes 1`
- `--num_machines 1`
- `--mixed_precision bf16`
- `--dynamo_backend no`

So the prior accelerate warning is resolved by configuration completeness.

## 3) Key Hypotheses
H1. For 1.7B, behavior improves with **targeted data quality + validation**, not just more rows.  
H2. `100 persona + 100 math` often outperforms random mixed `200` when examples are stratified and clean.  
H3. Two-stage tuning (persona stage, then math stage) can preserve identity while improving math compliance, but must be checked for catastrophic drift.

## 4) Why “small model = fewer points” is incomplete
- Small models overfit faster, but that does **not** prove fewer examples are always better.
- Correct claim: small models need tighter curation, cleaner labels, and stronger validation.
- Required: empirical evaluation on held-out sets (persona + math), not intuition only.

## 5) Experimental Design (Behavioral-First)

### Dataset splits (fixed across all runs)
- `train_persona`: 100 high-quality persona/identity rows.
- `train_math`: 100 high-quality math rows (metadata-aware formatting).
- `val_persona`: 20 held-out persona rows.
- `val_math`: 20 held-out math rows.
- Optional `challenge_eval`: 20 adversarial prompts (prompt injection, style drift, off-topic pivots).

### Run matrix
1. **R0 Baseline**: untuned base model.
2. **R1 Mixed200-OneStage**: 200 mixed rows, one pass.
3. **R2 Split100+100-OneStage**: 200 rows but balanced in each batch (or shuffled balanced).
4. **R3 TwoStage Persona->Math**:
   - Stage A: persona-only (100)
   - Stage B: math-only (100), low LR continuation.
5. **R4 TwoStage Math->Persona**:
   - Stage A: math-only
   - Stage B: persona-only (checks reverse-order effect).

### Primary selection metric
Composite behavioral score:
- Persona consistency (40%)
- Math structure compliance (40%)
- Safety/steerability and refusal quality (20%)

## 6) Metrics and Validation

### Persona metrics
- Identity consistency rate (% responses staying in intended Athena persona).
- Forbidden drift rate (% responses contradicting canonical identity constraints).
- Style adherence score (rubric-based, 1-5).

### Math metrics
- Format compliance (required structure present).
- Correctness proxy (rule-based checks + spot human verification).
- Metadata alignment score (uses appropriate tags/techniques where expected).

### Stability metrics
- Repetition failure rate.
- Hallucinated self-facts rate.
- Prompt-following under adversarial wording.

## 7) Recommended “slow but usable” run settings (for this dataset scale)
These are conservative while avoiding 2-day runtime behavior:

- `max_seq_length`: 768 (increase only if truncation is proven harmful).
- `per_device_train_batch_size`: 1
- `gradient_accumulation_steps`: 8
- `learning_rate`: `5e-6` (full SFT conservative).
- `num_train_epochs`: start 6-8 for pilot; extend only if val keeps improving.
- `warmup_ratio`: 0.05
- `lr_scheduler_type`: `constant_with_warmup` (preferred on short small-data runs).
- `logging_steps`: 5
- `save_steps`: 25
- `save_only_model`, `bf16`, `gradient_checkpointing`.

If runtime is too long, reduce epochs first; do not remove validation.

## 8) Persona Injection Guidance
Is 100 persona points enough?  
- It can be enough for visible behavior shifts if examples are highly consistent and non-contradictory.
- It is not enough if examples are noisy/duplicative/contradictory.

Minimum practical rule:
- 100 strong rows + 20 held-out persona validation is acceptable for a first controlled run.
- Expand only after measuring failure clusters.

## 9) Data Quality Requirements Before Any Next Run
- Remove duplicates and near-duplicates.
- Remove contradictory persona facts.
- Normalize user instruction diversity (no repetitive “Store canonical anchor ...” templates).
- Keep assistant responses coherent and consistent in voice.
- Ensure math rows use one canonical response schema.

## 10) Decision Rule After Experiments
Pick the run that wins on:
1. Highest composite behavioral score.
2. No severe regression on math correctness or persona consistency.
3. Best robustness on challenge_eval.

If ties:
- Prefer the simpler pipeline (one-stage) unless two-stage clearly reduces drift.

## 11) Immediate Next Steps
1. Build fixed splits (`train/val`) for persona and math now.
2. Run `R0`, `R1`, `R2` first.
3. Only then run two-stage `R3`, `R4`.
4. Compare with one evaluation script and one rubric.
5. Promote winning checkpoint to `AthenaV7.01-candidate`.
