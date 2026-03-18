from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _detect_root_dir() -> Path:
    env_root = (os.getenv("ATHENA_ROOT_DIR") or "").strip()
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if candidate.exists():
            return candidate

    candidates: list[Path] = [Path(__file__).resolve().parent]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)

    for base in list(candidates):
        candidates.extend(base.parents)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "athena_paths.py").exists():
            return candidate
        if (candidate / "browser").exists() and (candidate / "Finetune").exists() and (candidate / "models").exists():
            return candidate

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT_DIR = _detect_root_dir()

EXCLUSIVE_ROOT = ROOT_DIR / "exclusive"
EXCLUSIVE_MODEL_DIR = EXCLUSIVE_ROOT / "AthenaV1"
EXCLUSIVE_CONFIG_DIR = EXCLUSIVE_ROOT / "config"
EXCLUSIVE_LOG_ROOT = EXCLUSIVE_ROOT / "logs"
EXCLUSIVE_DATA_DIR = EXCLUSIVE_ROOT / "data"
EXCLUSIVE_DESKTOP_IMAGE_STAGE_DIR = EXCLUSIVE_DATA_DIR / "desktop_images"
EXCLUSIVE_DESKTOP_APP_DIR = EXCLUSIVE_ROOT / "desktop_app"
EXCLUSIVE_DESKTOP_ASSETS_DIR = EXCLUSIVE_DESKTOP_APP_DIR / "assets"
EXCLUSIVE_DESKTOP_TRANSCRIPT_HTML = EXCLUSIVE_DESKTOP_ASSETS_DIR / "transcript.html"

CHAT_MODEL_DIR = ROOT_DIR / "models" / "Qwen3.5-4B"
BASE_CHAT_MODEL_DIR = ROOT_DIR / "models" / "Qwen3.5-2B"
ORCHESTRATOR_MODEL_DIR = ROOT_DIR / "models" / "Qwen3.5-4B"
PROJECT_TUNED_MODELS_DIR = ROOT_DIR / "models" / "tuned"
FUTURE_TUNED_MODELS_ROOT = Path(r"N:\AthenaModels\tuned")
BROWSER_ROOT = ROOT_DIR / "browser"
BROWSER_CONFIG_DIR = BROWSER_ROOT / "config"
ENGINE_CONFIG_DIR = ROOT_DIR / "desktop_engine" / "config"
GUI_CONFIG_PATH = BROWSER_CONFIG_DIR / "gui_config.json"
ATHENA_GUI_CONFIG_PATH = ROOT_DIR / "athena_gui_config.json"
SYSTEM_PROMPT_FILE = BROWSER_CONFIG_DIR / "system_prompt.json"
ATHENA_SYSTEM_PROMPT_FILE = ROOT_DIR / "athena_system_prompt.json"
TOOL_BEHAVIOR_PRIMER_FILE = ENGINE_CONFIG_DIR / "tool_behavior_primer.txt"
COHERENCE_ABLATION_SET_FILE = ROOT_DIR / "research" / "source_notes" / "coherence_ablation_set.md"
COHERENCE_ABLATION_YAML_FILE = ROOT_DIR / "research" / "source_notes" / "coherence_ablation_set.yaml"

DATA_DIR = ROOT_DIR / "data"
LOG_ROOT = DATA_DIR / "users"
DESKTOP_IMAGE_STAGE_DIR = DATA_DIR / "desktop_images"
COMPARE_RUNS_DIR = DATA_DIR / "compare_runs"
EVALUATION_DIR = ROOT_DIR / "evaluation"
EVALUATION_TESTDATA_DIR = EVALUATION_DIR / "testdata"
EVALUATION_TESTS_DIR = EVALUATION_DIR / "tests"

FINETUNE_DIR = ROOT_DIR / "Finetune"
FINETUNE_PROMPTS_DIR = FINETUNE_DIR / "prompts"
TRAININGDATA_DIR = FINETUNE_DIR / "trainingdata"
ORCHESTRATOR_V1_DIR = TRAININGDATA_DIR / "orchestrator_v1"
ORCHESTRATOR_SCENARIO_CARDS_FILE = ORCHESTRATOR_V1_DIR / "scenario_cards.yaml"
ORCHESTRATOR_MANIFEST_FILE = ORCHESTRATOR_V1_DIR / "manifest.json"
ORCHESTRATOR_SEED_FILE = ORCHESTRATOR_V1_DIR / "orchestrator_seed.jsonl"
SOLVER_A_SEED_FILE = ORCHESTRATOR_V1_DIR / "solver_a_seed.jsonl"
SOLVER_B_SEED_FILE = ORCHESTRATOR_V1_DIR / "solver_b_seed.jsonl"
ORCHESTRATOR_CURATOR_PROMPT_FILE = FINETUNE_PROMPTS_DIR / "orchestrator_v1_curator_prompt.md"

