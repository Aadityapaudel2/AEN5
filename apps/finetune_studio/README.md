# Finetune Studio

`Finetune Studio` is the desktop control surface for the local AthenaV5 finetuning pipeline.

It provides five operator tabs:

- `Overview`: quick workflow guidance, environment summary, recent runs, and run details
- `Compose`: build or append train-ready user/assistant rows
- `Data`: import an existing train-ready JSONL file and review the required format
- `Arguments`: operator-facing profiles, direct finetune-args loading, and fully editable finetune arguments
- `Jobs`: preflight, launch, live logs, and cancel controls

## Run

If the active environment does not already include PySide6:

```powershell
python -m pip install -r .\apps\finetune_studio\requirements.txt
```

Then, from `AthenaV5`:

```powershell
.\apps\finetune_studio\run.ps1
```

Or directly as a module:

```powershell
python -m apps.finetune_studio
```

## Notes

- The UI is a PySide6 app that runs from source.
- Training still executes through `Finetune/train.py` via `accelerate`.
- The cross-platform backend lives under `Finetune/studio_backend/`.
- Session state, logs, and other mutable studio files are stored in a user-local app data directory by default.
- Set `AEN_FINETUNE_STUDIO_HOME` if you want to override that storage root explicitly.
- When training launches, the studio writes `FINETUNE_ARGS.json`, `FINETUNE_CARD.md`, a transcript log, and `_finetune_source/` snapshots for that run.
