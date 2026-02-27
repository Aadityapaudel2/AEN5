# Athena V5 Workspace

`AthenaV5/` contains local finetuning scripts and a local Qt/Tk chat UI for Qwen checkpoints.

## Layout
- `Finetune/prepare_data.py`: converts turn-level JSONL into conversation-level SFT JSONL.
- `Finetune/train.py`: supervised finetuning trainer.
- `Finetune/run_training.ps1`: canonical finetuning entrypoint.
- `qt_ui.py`: primary Qt UI (Markdown + LaTeX + emoji), static ASCII avatar panel.
- `ui.py`: legacy Tk fallback UI.
- `run_ui.ps1`: canonical UI launcher.
- `tk_chat.py`: model loading + generation settings.
- `athena_paths.py`: default model path selection.

## Environment
```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

## Canonical Commands
Prepare data:
```powershell
python .\Finetune\prepare_data.py
```

Run finetuning:
```powershell
. .\Finetune\run_training.ps1
```

Run UI (Qt default):
```powershell
.\run_ui.ps1
```

Run legacy Tk UI:
```powershell
.\run_ui.ps1 -LegacyTk
```

Run web portal (smoke mode by default; no model load):
```powershell
.\run_portal.ps1
```

Run web portal with live model:
```powershell
.\run_portal.ps1 -LoadModel
```

Run portal + tunnel together (single command):
```powershell
.\run_portal_v5.ps1
```

## UI Notes
- Avatar is intentionally minimal and static ASCII (`[^_^]`) for stability.
- No anime/avatar bundle pipeline is used.
- `run_ui.ps1` auto-checks Qt dependencies and falls back to Tk if Qt cannot start.
- Offline MathJax path: `assets/mathjax/es5/tex-mml-chtml.js`.

## Launcher Flags
- `-ModelDir <path>`: override model directory for this run.
- `-LegacyTk`: force Tk UI.
- `-NoAutoInstallDeps`: disable first-run pip bootstrap.
- `-NoMathJaxBootstrap`: skip local MathJax bootstrap attempt.
- `-BootstrapVerbose`: print detailed bootstrap diagnostics.

## Smoke Check
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_ui.ps1
```

Portal smoke check:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_portal.ps1
```

## Portal Notes
- FastAPI portal entrypoint is `portal_server.py`, mounted at `/AthenaV5` by default.
- Cloudflare helper for `portal.neohmlabs.com`: `.\cloudflared_athenav5.ps1`.
- One-shot launcher (server + tunnel): `.\run_portal_v5.ps1`.
- Full portal docs: `portal/README.md`.

## Cleanup Note
Legacy avatar rig/bundle stack was removed from active runtime in favor of a deterministic ASCII-only side panel.