PRIVATE_DESKTOP_SEED_DIR = ROOT_DIR / "archive" / "shared_archives" / "private_desktop_seed_2026-03"
DESKTOP_APP_DIR = PRIVATE_DESKTOP_SEED_DIR / "desktop_app"
DESKTOP_ASSETS_DIR = DESKTOP_APP_DIR / "assets"
DESKTOP_TRANSCRIPT_HTML = DESKTOP_ASSETS_DIR / "transcript.html"

PORTAL_DIR = BROWSER_ROOT / "portal"
PORTAL_TEMPLATES_DIR = PORTAL_DIR / "templates"
PORTAL_STATIC_DIR = PORTAL_DIR / "static"

PORTAL_PATH_PREFIX = "/AEN5"
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
    "no_repeat_ngram_size": 0,
    "tools_enabled": TOOLS_ENABLED_DEFAULT,
    "enable_thinking": False,
    "hide_thoughts": True,
    "renderer_mode": "qt_web",
    "render_throttle_ms": 75,
}


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def _same_path(left: Path, right: Path) -> bool:
    try:
        return _resolve(left) == _resolve(right)
    except Exception:
        return False


def _model_local_path(model_dir: Path | None, name: str) -> Path | None:
    if model_dir is None:
        return None
    candidate = _resolve(Path(model_dir) / name)
    return candidate if candidate.exists() else None


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


def _private_mode_enabled() -> bool:
    scope = _env("ATHENA_RUNTIME_SCOPE").lower()
    return _env_bool("ATHENA_PRIVATE_MODE", False) or scope == "private"


def _env_path(name: str) -> Path | None:
    raw = _env(name)
    if not raw:
        return None
    try:
        return _resolve(Path(raw))
    except Exception:
        return None


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
    explicit = _env_path("ATHENA_CHAT_MODEL_DIR")
    if explicit is not None:
        return explicit
    if _private_mode_enabled() and EXCLUSIVE_MODEL_DIR.is_dir():
        return _resolve(EXCLUSIVE_MODEL_DIR)
    return _resolve(CHAT_MODEL_DIR)


def get_base_chat_model_dir() -> Path:
    explicit = _env_path("ATHENA_BASE_CHAT_MODEL_DIR")
    return explicit if explicit is not None else _resolve(BASE_CHAT_MODEL_DIR)


def get_orchestrator_model_dir() -> Path:
    explicit = _env_path("ATHENA_ORCHESTRATOR_MODEL_DIR")
    return explicit if explicit is not None else _resolve(ORCHESTRATOR_MODEL_DIR)


def get_project_tuned_models_dir() -> Path:
    return _resolve(PROJECT_TUNED_MODELS_DIR)


def get_future_tuned_models_root() -> Path:
    raw = _env("ATHENA_TUNED_MODELS_ROOT")
    return _resolve(Path(raw)) if raw else _resolve(FUTURE_TUNED_MODELS_ROOT)


def get_gui_config_path(model_dir: Path | str | None = None) -> Path:
    explicit = _env_path("ATHENA_GUI_CONFIG_PATH")
    if explicit is not None:
        return explicit
    if _private_mode_enabled():
        private_cfg = _resolve(EXCLUSIVE_CONFIG_DIR / "gui_config.json")
        if private_cfg.exists():
            return private_cfg
    model_path = Path(model_dir).expanduser().resolve() if model_dir is not None else None
    for local_name in ("athena_gui_config.json", "gui_config.json"):
        candidate = _model_local_path(model_path, local_name)
        if candidate is not None:
            return candidate
    if model_path is not None and _same_path(model_path, CHAT_MODEL_DIR) and ATHENA_GUI_CONFIG_PATH.exists():
        return _resolve(ATHENA_GUI_CONFIG_PATH)
    return _resolve(GUI_CONFIG_PATH)


def get_system_prompt_path(model_dir: Path | str | None = None) -> Path:
    explicit = _env_path("ATHENA_SYSTEM_PROMPT_FILE")
    if explicit is not None:
        return explicit
    if _private_mode_enabled():
        private_prompt = _resolve(EXCLUSIVE_CONFIG_DIR / "system_prompt.json")
        if private_prompt.exists():
            return private_prompt
    model_path = Path(model_dir).expanduser().resolve() if model_dir is not None else None
    for local_name in ("athena_system_prompt.json", "system_prompt.json"):
        candidate = _model_local_path(model_path, local_name)
        if candidate is not None:
            return candidate
    if model_path is not None and _same_path(model_path, CHAT_MODEL_DIR) and ATHENA_SYSTEM_PROMPT_FILE.exists():
        return _resolve(ATHENA_SYSTEM_PROMPT_FILE)
    return _resolve(SYSTEM_PROMPT_FILE)


def get_tool_behavior_primer_path() -> Path:
    return _resolve(TOOL_BEHAVIOR_PRIMER_FILE)


def get_coherence_ablation_set_path() -> Path:
    return _resolve(COHERENCE_ABLATION_SET_FILE)


def get_coherence_ablation_yaml_path() -> Path:
    return _resolve(COHERENCE_ABLATION_YAML_FILE)


def get_data_dir() -> Path:
    return _resolve(DATA_DIR)


