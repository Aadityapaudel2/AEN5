# AthenaV5 Repository Report (Historical Snapshot)

Status note: 2026-03-07 (America/New_York)  
This report predates the desktop-first rebuild. The current live architecture is:
- `desktop_engine/` as the canonical runtime
- `desktop_app/` as the canonical product surface
- `browser/` as a thin adapter over the shared engine

Treat the remainder of this file as historical analysis from the pre-rebuild layout, not as the authoritative current-state handoff.

---

## 1) Executive Summary

AthenaV5 is currently a **local-first LLM stack** with two production-facing interfaces:

1. **Desktop UI runtime** (`run_ui.ps1` -> `qt_ui.py`, fallback `ui.py`)
2. **Web portal runtime** (`run_portal_v5.ps1` -> `portal_server.py` + `cloudflared_athenav5.ps1`)

It already supports:
- local GPU inference on Qwen-family checkpoints,
- streamed generation,
- Markdown + LaTeX rendering,
- multimodal image input (desktop + portal),
- Google OAuth gated web access,
- per-user local logging and uploads.

For AIMO, the repo now has a compact SFT pipeline with a curated dataset:
- `Finetune/aimo_sft_final.jsonl` (207 samples),
- `Finetune/train.py` (compact chat-SFT trainer),
- `Finetune/train_fast_sft.ps1` (single-click fast run wrapper),
- output target `models/tuned/AthenaV8_AIMO_fast`.

The major next frontier is not basic plumbing anymore; it is **agentic orchestration quality**:
- tool-verified reasoning,
- domain-specialized model routing,
- submission-time consensus and retry logic.

---

## 2) Repository Snapshot

Top-level key directories/files:

- `assets/` - Desktop transcript shell/CSS/JS.
- `portal/` - Portal templates/static assets.
- `Finetune/` - Training scripts + datasets + args.
- `models/` - Base/tuned model directories.
- `data/users/` - Per-user portal logs/profiles/uploads.
- `data/clipboard_images/` - Desktop staged pasted images.
- `run_ui.ps1` - canonical desktop launcher.
- `run_portal_v5.ps1` - canonical portal + tunnel launcher.
- `portal_server.py` - FastAPI portal backend (auth, streaming, logging, model bridge).
- `tk_chat.py` - model runtime adapter (`LocalStreamer`).
- `wrap.py` - system prompt loading + chat template rendering + think stripping.
- `athena_paths.py` - canonical model path resolver.
- `system_prompt.json` - active structured persona prompt.
- `gui_config.json` - runtime defaults (sampling, thinking, renderer).

Current tracked local modifications (not yet committed):
- `assets/chat.js`
- `portal/static/portal.js`
- `qt_ui.py`
- `system_prompt.json`

---

## 3) Runtime Architecture

### 3.1 Core Inference Layer

File: `tk_chat.py`

Primary runtime class: `LocalStreamer`

Responsibilities:
- Load tokenizer/config/model from canonical model dir.
- Detect vision-capable models (`vision_config` check).
- Load `AutoProcessor` + multimodal model when available.
- Fallback to text-only causal model if vision init fails.
- Stream tokens via `TextIteratorStreamer`.
- Support stop via `StoppingCriteria` + `threading.Event`.
- Provide runtime config and model-proof metadata.

Prompt/render path:
- `wrap.build_prompt(...)` and/or `wrap.build_messages_from_history(...)`
- model generation
- streamed chunks filtered with `wrap.ThinkStripper`
- final normalized text via `wrap.clean_assistant_text`

### 3.2 Desktop UI Runtime (Primary Local UX)

Launcher: `run_ui.ps1`

Execution flow:
1. Resolve Python executable from local/workspace `.venv`.
2. Prefer Qt UI (`qt_ui.py`), fallback Tk (`ui.py`) if Qt deps missing/failure.
3. Optional dependency auto-install from `requirements.txt`.
4. Launches with software-safe Qt flags/environment.

Qt UI file: `qt_ui.py`

