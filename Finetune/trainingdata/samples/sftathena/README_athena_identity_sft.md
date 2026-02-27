# Athena identity + myth puzzles — SFT-ready rebuild (from athena_identity_myth_puzzles_train.jsonl)

## What you get in this zip
This package contains **clean, SFT-ready** JSONL datasets split by objective, plus a combined “best” file.

### Files
- `dataset_persona_chat.jsonl` — **Athena persona + myth-puzzle solving** (clean conversational outputs)
- `dataset_math_distillator_v21.jsonl` — **Canon v2.1 distillation** YAML targets (`schema_id: distillator_dsl.math.v2.1`)
- `dataset_math_rs_adj.jsonl` — **RS-ADJ math metadata** targets (`id: RS-ADJ-...`)
- `dataset_math_metadata.jsonl` — combined math metadata (Distillator v2.1 + RS-ADJ)
- `athena_identity_myth_puzzles_sft_best.jsonl` — **recommended single-file training set** (persona + math; still clean)
- `excluded_rows.json` — list of source line numbers excluded (87–229) with coarse reason tags

## Row counts
- Persona: **40**
- Math (Distillator v2.1): **45**
- Math (RS-ADJ): **4**
- Math (combined): **49**
- Best combined SFT set: **89**
- Excluded from source: **143** (all rows 87–229)

## Key fixes applied (high signal)
- **Hard split by objective**: persona vs math metadata.
- **Dropped the contaminated “memory-extraction / raw transcript” zone** (source lines 87–229).
- **Persona normalization**:
  - added a stable **Athena system conditioning** message per row
  - assistant outputs rewritten to be **warm, modern, paragraph style**, myth-aware (no raw logs)
  - removed markdown-heavy blueprint formatting in the Outlier/blueprint rows
  - salvaged a few *useful* embedded user prompts that were trapped inside assistant transcript blobs (rewritten cleanly)
- **Math normalization**:
  - added dedicated **system conditioning** for distillator vs RS-ADJ
  - cleaned the RS-ADJ line 77 user prompt down to the actual math problem statement (kept target metadata intact)

## Training suggestion
- Default: train on `athena_identity_myth_puzzles_sft_best.jsonl`.
- If you want tighter control: two-stage training
  1) persona (`dataset_persona_chat.jsonl`)
  2) math metadata (`dataset_math_metadata.jsonl`) with a smaller LR

