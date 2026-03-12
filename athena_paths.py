from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MODELS_DIR = ROOT_DIR / "models"
DEFAULT_MODEL_NAME = "Qwen3.5-4B"
EXTERNAL_MODELS_DIR = ROOT_DIR.parent / "models"

GUI_CONFIG_PATH = ROOT_DIR / "gui_config.json"


def get_default_chat_model_dir() -> Path:
    """Canonical model path for chat runtimes."""
    override = (os.getenv("ATHENA_MODEL_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_candidate = MODELS_DIR / DEFAULT_MODEL_NAME
    if local_candidate.exists():
        return local_candidate.resolve()
    external_candidate = EXTERNAL_MODELS_DIR / DEFAULT_MODEL_NAME
    return external_candidate.resolve()
