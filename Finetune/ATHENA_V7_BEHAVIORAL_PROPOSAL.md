# Athena V7 Behavioral Finetune Proposal

## 1) Goal
Find the best training strategy for Athena behavior quality on a 1.7B model, focusing on:
- persona consistency,
- math behavior quality,
- instruction compliance,
- minimal overfitting.

Compute cost is secondary in this phase.

## 2) Key Questions
1. Is `100 persona + 100 math` better than one mixed `200` set?
2. Is two-stage training (persona then math) better than one-stage mixed training?
3. How many examples are enough before behavior saturates on 1.7B?

## 3) Core Principles
- Small models can adapt with fewer examples, but also overfit faster.
- Line count alone is weak; diversity and validation are required.
- Claims must be empirical: fixed protocol + holdout evaluation.

## 4) Dataset Protocol
Create **three non-overlapping sets**:
- `train`: training examples
- `dev`: model selection / early checks
- `test_behavior`: final behavioral report only (never used for tuning)

Recommended split for current scale:
- 70% train / 15% dev / 15% test_behavior

Add a `source_group` tag to each row:
- `persona`, `math`, `memory`, `policy`, etc.
This enables stratified split and fair comparisons.

## 5) Experimental Matrix (Behavioral-Only)
Run all with identical optimizer policy unless noted.

### Base hyperparameter profile
- max_seq_length: 512 (or 768 if runtime acceptable)
- per_device_train_batch_size: 1
- gradient_accumulation_steps: 8
- learning_rate: 5e-6
- num_train_epochs: 8
- warmup_ratio: 0.05
- scheduler: constant_with_warmup (preferred)
- max_grad_norm: 1.0
- weight_decay: 0.01
- bf16 + gradient_checkpointing

### Runs
1. `R1 Persona-100`
2. `R2 Math-100`
3. `R3 Mixed-200` (single-stage)
4. `R4 Two-stage`: Persona-100 -> Math-100
5. `R5 Two-stage`: Math-100 -> Persona-100
6. `R6 Mixed-200 (shuffled curriculum with balanced source_group)`

## 6) Evaluation (No Cost Metric)
Use the same fixed prompt suite for all runs.

### Behavioral metrics
- Persona fidelity score (0-5 rubric, blind rated)
- Identity stability across 10-turn conversations
- Instruction compliance (exact-format tasks)
- Refusal/guardrail consistency

### Math metrics
- Exact answer accuracy on held-out math prompts
- Error type breakdown: arithmetic / logic / formatting

### Overfitting checks
- train-vs-dev loss gap trend
- near-copy detection against training set
- behavior collapse under paraphrased prompts

## 7) Decision Rule
Pick the model that satisfies all:
1. Highest `test_behavior` persona stability,
2. No major dev overfit signal,
3. Math score not lower than baseline threshold,
4. Consistent response formatting.

If tie:
- prefer simpler training path (single-stage mixed) unless two-stage gives clear gains.

## 8) Practical Recommendation Right Now
- Current run throughput is very slow; do not use it as primary evidence.
- Start with `R3 Mixed-200` and `R4 Persona->Math` first.
- Compare on the same frozen test_behavior suite before launching more runs.

## 9) Deliverables
For each run, store:
- config file / command,
- checkpoint path,
- dev metrics,
- behavior report table,
- final decision summary.