def get_evaluation_dir() -> Path:
    return _resolve(EVALUATION_DIR)


def get_evaluation_testdata_dir() -> Path:
    return _resolve(EVALUATION_TESTDATA_DIR)


def get_evaluation_tests_dir() -> Path:
    return _resolve(EVALUATION_TESTS_DIR)


def get_finetune_dir() -> Path:
    return _resolve(FINETUNE_DIR)


def get_finetune_prompts_dir() -> Path:
    return _resolve(FINETUNE_PROMPTS_DIR)


def get_trainingdata_dir() -> Path:
    return _resolve(TRAININGDATA_DIR)


def get_orchestrator_v1_dir() -> Path:
    return _resolve(ORCHESTRATOR_V1_DIR)


def get_orchestrator_scenario_cards_path() -> Path:
    return _resolve(ORCHESTRATOR_SCENARIO_CARDS_FILE)


def get_orchestrator_manifest_path() -> Path:
    return _resolve(ORCHESTRATOR_MANIFEST_FILE)


def get_orchestrator_seed_path() -> Path:
    return _resolve(ORCHESTRATOR_SEED_FILE)


def get_solver_a_seed_path() -> Path:
    return _resolve(SOLVER_A_SEED_FILE)


def get_solver_b_seed_path() -> Path:
    return _resolve(SOLVER_B_SEED_FILE)


def get_orchestrator_curator_prompt_path() -> Path:
    return _resolve(ORCHESTRATOR_CURATOR_PROMPT_FILE)


def get_log_root() -> Path:
    raw = _env("ATHENA_LOG_ROOT")
    if raw:
        return _resolve(Path(raw))
    if _private_mode_enabled() and EXCLUSIVE_LOG_ROOT.exists():
        return _resolve(EXCLUSIVE_LOG_ROOT)
    return _resolve(LOG_ROOT)


def get_desktop_image_stage_dir() -> Path:
    explicit = _env_path("ATHENA_DESKTOP_IMAGE_STAGE_DIR")
    if explicit is not None:
        return explicit
    if _private_mode_enabled():
        return _resolve(EXCLUSIVE_DESKTOP_IMAGE_STAGE_DIR)
    return _resolve(DESKTOP_IMAGE_STAGE_DIR)


def get_compare_runs_dir() -> Path:
    explicit = _env_path("ATHENA_COMPARE_RUNS_DIR")
    return explicit if explicit is not None else _resolve(COMPARE_RUNS_DIR)


def get_desktop_assets_dir() -> Path:
    explicit = _env_path("ATHENA_DESKTOP_ASSETS_DIR")
    if explicit is not None:
        return explicit
    if _private_mode_enabled() and EXCLUSIVE_DESKTOP_ASSETS_DIR.exists():
        return _resolve(EXCLUSIVE_DESKTOP_ASSETS_DIR)
    return _resolve(DESKTOP_ASSETS_DIR)


def get_desktop_transcript_html_path() -> Path:
    explicit = _env_path("ATHENA_DESKTOP_TRANSCRIPT_HTML")
    if explicit is not None:
        return explicit
    if _private_mode_enabled() and EXCLUSIVE_DESKTOP_TRANSCRIPT_HTML.exists():
        return _resolve(EXCLUSIVE_DESKTOP_TRANSCRIPT_HTML)
    return _resolve(DESKTOP_TRANSCRIPT_HTML)


def get_browser_root() -> Path:
    return _resolve(BROWSER_ROOT)


def get_browser_config_dir() -> Path:
    return _resolve(BROWSER_CONFIG_DIR)


def get_engine_config_dir() -> Path:
    return _resolve(ENGINE_CONFIG_DIR)


def get_portal_dir() -> Path:
    return _resolve(PORTAL_DIR)


def get_portal_templates_dir() -> Path:
    return _resolve(PORTAL_TEMPLATES_DIR)


def get_portal_static_dir() -> Path:
    return _resolve(PORTAL_STATIC_DIR)


def get_gui_config(model_dir: Path | str | None = None) -> dict[str, object]:
    data = _read_json_object(get_gui_config_path(model_dir))
    return {
        "temperature": float(data.get("temperature", GUI_CONFIG_DEFAULTS["temperature"])),
        "max_new_tokens": max(1, int(data.get("max_new_tokens", GUI_CONFIG_DEFAULTS["max_new_tokens"]))),
        "top_p": float(data.get("top_p", GUI_CONFIG_DEFAULTS["top_p"])),
        "top_k": int(data.get("top_k", GUI_CONFIG_DEFAULTS["top_k"])),
        "repetition_penalty": float(data.get("repetition_penalty", GUI_CONFIG_DEFAULTS["repetition_penalty"])),
        "no_repeat_ngram_size": max(0, int(data.get("no_repeat_ngram_size", GUI_CONFIG_DEFAULTS["no_repeat_ngram_size"]))),
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


def get_tools_enabled_default(model_dir: Path | str | None = None) -> bool:
    return bool(get_gui_config(model_dir)["tools_enabled"])
