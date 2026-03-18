# Two-Model Dialogue Evaluator

Standalone local GUI for side-by-side model comparison and controlled dialogue loops.

## Branch

Recommended branch name:

`feat/standalone-two-model-dialogue-evaluator`

## Setup

Create a Python environment inside this app folder or point `run.ps1` at an existing interpreter.

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\apps\two_model_dialogue_evaluator
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

## Launch

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\apps\two_model_dialogue_evaluator
.\run.ps1
```

## Local State

- `config/runtime.json`: generation defaults
- `config/system_prompt_a.txt`: editable local system instructions for Model A
- `config/system_prompt_b.txt`: editable local system instructions for Model B
- `config/session_state.json`: persisted UI state
- `logs/`: CSV outputs

Model folders are always browsed externally and are not bundled.

## Packaging

Optional standalone build:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5\apps\two_model_dialogue_evaluator
.\build_standalone.ps1
```
