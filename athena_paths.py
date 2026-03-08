from __future__ import annotations

import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

CHAT_MODEL_DIR = Path(r"D:\AthenaPlayground\AthenaV5\models\tuned\NeohmIdentityV2_fast")
BASE_CHAT_MODEL_DIR = ROOT_DIR / "models" / "Qwen3.5-2B"
PROJECT_TUNED_MODELS_DIR = ROOT_DIR / "models" / "tuned"
FUTURE_TUNED_MODELS_ROOT = Path(r"N:\AthenaModels\tuned")
GUI_CONFIG_PATH = ROOT_DIR / "gui_config.json"
SYSTEM_PROMPT_FILE = ROOT_DIR / "system_prompt.json"
TOOL_BEHAVIOR_PRIMER_FILE = ROOT_DIR / "tool_behavior_primer.txt"
COHERENCE_ABLATION_SET_FILE = ROOT_DIR / "coherence_ablation_set.md"
COHERENCE_ABLATION_YAML_FILE = ROOT_DIR / "coherence_ablation_set.yaml"

DATA_DIR = ROOT_DIR / "data"
LOG_ROOT = DATA_DIR / "users"
DESKTOP_IMAGE_STAGE_DIR = DATA_DIR / "desktop_images"
COMPARE_RUNS_DIR = DATA_DIR / "compare_runs"

DESKTOP_APP_DIR = ROOT_DIR / "desktop_app"
DESKTOP_ASSETS_DIR = DESKTOP_APP_DIR / "assets"
DESKTOP_TRANSCRIPT_HTML = DESKTOP_ASSETS_DIR / "transcript.html"

BROWSER_ROOT = ROOT_DIR / "browser"
PORTAL_DIR = BROWSER_ROOT / "portal"
PORTAL_TEMPLATES_DIR = PORTAL_DIR / "templates"
PORTAL_STATIC_DIR = PORTAL_DIR / "static"

PORTAL_PATH_PREFIX = "/AthenaV5"
PORTAL_PORT = 8000
PORTAL_HOSTS = {"dev": "127.0.0.1", "prod": "0.0.0.0"}
AUTH_REQUIRED = {"dev": False, "prod": True}
TOOLS_ENABLED_DEFAULT = False
GUI_CONFIG_DEFAULTS = {
    "temperature": 0.7,
    "max_new_tokens": 32000,
    "top_p": 0.8,
    "top_k": 20,
    "repetition_penalty": 1.0,
    "tools_enabled": TOOLS_ENABLED_DEFAULT,
    "enable_thinking": False,
    "hide_thoughts": True,
    "renderer_mode": "qt_web",
    "render_throttle_ms": 75,
}


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def _normalize_mode(mode: str) -> str:
    return "prod" if (mode or "").strip().lower() == "prod" else "dev"


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _safe_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _read_json_object(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def get_root_dir() -> Path:
    return _resolve(ROOT_DIR)


def get_default_chat_model_dir() -> Path:
    return _resolve(CHAT_MODEL_DIR)


def get_base_chat_model_dir() -> Path:
    return _resolve(BASE_CHAT_MODEL_DIR)


def get_project_tuned_models_dir() -> Path:
    return _resolve(PROJECT_TUNED_MODELS_DIR)


def get_future_tuned_models_root() -> Path:
    raw = _env("ATHENA_TUNED_MODELS_ROOT")
    return _resolve(Path(raw)) if raw else _resolve(FUTURE_TUNED_MODELS_ROOT)


def get_gui_config_path() -> Path:
    return _resolve(GUI_CONFIG_PATH)


def get_system_prompt_path() -> Path:
    return _resolve(SYSTEM_PROMPT_FILE)


def get_tool_behavior_primer_path() -> Path:
    return _resolve(TOOL_BEHAVIOR_PRIMER_FILE)


def get_coherence_ablation_set_path() -> Path:
    return _resolve(COHERENCE_ABLATION_SET_FILE)


def get_coherence_ablation_yaml_path() -> Path:
    return _resolve(COHERENCE_ABLATION_YAML_FILE)


def get_data_dir() -> Path:
    return _resolve(DATA_DIR)


def get_log_root() -> Path:
    raw = _env("ATHENA_LOG_ROOT")
    return _resolve(Path(raw)) if raw else _resolve(LOG_ROOT)


def get_desktop_image_stage_dir() -> Path:
    return _resolve(DESKTOP_IMAGE_STAGE_DIR)


def get_compare_runs_dir() -> Path:
    return _resolve(COMPARE_RUNS_DIR)


def get_desktop_assets_dir() -> Path:
    return _resolve(DESKTOP_ASSETS_DIR)


def get_desktop_transcript_html_path() -> Path:
    return _resolve(DESKTOP_TRANSCRIPT_HTML)


def get_browser_root() -> Path:
    return _resolve(BROWSER_ROOT)


def get_portal_dir() -> Path:
    return _resolve(PORTAL_DIR)


def get_portal_templates_dir() -> Path:
    return _resolve(PORTAL_TEMPLATES_DIR)


def get_portal_static_dir() -> Path:
    return _resolve(PORTAL_STATIC_DIR)


def get_gui_config() -> dict[str, object]:
    data = _read_json_object(get_gui_config_path())
    return {
        "temperature": float(data.get("temperature", GUI_CONFIG_DEFAULTS["temperature"])),
        "max_new_tokens": max(1, int(data.get("max_new_tokens", GUI_CONFIG_DEFAULTS["max_new_tokens"]))),
        "top_p": float(data.get("top_p", GUI_CONFIG_DEFAULTS["top_p"])),
        "top_k": int(data.get("top_k", GUI_CONFIG_DEFAULTS["top_k"])),
        "repetition_penalty": float(data.get("repetition_penalty", GUI_CONFIG_DEFAULTS["repetition_penalty"])),
        "tools_enabled": _safe_bool(data.get("tools_enabled"), bool(GUI_CONFIG_DEFAULTS["tools_enabled"])),
        "enable_thinking": _safe_bool(data.get("enable_thinking"), bool(GUI_CONFIG_DEFAULTS["enable_thinking"])),
        "hide_thoughts": _safe_bool(data.get("hide_thoughts"), bool(GUI_CONFIG_DEFAULTS["hide_thoughts"])),
        "renderer_mode": str(data.get("renderer_mode", GUI_CONFIG_DEFAULTS["renderer_mode"]) or GUI_CONFIG_DEFAULTS["renderer_mode"]),
        "render_throttle_ms": max(1, int(data.get("render_throttle_ms", GUI_CONFIG_DEFAULTS["render_throttle_ms"]))),
    }


def get_path_prefix() -> str:
    raw = _env("ATHENA_PORTAL_PATH_PREFIX") or PORTAL_PATH_PREFIX
    prefixed = raw if raw.startswith("/") else f"/{raw}"
    return prefixed.rstrip("/") or PORTAL_PATH_PREFIX


def get_portal_port() -> int:
    return _env_int("ATHENA_PORTAL_PORT", PORTAL_PORT)


def get_portal_host(mode: str) -> str:
    normalized = _normalize_mode(mode)
    return _env("ATHENA_PORTAL_HOST") or PORTAL_HOSTS[normalized]


def get_auth_required(mode: str) -> bool:
    normalized = _normalize_mode(mode)
    return _env_bool("ATHENA_AUTH_REQUIRED", AUTH_REQUIRED[normalized])


def get_tools_enabled_default() -> bool:
    return bool(get_gui_config()["tools_enabled"])
