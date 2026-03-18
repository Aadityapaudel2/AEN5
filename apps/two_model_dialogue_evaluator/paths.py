from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
CONFIG_DIR = APP_DIR / "config"
LOGS_DIR = APP_DIR / "logs"
BUILD_DIR = APP_DIR / "build"
DIST_DIR = APP_DIR / "dist"
MODEL_PROFILES_DIR = CONFIG_DIR / "model_profiles"

RUNTIME_CONFIG_PATH = CONFIG_DIR / "runtime.json"
SESSION_STATE_PATH = CONFIG_DIR / "session_state.json"
SESSION_STATE_EXAMPLE_PATH = CONFIG_DIR / "session_state.example.json"
SYSTEM_PROMPT_DEFAULT_PATH = CONFIG_DIR / "system_prompt_default.txt"
SYSTEM_PROMPT_A_PATH = CONFIG_DIR / "system_prompt_a.txt"
SYSTEM_PROMPT_B_PATH = CONFIG_DIR / "system_prompt_b.txt"
SYSTEM_PROMPT_A_EXAMPLE_PATH = CONFIG_DIR / "system_prompt_a.example.txt"
SYSTEM_PROMPT_B_EXAMPLE_PATH = CONFIG_DIR / "system_prompt_b.example.txt"
TOOL_BEHAVIOR_PRIMER_PATH = CONFIG_DIR / "tool_behavior_primer.txt"

RUNTIME_CONFIG_DEFAULTS: dict[str, object] = {
    "temperature": 0.7,
    "max_new_tokens": 32000,
    "top_p": 0.8,
    "top_k": 20,
    "repetition_penalty": 1.0,
    "tools_enabled": False,
}

SESSION_STATE_DEFAULTS: dict[str, object] = {
    "name_a": "",
    "name_b": "",
    "model_a_path": "",
    "model_b_path": "",
    "profile_a_path": "",
    "profile_b_path": "",
    "turn_limit": 12,
    "tools_enabled": False,
}

DEFAULT_MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "qwen35_4b_solver.json": {
        "profile_name": "Qwen 4B Solver",
        "display_name": "Solver",
        "description": "Direct mathematical solver profile for structured problem solving.",
        "system_prompt": (
            "You are a mathematical solver. Work directly toward the answer, keep reasoning coherent, "
            "and use exact arithmetic or checking tools when precision matters."
        ),
        "generation": {
            "temperature": 0.25,
            "max_new_tokens": 2048,
            "top_p": 0.9,
            "top_k": 20,
            "repetition_penalty": 1.02,
        },
    },
    "qwen35_4b_verifier.json": {
        "profile_name": "Qwen 4B Verifier",
        "display_name": "Verifier",
        "description": "Skeptical verifier profile that pressures for correctness and gap detection.",
        "system_prompt": (
            "You are a mathematical verifier. Examine claims for hidden assumptions, missing cases, "
            "weak justification, and arithmetic error. Ask the shortest correction-focused question needed."
        ),
        "generation": {
            "temperature": 0.15,
            "max_new_tokens": 1024,
            "top_p": 0.85,
            "top_k": 20,
            "repetition_penalty": 1.05,
        },
    },
    "qwen35_4b_public.json": {
        "profile_name": "Qwen 4B Public",
        "display_name": "Assistant",
        "description": "General public-facing structured reasoning profile.",
        "system_prompt": (
            "You are a precise reasoning assistant. Answer clearly, keep claims verifiable, "
            "and prefer direct structured explanations over style."
        ),
        "generation": {
            "temperature": 0.55,
            "max_new_tokens": 1536,
            "top_p": 0.9,
            "top_k": 20,
            "repetition_penalty": 1.0,
        },
    },
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


def _copy_if_missing(target: Path, source: Path, fallback: str = "") -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        text = source.read_text(encoding="utf-8-sig")
    else:
        text = fallback
    target.write_text(text.rstrip() + "\n" if text.strip() else "", encoding="utf-8")


def ensure_app_layout() -> None:
    for path in (CONFIG_DIR, LOGS_DIR, BUILD_DIR, DIST_DIR, MODEL_PROFILES_DIR):
        path.mkdir(parents=True, exist_ok=True)
    _copy_if_missing(SYSTEM_PROMPT_A_PATH, SYSTEM_PROMPT_A_EXAMPLE_PATH)
    _copy_if_missing(SYSTEM_PROMPT_B_PATH, SYSTEM_PROMPT_B_EXAMPLE_PATH)
    if not SESSION_STATE_PATH.exists():
        seed = _read_json_object(SESSION_STATE_EXAMPLE_PATH) or dict(SESSION_STATE_DEFAULTS)
        _write_json_object(SESSION_STATE_PATH, seed)
    for filename, payload in DEFAULT_MODEL_PROFILES.items():
        profile_path = MODEL_PROFILES_DIR / filename
        if not profile_path.exists():
            _write_json_object(profile_path, payload)


