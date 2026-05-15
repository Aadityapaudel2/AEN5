from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
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
PRIVATE_BASE_MULTIMODAL_MODEL_DIR = ROOT_DIR / "models" / "Qwen3.5-4B"
PRIVATE_VLLM_EXPORT_ROOT = ROOT_DIR / ".local" / "runtime" / "vllm_private_models"
AUTHORITATIVE_MODEL_ROUTES_FILE = ROOT_DIR / ".local" / "config" / "athena_model_routes.json"
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


def _route_defaults() -> dict[str, Path]:
    return {
        "private_model_dir": _resolve(EXCLUSIVE_MODEL_DIR),
        "public_model_dir": _resolve(CHAT_MODEL_DIR),
    }


def _read_authoritative_model_routes() -> dict[str, object]:
    return _read_json_object(AUTHORITATIVE_MODEL_ROUTES_FILE)


def _write_authoritative_model_routes(routes: dict[str, object]) -> None:
    AUTHORITATIVE_MODEL_ROUTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(routes)
    payload["version"] = 1
    payload["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    tmp_path = AUTHORITATIVE_MODEL_ROUTES_FILE.with_name(AUTHORITATIVE_MODEL_ROUTES_FILE.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, AUTHORITATIVE_MODEL_ROUTES_FILE)


def _stored_route_path(key: str) -> Path | None:
    raw = _read_authoritative_model_routes().get(key)
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return _resolve(Path(raw))
    except Exception:
        return None


def _stored_existing_route_path(key: str) -> Path | None:
    candidate = _stored_route_path(key)
    if candidate is None or not candidate.exists():
        return None
    return candidate


def _validate_model_dir(path: Path) -> Path:
    candidate = _resolve(path)
    if not candidate.exists():
        raise ValueError(f"model directory does not exist: {candidate}")
    if not candidate.is_dir():
        raise ValueError(f"model path is not a directory: {candidate}")
    if not (candidate / "config.json").exists():
        raise ValueError(f"model directory is missing config.json: {candidate}")
    has_single = (candidate / "model.safetensors").exists()
    has_index = (candidate / "model.safetensors.index.json").exists()
    has_shard = any(candidate.glob("model.safetensors-*.safetensors"))
    if not (has_single or has_index or has_shard):
        raise ValueError(f"model directory has no safetensors weights: {candidate}")
    return candidate


def _validate_private_model_dir(path: Path) -> Path:
    candidate = _validate_model_dir(path)
    if not (candidate / "model.safetensors").exists():
        raise ValueError(
            "private Athena source must contain a single model.safetensors because "
            f"exclusive/desktop_engine/export_vllm_ready_model.py loads that exact file: {candidate}"
        )
    config = _read_json_object(candidate / "config.json")
    architectures = [str(item) for item in list(config.get("architectures") or [])]
    model_type = str(config.get("model_type") or "")
    if "Qwen3_5ForCausalLM" not in architectures and model_type != "qwen3_5_text":
        raise ValueError(
            "private Athena source must be the AthenaV1/Qwen3.5 text overlay checkpoint expected by "
            f"export_vllm_ready_model.py, not a full multimodal/base model: {candidate}"
        )
    return candidate


def get_authoritative_model_routes_path() -> Path:
    return _resolve(AUTHORITATIVE_MODEL_ROUTES_FILE)


def get_authoritative_private_model_dir() -> Path:
    return _stored_existing_route_path("private_model_dir") or _resolve(EXCLUSIVE_MODEL_DIR)


def get_authoritative_public_model_dir() -> Path:
    return _stored_existing_route_path("public_model_dir") or _resolve(CHAT_MODEL_DIR)


def get_authoritative_model_routes() -> dict[str, str]:
    return {
        "routes_file": str(get_authoritative_model_routes_path()),
        "private_model_dir": str(get_authoritative_private_model_dir()),
        "public_model_dir": str(get_authoritative_public_model_dir()),
    }


def initialize_authoritative_model_routes(overwrite: bool = False) -> dict[str, str]:
    defaults = _route_defaults()
    existing = _read_authoritative_model_routes()
    payload = dict(existing)
    for key, value in defaults.items():
        if overwrite or not isinstance(payload.get(key), str) or not str(payload.get(key) or "").strip():
            validator = _validate_private_model_dir if key == "private_model_dir" else _validate_model_dir
            payload[key] = str(validator(value))
    _write_authoritative_model_routes(payload)
    return get_authoritative_model_routes()


def set_authoritative_model_route(scope: str, model_dir: Path | str) -> Path:
    normalized = (scope or "").strip().lower()
    if normalized not in {"private", "public"}:
        raise ValueError("scope must be 'private' or 'public'")
    key = f"{normalized}_model_dir"
    candidate = _validate_private_model_dir(Path(model_dir)) if normalized == "private" else _validate_model_dir(Path(model_dir))
    payload = dict(_read_authoritative_model_routes())
    defaults = _route_defaults()
    for default_key, default_path in defaults.items():
        if default_key not in payload:
            validator = _validate_private_model_dir if default_key == "private_model_dir" else _validate_model_dir
            payload[default_key] = str(validator(default_path))
    payload[key] = str(candidate)
    _write_authoritative_model_routes(payload)
    return candidate


def get_root_dir() -> Path:
    return _resolve(ROOT_DIR)


def get_public_chat_model_dir() -> Path:
    explicit = _env_path("ATHENA_PUBLIC_CHAT_MODEL_DIR")
    if explicit is not None:
        return explicit
    if not _private_mode_enabled():
        legacy = _env_path("ATHENA_CHAT_MODEL_DIR")
        if legacy is not None:
            return legacy
    stored = _stored_existing_route_path("public_model_dir")
    if stored is not None:
        return stored
    return _resolve(CHAT_MODEL_DIR)


def get_private_chat_model_dir() -> Path:
    explicit = _env_path("ATHENA_PRIVATE_CHAT_MODEL_DIR")
    if explicit is not None:
        return explicit
    if _private_mode_enabled():
        legacy = _env_path("ATHENA_CHAT_MODEL_DIR")
        if legacy is not None:
            return legacy
    stored = _stored_existing_route_path("private_model_dir")
    if stored is not None:
        return stored
    return _resolve(EXCLUSIVE_MODEL_DIR)


def get_public_vllm_model_dir() -> Path:
    explicit = _env_path("ATHENA_PUBLIC_VLLM_MODEL_DIR")
    if explicit is not None:
        return explicit
    return get_public_chat_model_dir()


def get_private_vllm_source_model_dir() -> Path:
    explicit = _env_path("ATHENA_PRIVATE_VLLM_SOURCE_MODEL_DIR")
    if explicit is not None:
        return explicit
    return get_private_chat_model_dir()


def get_private_base_multimodal_model_dir() -> Path:
    for env_name in (
        "ATHENA_PRIVATE_BASE_MULTIMODAL_MODEL_DIR",
        "ATHENA_BASE_MULTIMODAL_MODEL_DIR",
        "ATHENA_BASE_MODEL_DIR",
    ):
        explicit = _env_path(env_name)
        if explicit is not None:
            return explicit
    return _resolve(PRIVATE_BASE_MULTIMODAL_MODEL_DIR)


def get_private_vllm_export_root() -> Path:
    explicit = _env_path("ATHENA_PRIVATE_VLLM_EXPORT_ROOT")
    if explicit is not None:
        return explicit
    return _resolve(PRIVATE_VLLM_EXPORT_ROOT)


def get_default_chat_model_dir() -> Path:
    return get_private_chat_model_dir() if _private_mode_enabled() else get_public_chat_model_dir()


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


def _path_query_handlers() -> dict[str, object]:
    return {
        "root_dir": get_root_dir,
        "authoritative_model_routes_file": get_authoritative_model_routes_path,
        "authoritative_private_model_dir": get_authoritative_private_model_dir,
        "authoritative_public_model_dir": get_authoritative_public_model_dir,
        "public_chat_model_dir": get_public_chat_model_dir,
        "private_chat_model_dir": get_private_chat_model_dir,
        "default_chat_model_dir": get_default_chat_model_dir,
        "public_vllm_model_dir": get_public_vllm_model_dir,
        "private_vllm_source_model_dir": get_private_vllm_source_model_dir,
        "private_base_multimodal_model_dir": get_private_base_multimodal_model_dir,
        "private_vllm_export_root": get_private_vllm_export_root,
        "base_chat_model_dir": get_base_chat_model_dir,
        "orchestrator_model_dir": get_orchestrator_model_dir,
        "project_tuned_models_dir": get_project_tuned_models_dir,
        "future_tuned_models_root": get_future_tuned_models_root,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Query canonical Athena paths.")
    parser.add_argument("--query", choices=sorted(_path_query_handlers().keys()))
    parser.add_argument("--set-route", choices=("private", "public"), help="Persist the authoritative model route for one scope.")
    parser.add_argument("--model-dir", help="Model directory to persist with --set-route.")
    parser.add_argument("--init-routes", action="store_true", help="Create the authoritative route file with current defaults.")
    parser.add_argument("--overwrite-routes", action="store_true", help="When used with --init-routes, reset routes to code defaults.")
    parser.add_argument("--status", action="store_true", help="Print the authoritative public/private model routes.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if args.set_route:
        if not args.model_dir:
            parser.error("--set-route requires --model-dir")
        try:
            changed = set_authoritative_model_route(args.set_route, args.model_dir)
        except ValueError as exc:
            parser.error(str(exc))
        routes = get_authoritative_model_routes()
        print("path changed successfully")
        print(f"authoritative_private_model_dir={routes['private_model_dir']}")
        print(f"authoritative_public_model_dir={routes['public_model_dir']}")
        print(f"next_{args.set_route}_launch_model={changed.name}")
        return 0

    if args.init_routes:
        try:
            routes = initialize_authoritative_model_routes(overwrite=bool(args.overwrite_routes))
        except ValueError as exc:
            parser.error(str(exc))
        if args.as_json:
            print(json.dumps(routes, indent=2))
        else:
            print("path changed successfully")
            print(f"authoritative_private_model_dir={routes['private_model_dir']}")
            print(f"authoritative_public_model_dir={routes['public_model_dir']}")
        return 0

    if args.status:
        routes = get_authoritative_model_routes()
        print(json.dumps(routes, indent=2) if args.as_json else "\n".join(f"{key}={value}" for key, value in routes.items()))
        return 0

    handlers = _path_query_handlers()
    if args.as_json:
        payload = {key: str(handler()) for key, handler in handlers.items()}
        print(json.dumps(payload, indent=2))
        return 0
    if args.query:
        print(handlers[args.query]())
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