Notable behaviors:
- Transcript rendered in embedded webview (`assets/chat_shell.html` + `assets/chat.js` + `qt_render.py`).
- Character-by-character stream display (queue + timer).
- Enter sends, Shift+Enter newline.
- Image paste support from clipboard and local file URI rendering.
- Staged clipboard images stored under `data/clipboard_images/`.
- Copy buttons for:
  - full message raw text (unrendered source),
  - per-code-block text.
- Thinking/show-thoughts toggles persisted to `gui_config.json`.
- Local logs in `~/.athena_v5/logs/`:
  - `raw.log`
  - `clean.log`
  - `ui_events.jsonl`

Tk fallback file: `ui.py`
- Still maintained as fallback.
- Uses same inference/prompt core (`tk_chat.py`, `wrap.py`).

### 3.3 Portal Runtime (Web + Remote Access)

Launchers:
- `run_portal.ps1` - local-only server run.
- `run_portal_v5.ps1` - full stack (server + cloudflared).
- `cloudflared_athenav5.ps1` - tunnel orchestration modes.

Backend file: `portal_server.py`

Core server features:
- FastAPI app with path prefix (default `/AthenaV5`).
- Session cookie middleware.
- Optional/required Google OAuth (Authlib).
- Startup preflight (auth env completeness, model warm start, log root writability).
- Health endpoint with model/auth/logging state.
- `/api/chat/stream` SSE endpoint.
- `/api/chat` compatibility endpoint (deprecated).
- `/api/me`, `/api/config`, uploads serving endpoint.

Portal frontend:
- `portal/templates/index.html`
- `portal/static/portal.js`
- `portal/static/portal.css`

UX features:
- Authenticated session identity display.
- Enter send + Shift+Enter newline.
- First-token and stream-stall status messages.
- Attach-image + paste-image in composer.
- Preview pending images and rendered transcript images.
- Message and code copy buttons.

---

## 4) Auth, Security, and Data Handling

### 4.1 Google OAuth

Enabled by `ATHENA_AUTH_REQUIRED=1` (default in `run_portal_v5.ps1` parameters).

Required env vars:
- `ATHENA_GOOGLE_CLIENT_ID`
- `ATHENA_GOOGLE_CLIENT_SECRET`
- `ATHENA_AUTH_REDIRECT_URI`
- `ATHENA_PORTAL_SESSION_SECRET`

Portal startup hard-fails when auth is required and env is missing/placeholder.

Current policy in code:
- Any Google account accepted (no domain restriction yet).

### 4.2 Session/Cookies

Session middleware:
- `same_site="lax"`
- `https_only` configurable via `ATHENA_PORTAL_COOKIE_SECURE`
- cookie name: `athena_portal_session`

### 4.3 User-Scoped Local Storage

Root: `data/users/<normalized_email>/`

Files/folders:
- `profile.json`
- `sessions/YYYY-MM-DD.ndjson`
- `errors/YYYY-MM-DD.ndjson`
- `uploads/YYYY-MM-DD/*`

Notes:
- Paths are sanitized and checked against traversal.
- Upload read endpoint enforces ownership when auth is enabled.

### 4.4 Logging Granularity

Event types:
- `auth_login`
- `auth_logout`
- `request_start`
- `delta` (optional)
- `request_done`
- `request_error`

`ATHENA_LOG_DELTAS` defaults to off to avoid NDJSON explosion.

---

## 5) Model and Environment State

### 5.1 Canonical Model Path

File: `athena_paths.py`

Current canonical chat model:
- `D:\AthenaPlayground\AthenaV5\models\Qwen3.5-2B`

### 5.2 Models Present

Under `models/`:
- `Qwen3-1.7B`
- `Qwen3-4B-Instruct-2507`
- `Qwen3.5-2B`
- `Qwen3.5-4B`
- `tuned/`

Under `models/tuned/`:
- `AthenaV7.03_recover`
- `AthenaV8_AIMO_fast` (plus checkpoints present)

### 5.3 Runtime Sampling Defaults

