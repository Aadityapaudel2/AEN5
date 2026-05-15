from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent


def _default_app_data_dir() -> Path:
    explicit = (os.getenv("AEN_FINETUNE_STUDIO_HOME") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    if os.name == "nt":
        base = (os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or "").strip()
        if base:
            return (Path(base) / "NeoHMLabs" / "AENFinetuneStudio").expanduser().resolve()

    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "NeoHMLabs" / "AENFinetuneStudio").resolve()

    xdg_state = (os.getenv("XDG_STATE_HOME") or "").strip()
    if xdg_state:
        return (Path(xdg_state) / "neohmlabs" / "aen_finetune_studio").expanduser().resolve()
    return (Path.home() / ".local" / "state" / "neohmlabs" / "aen_finetune_studio").resolve()


APP_DATA_DIR = _default_app_data_dir()
CONFIG_DIR = APP_DATA_DIR / "config"
LOGS_DIR = APP_DATA_DIR / "logs"
BUILD_DIR = APP_DATA_DIR / "build"
DIST_DIR = APP_DATA_DIR / "dist"

LEGACY_CONFIG_DIR = APP_DIR / "config"
LEGACY_SESSION_STATE_PATH = LEGACY_CONFIG_DIR / "session_state.json"

SESSION_STATE_PATH = CONFIG_DIR / "session_state.json"

SESSION_STATE_DEFAULTS: dict[str, Any] = {
    "selected_preset": "most_stable",
    "loaded_args_path": "",
    "input_mode": "train_ready_jsonl",
    "selected_train_file_path": "",
    "train_ready_path": "",
    "compose": {
        "output_path": "Finetune/trainingdata/manual_train_ready.jsonl",
        "system_instructions": "",
        "user_prompt": "",
        "assistant_prompt": "",
    },
    "prepare": {
        "input_path": "",
        "output_path": "",
        "assistant_role": "teacher",
        "artifact_style": "assistant_turn",
        "max_context_messages": 12,
        "min_messages": 2,
        "drop_empty": True,
        "require_user_before_assistant": True,
        "merge_consecutive_same_role": True,
        "strip_role_prefixes": True,
    },
    "build": {
        "builder_id": "verified_sft",
        "source": "Finetune/trainingdata/math_plus_logic_verified_sft.jsonl",
        "output": "Finetune/trainingdata/math_plus_logic_verified_sft_chunked4096.jsonl",
        "manifest_output": "Finetune/trainingdata/math_plus_logic_verified_sft_chunked4096_manifest.json",
        "model": "models/Qwen3.5-4B",
        "max_seq_length": 4096,
        "drop_overlong_base": False,
        "drop_unchunkable": False,
        "bootstrap": False,
        "overwrite_bootstrap": False,
        "write": True,
        "validate": True,
        "token_stats": False,
        "model_name_or_path": "models/Qwen3.5-4B",
        "orchestrator_max_seq_length": 2048,
    },
    "allow_cpu": False,
    "python_exe": "",
    "recent_run_meta_paths": [],
    "training_config": {},
}


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base))
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def ensure_app_layout() -> None:
    for path in (CONFIG_DIR, LOGS_DIR, BUILD_DIR, DIST_DIR):
        path.mkdir(parents=True, exist_ok=True)
    if (
        not SESSION_STATE_PATH.exists()
        and LEGACY_SESSION_STATE_PATH.exists()
        and LEGACY_SESSION_STATE_PATH.resolve() != SESSION_STATE_PATH.resolve()
    ):
        shutil.copy2(LEGACY_SESSION_STATE_PATH, SESSION_STATE_PATH)
    if not SESSION_STATE_PATH.exists():
        _write_json_object(SESSION_STATE_PATH, dict(SESSION_STATE_DEFAULTS))


def get_app_dir() -> Path:
    ensure_app_layout()
    return APP_DIR


def get_app_data_dir() -> Path:
    ensure_app_layout()
    return APP_DATA_DIR


def get_logs_dir() -> Path:
    ensure_app_layout()
    return LOGS_DIR


def get_session_state_path() -> Path:
    ensure_app_layout()
    return SESSION_STATE_PATH


def load_session_state() -> dict[str, Any]:
    ensure_app_layout()
    return _deep_merge(SESSION_STATE_DEFAULTS, _read_json_object(SESSION_STATE_PATH))


def save_session_state(updates: dict[str, Any]) -> dict[str, Any]:
    state = load_session_state()
    merged = _deep_merge(state, updates)
    _write_json_object(SESSION_STATE_PATH, merged)
    return merged