def get_app_dir() -> Path:
    ensure_app_layout()
    return APP_DIR


def get_runtime_config_path() -> Path:
    ensure_app_layout()
    return RUNTIME_CONFIG_PATH


def get_runtime_config() -> dict[str, Any]:
    ensure_app_layout()
    data = dict(RUNTIME_CONFIG_DEFAULTS)
    data.update(_read_json_object(RUNTIME_CONFIG_PATH))
    data["temperature"] = float(data.get("temperature", RUNTIME_CONFIG_DEFAULTS["temperature"]))
    data["max_new_tokens"] = int(data.get("max_new_tokens", RUNTIME_CONFIG_DEFAULTS["max_new_tokens"]))
    data["top_p"] = float(data.get("top_p", RUNTIME_CONFIG_DEFAULTS["top_p"]))
    data["top_k"] = int(data.get("top_k", RUNTIME_CONFIG_DEFAULTS["top_k"]))
    data["repetition_penalty"] = float(
        data.get("repetition_penalty", RUNTIME_CONFIG_DEFAULTS["repetition_penalty"])
    )
    data["tools_enabled"] = bool(data.get("tools_enabled", RUNTIME_CONFIG_DEFAULTS["tools_enabled"]))
    return data


def get_tools_enabled_default() -> bool:
    return bool(get_runtime_config()["tools_enabled"])


def get_logs_dir() -> Path:
    ensure_app_layout()
    return LOGS_DIR


def get_model_profiles_dir() -> Path:
    ensure_app_layout()
    return MODEL_PROFILES_DIR

def get_session_state_path() -> Path:
    ensure_app_layout()
    return SESSION_STATE_PATH


def load_session_state() -> dict[str, Any]:
    ensure_app_layout()
    data = dict(SESSION_STATE_DEFAULTS)
    data.update(_read_json_object(SESSION_STATE_PATH))
    data["turn_limit"] = int(data.get("turn_limit", SESSION_STATE_DEFAULTS["turn_limit"]))
    data["tools_enabled"] = bool(data.get("tools_enabled", SESSION_STATE_DEFAULTS["tools_enabled"]))
    for key in ("name_a", "name_b", "model_a_path", "model_b_path", "profile_a_path", "profile_b_path"):
        data[key] = str(data.get(key, SESSION_STATE_DEFAULTS.get(key, ""))).strip()
    return data


def save_session_state(updates: dict[str, Any]) -> dict[str, Any]:
    state = load_session_state()
    state.update(updates)
    _write_json_object(SESSION_STATE_PATH, state)
    return state


def get_system_prompt_default_path() -> Path:
    ensure_app_layout()
    return SYSTEM_PROMPT_DEFAULT_PATH


def get_tool_behavior_primer_path() -> Path:
    ensure_app_layout()
    return TOOL_BEHAVIOR_PRIMER_PATH


def get_system_prompt_path(side: str) -> Path:
    ensure_app_layout()
    return SYSTEM_PROMPT_A_PATH if side == "left" else SYSTEM_PROMPT_B_PATH


def get_system_prompt_example_path(side: str) -> Path:
    return SYSTEM_PROMPT_A_EXAMPLE_PATH if side == "left" else SYSTEM_PROMPT_B_EXAMPLE_PATH


def load_system_prompt_text(side: str) -> str:
    ensure_app_layout()
    path = get_system_prompt_path(side)
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return ""


def save_system_prompt_text(side: str, text: str) -> None:
    ensure_app_layout()
    path = get_system_prompt_path(side)
    content = (text or "").rstrip()
    path.write_text((content + "\n") if content else "", encoding="utf-8")


def load_model_profile(path: Path) -> dict[str, Any]:
    ensure_app_layout()
    raw = _read_json_object(path)
    profile: dict[str, Any] = {
        "profile_name": str(raw.get("profile_name") or path.stem).strip() or path.stem,
        "display_name": str(raw.get("display_name") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
        "system_prompt": str(raw.get("system_prompt") or "").strip(),
        "model_path": str(raw.get("model_path") or "").strip(),
        "tools_enabled": raw.get("tools_enabled"),
        "generation": {},
    }
    generation = raw.get("generation")
    if isinstance(generation, dict):
        merged = dict(RUNTIME_CONFIG_DEFAULTS)
        merged.update(generation)
        profile["generation"] = {
            "temperature": float(merged.get("temperature", RUNTIME_CONFIG_DEFAULTS["temperature"])),
            "max_new_tokens": int(merged.get("max_new_tokens", RUNTIME_CONFIG_DEFAULTS["max_new_tokens"])),
            "top_p": float(merged.get("top_p", RUNTIME_CONFIG_DEFAULTS["top_p"])),
            "top_k": int(merged.get("top_k", RUNTIME_CONFIG_DEFAULTS["top_k"])),
            "repetition_penalty": float(
                merged.get("repetition_penalty", RUNTIME_CONFIG_DEFAULTS["repetition_penalty"])
            ),
        }
    return profile