`gui_config.json`:
- `temperature: 0.3`
- `max_new_tokens: 2048`
- `top_p: 0.8`
- `top_k: 40`
- `repetition_penalty: 1.1`
- `enable_thinking: false`
- `hide_thoughts: true`
- `renderer_mode: qt_web`

### 5.4 Dependency Baseline

`requirements.txt` currently includes:
- `torch==2.10.0.dev20251016+cu129`
- transformers from `main`
- `accelerate>=1.10.0`
- `huggingface-hub>=1.3.0,<2.0`
- PySide6 + Addons
- FastAPI + Uvicorn + Authlib

Practical note:
- Repo has recently been operated with newer nightly CUDA stack (cu130) in active venv.
- `requirements.txt` pin and live venv can diverge; this needs reconciliation to avoid reproducibility drift.

---

## 6) Prompting and Persona Layer

### 6.1 Prompt Loader

File: `wrap.py`

Resolution order:
1. `system_prompt.json`
2. fallback `system_prompt.txt`
3. hardcoded fallback default

`system_prompt.json` is rendered into one assembled system prompt with sections:
- persona
- core behavior
- math protocol
- formatting rules
- default mode
- few-shot examples

### 6.2 Current Persona Direction

Current `system_prompt.json` has been shifted toward:
- Athena sovereign identity,
- Neohm creator acknowledgment,
- high factual discipline,
- math-first structured answers,
- 10 few-shot behavior examples.

### 6.3 Thinking Mode Mechanics

There are two separate concepts:
- Model-side thinking flag (`enable_thinking`) passed through chat templates where supported.
- UI-side thought visibility (`hide_thoughts` / show-thoughts toggle).

`wrap.ThinkStripper` is used to suppress `<think>...</think>` spans in outputs when configured.

---

## 7) Finetune Pipeline: What Exists and What Was Done

### 7.1 Current Training Entrypoints

- `Finetune/train_fast_sft.ps1`  
  One-step wrapper that calls `run_training.ps1` with `fast_sft.json`.

- `Finetune/run_training.ps1`  
  Args-file driven orchestrator with preflight checks.

- `Finetune/train.py`  
  Compact SFT trainer using Transformers `Trainer`.

### 7.2 Current Fast Config (AIMO)

File: `Finetune/fast_sft.json`

Key values:
- `model_path`: `models/Qwen3-1.7B`
- `train_file`: `Finetune/aimo_sft_final.jsonl`
- `output_dir`: `models/tuned/AthenaV8_AIMO_fast`
- `expected_samples`: `207`
- `max_seq_length`: `2048`
- `batch_size`: 1
- `grad_accumulation`: 8
- `learning_rate`: `3e-6`
- `epochs`: `2.0`
- `scheduler`: `constant_with_warmup`
- `save_steps`: 20
- `save_only_model`: true
- `bf16`: true
- `gradient_checkpointing`: true

### 7.3 Dataset Compliance Snapshot

File: `Finetune/aimo_sft_final.jsonl`

Observed stats:
- Samples: 207
- Bad JSON lines: 0
- Structure: each sample has exactly one `messages` array
- Messages per sample: 3
- Roles per sample: `system`, `user`, `assistant` (exactly one each)

Role totals:
- `system`: 207
- `user`: 207
- `assistant`: 207

### 7.4 Trainer Behavior (train.py)

Key implementation details:
- Validates message roles (`system/user/assistant`) and non-empty content.
- Uses tokenizer chat template as canonical rendering.
- Creates assistant-only loss mask (`labels=-100` except assistant token spans).
- Reports token-length distribution and truncation count.
- Optional strict mode: fail if any sample exceeds `max_seq_length`.
- Supports checkpoint resume and gradient checkpointing.

### 7.5 Finetune Prep Utility

`prepare_data.py` converts turn-level dialogue JSONL into training artifacts:
- `dialogue` style (full dialogue)
- `assistant_turn` style (windowed supervised target turns)

Features:
- role mapping (teacher/student -> user/assistant)
- optional role-prefix stripping
- optional merge of consecutive same-role messages
- optional user-before-assistant enforcement

### 7.6 Existing Tuned Outputs

Under `models/tuned/`:
- `AthenaV7.03_recover` (full model artifacts)
- `AthenaV8_AIMO_fast` (full model artifacts + checkpoints)

This confirms at least two successful tuned export directories exist.

---

## 8) Capability Matrix (Current State)

### 8.1 Working Now

- Local desktop chat launch via one command.
- Qt transcript streaming with Markdown + LaTeX.
- Image input in local UI (clipboard/file) for vision-capable models.
- Portal auth login, session handling, and per-user folder creation.
- Portal SSE streaming and status handling.
- Portal image attach/paste + upload + transcript display.
- Raw message copy and code-block copy controls in portal and desktop transcript shell.
- NDJSON event logging with request lifecycle.
- Fast SFT training path with args file and GPU preflight checks.

### 8.2 Partial / Transitional

- Requirements pin vs active CUDA nightly runtime alignment (cu129 pin vs cu130 usage).
- Tk fallback UX still carries older startup/system verbosity patterns.
- `run_ui.ps1` references `scripts/bootstrap_mathjax.ps1`, but `scripts/` directory is absent in this snapshot.

### 8.3 Not Implemented Yet (Explicitly Planned)

- Native tool-execution router in inference loop (python/sympy/numpy).
- Plan -> Act -> Verify agent loop.
- Persistent structured session memory retrieval for reasoning.
- Multi-agent SWARM execution layer.
- AIMO submission automation integrated with evaluation harness.

---

## 9) Proposed Tool-Calling Architecture (AIMO-Oriented)

Goal: move from text imitation to **verified computation**.

### 9.1 Design Principles

1. Tool calls must be executable and auditable.
2. Every tool result must be linked to a model claim.
3. Final answer should include verification trace.
4. Tool failures must degrade safely (retry/fallback, never silent hallucination).

### 9.2 Minimal Tool Set (v1)

1. `calculator`
- deterministic arithmetic and numeric expression evaluation.

2. `sympy_solver`
- equation solving, symbolic simplification, factorization, polynomial checks.

3. `mod_arith`
- modular exponentiation, inverses, CRT helper for olympiad number theory.

4. `combinatorics_helper`
- exact binomial/multinomial/stirling computations with overflow-safe integer arithmetic.

### 9.3 Tool Contract (JSON)

Proposed call schema:
```json
{
  "tool": "sympy_solver",
  "input": {"expr": "solve(x**2-5*x+6, x)"},
  "reason": "Need exact roots to avoid arithmetic slip"
}
```

Tool result schema:
```json
{
  "ok": true,
  "tool": "sympy_solver",
  "output": "[2, 3]",
  "runtime_ms": 5,
  "error": ""
}
```

### 9.4 Verification Trace Policy

Assistant final format should include:
1. short derivation,
2. tool trace block:
   - tool input
   - tool output
   - interpretation,
3. final boxed answer.

---

## 10) Proposed SWARM Architecture for AIMO

Objective: maximize correctness under small-model constraints by decomposition and consensus.

### 10.1 Agent Roles

1. **Router Agent**
- Classifies problem domain:
  - Number Theory
  - Algebra
  - Combinatorics
  - Geometry
  - Mixed

2. **Domain Solver Agents**
- One specialized model per domain (SFT-biased dataset).
- Produce candidate solution + confidence + tool requests.

3. **Verifier Agent**
- Cross-checks each candidate with tools.
- Flags broken assumptions or algebraic slips.

4. **Judge Agent**
- Aggregates candidates/verifications.
- Selects final answer and emits rationale.

### 10.2 Message Protocol (Internal)

Common packet:
```json
{
  "problem_id": "aimo_xx",
  "domain": "number_theory",
  "prompt": "...",
  "candidate_answer": "...",
  "proof_outline": "...",
  "tool_trace": [],
  "confidence": 0.0
}
```

### 10.3 Execution Graph

1. Router -> top-2 domains (not only top-1, to reduce misrouting risk)
2. Parallel solver generation (domain-specific prompts)
3. Verifier tool pass on each candidate
4. Judge chooses:
   - majority-consistent answer OR
   - highest verification score answer OR
   - abstain/retry branch if inconsistent

### 10.4 Compute Strategy

- Use 2B specialists for fast breadth.
- Use 4B (or strongest local) as judge/verifier when latency permits.
- Cache repeated tool evaluations across candidates.

### 10.5 Failure-Mode Handling

Common failures:
- wrong domain route,
- symbolic simplification error,
- modular arithmetic slip,
- confidence inflation without proof.

Countermeasures:
- dual-route top-2 domain dispatch,
- mandatory verifier pass for finalization,
- confidence calibration with verification score,
- auto-retry with alternative prompting if verifier rejects.

---

## 11) AIMO Pipeline Blueprint (End-to-End)

### 11.1 Offline Loop

1. Curate domain datasets (strict quality over volume).
2. Train domain specialists.
3. Run benchmark suite:
   - known olympiad sets,
   - synthetic adversarial checks,
   - format compliance checks.
4. Measure:
   - exact-match accuracy,
   - tool verification pass rate,
   - hallucination/error taxonomy.

### 11.2 Online Inference Loop

1. Receive problem.
2. Route -> parallel specialists.
3. Verify candidates with tools.
4. Judge final answer.
5. Emit answer in strict target format (AIMO output constraints).

### 11.3 Submission Automation (Recommended)

Build a deterministic script that:
- ingests all 50 test problems,
- runs swarm inference per problem,
- writes exactly one CSV output format expected by Kaggle/AIMO,
- fills unsolved with sentinel policy (explicit and consistent),
- logs per-problem reasoning metadata separately.

---

## 12) Risks and Debt Register

1. **Environment reproducibility risk**  
   Requirements pin and active CUDA nightly stack may diverge.

2. **Prompt drift risk**  
   Frequent persona changes can hurt math consistency if not benchmark-gated.

3. **Data leakage/privacy risk**  
   Raw per-user logs include prompt/response content by design.

4. **Tooling gap risk**  
   Without execution-verified tool calls, model can still produce confident nonsense.

5. **UI parity risk**  
   Desktop and portal are separate stacks; behavior can drift without shared test suite.

6. **Missing script references**  
   `run_ui.ps1` references `scripts/bootstrap_mathjax.ps1` but `scripts/` folder is absent in this snapshot.

---

## 13) Recommended Next Steps (Research-Ready)

### Immediate (0-1 day)

1. Freeze environment manifest (exact pip freeze for working venv).
2. Add one reproducibility doc for GPU/runtime setup.
3. Implement tool router v1 with `calculator` + `sympy_solver`.
4. Add verifier policy to final answer path.

### Short-term (1-3 days)

1. Train 2B domain specialists (NT/ALG/COMB/GEO) with clean splits.
2. Implement router + judge orchestration harness.
3. Build internal evaluation board with per-domain metrics and failure taxonomy.

### Mid-term (3-7 days)

1. Integrate full SWARM flow into a single CLI or service endpoint.
2. Add Kaggle-ready submission generator.
3. Run ablations:
   - single model vs swarm,
   - no-tools vs tools,
   - top-1 route vs top-2 route.

---

## 14) Operational Commands (Canonical)

Desktop UI:
```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_ui.ps1
```

Portal local:
```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_portal.ps1 -LoadModel
```

Portal full stack:
```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_portal_v5.ps1
```

Fast SFT:
```powershell
Set-Location D:\AthenaPlayground\AthenaV5\Finetune
.\train_fast_sft.ps1
```

---

## 15) Final Notes for Research Agent

If the objective is "win AIMO," the strategic bottleneck is now:
- not basic UI/infra,
- not single-model prompting,
- but **verified multi-agent reasoning orchestration** with strong data hygiene.

This repository already has enough stable substrate (desktop + portal + SFT + logging + auth + multimodal) to support a serious SWARM experiment.
The next gains come from:
1. strict tool-backed correctness,
2. domain-specialized model roles,
3. robust judge/verifier consensus,
4. reproducible evaluation-to-submission pipeline.
