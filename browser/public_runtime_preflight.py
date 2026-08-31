from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from athena_paths import get_public_chat_model_dir
from browser.canvas_support import InstitutionRegistry
from desktop_engine.prompt_config import PromptConfigError, load_prompt_document


CONFIG_ENV = REPO_ROOT / "browser" / "config" / "portal_auth.env"
RUNTIME_ENV = REPO_ROOT / ".local" / "runtime" / "vllm_runtime.env"
INSTITUTIONS_CONFIG = REPO_ROOT / "browser" / "config" / "institutions.json"
SYSTEM_PROMPT_CONFIG = REPO_ROOT / "browser" / "config" / "system_prompt.json"
CONTEXT_PROFILES_CONFIG = REPO_ROOT / "browser" / "config" / "context_profiles.json"
RUN_BROWSER = REPO_ROOT / "browser" / "run_browser.ps1"
PUBLIC_IDENTITY_FILES = (
    REPO_ROOT / "browser" / "portal" / "templates" / "index.html",
    REPO_ROOT / "browser" / "portal" / "templates" / "login.html",
    REPO_ROOT / "browser" / "portal" / "templates" / "_signin_methods.html",
    REPO_ROOT / "browser" / "config" / "system_prompt.json",
)
PUBLIC_BANNED_MARKERS = (
    "miamioh",
    "@miamioh.edu",
    "athenav11",
    "athena_v11",
    "stellar sway",
)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _http_json(url: str, api_key: str | None = None) -> dict | None:
    try:
        request = Request(url)
        if api_key:
            request.add_header("Authorization", f"Bearer {api_key}")
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _pair_state(client_id_key: str, client_secret_key: str) -> tuple[bool, bool]:
    client_id = bool(str(os.getenv(client_id_key) or "").strip())
    client_secret = bool(str(os.getenv(client_secret_key) or "").strip())
    return client_id and client_secret, client_id != client_secret


def _scan_public_identity(errors: list[str]) -> None:
    for path in PUBLIC_IDENTITY_FILES:
        if not path.exists():
            errors.append(f"Missing public identity file: {path}")
            continue
        lowered = path.read_text(encoding="utf-8-sig").lower()
        for marker in PUBLIC_BANNED_MARKERS:
            if marker in lowered:
                errors.append(f"Public identity file contains banned private or stale marker {marker!r}: {path}")


def _validate_public_prompt_profile(errors: list[str]):
    try:
        return load_prompt_document(
            SYSTEM_PROMPT_CONFIG,
            strict=True,
            public_tutor=True,
            banned_markers=PUBLIC_BANNED_MARKERS,
        )
    except PromptConfigError as exc:
        errors.append(f"Public tutor prompt profile is invalid: {exc}")
        return None


def _validate_context_profiles(errors: list[str]) -> dict:
    try:
        payload = json.loads(CONTEXT_PROFILES_CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Context profile configuration is unavailable or invalid: {exc}")
        return {}
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    if not isinstance(profiles, dict):
        errors.append("Context profile configuration has no profiles object.")
        return {}
    native = profiles.get("native")
    yarn = profiles.get("yarn_1010k")
    if not isinstance(native, dict) or int(native.get("max_model_len") or 0) < 128000:
        errors.append("Native context profile must preserve at least the current 128K practical window.")
    if not isinstance(yarn, dict) or not bool(yarn.get("experimental")):
        errors.append("YaRN 1.01M context profile must exist and remain explicitly experimental.")
        return profiles
    rope = (((yarn.get("hf_overrides") or {}).get("text_config") or {}).get("rope_parameters") or {})
    expected = {
        "rope_type": "yarn",
        "factor": 4.0,
        "original_max_position_embeddings": 262144,
        "partial_rotary_factor": 0.25,
    }
    for key, value in expected.items():
        if rope.get(key) != value:
            errors.append(f"YaRN context profile has unexpected {key}: {rope.get(key)!r}")
    if int(yarn.get("max_model_len") or 0) != 1010000:
        errors.append("YaRN context profile max_model_len must be 1010000.")
    return profiles


def main() -> int:
    _load_env_file(RUNTIME_ENV)
    _load_env_file(CONFIG_ENV)

    errors: list[str] = []
    warnings: list[str] = []
    system_name = platform.system()

    google_ready, google_partial = _pair_state("ATHENA_GOOGLE_CLIENT_ID", "ATHENA_GOOGLE_CLIENT_SECRET")
    github_ready, github_partial = _pair_state("ATHENA_GITHUB_CLIENT_ID", "ATHENA_GITHUB_CLIENT_SECRET")
    if google_partial:
        errors.append("Google OAuth is partial; configure both client ID and client secret or neither.")
    if github_partial:
        errors.append("GitHub OAuth is partial; configure both client ID and client secret or neither.")

    registry = InstitutionRegistry.load(INSTITUTIONS_CONFIG, project_root=REPO_ROOT)
    available_institutions = registry.available()
    for record in registry.all():
        values = (bool(record.client_id), bool(record.client_secret), bool(record.redirect_uri))
        if any(values) and not all(values):
            errors.append(f"Institution OAuth is partial for {record.institution_key!r}; configure ID, secret, and redirect URI together.")

    guest_ready = _env_bool("ATHENA_GUEST_LOGIN_ENABLED", True)
    oauth_ready = google_ready or github_ready or bool(available_institutions)
    if not oauth_ready and not guest_ready:
        errors.append("No usable sign-in route is configured. Enable Guest or configure a complete OAuth provider.")

    redirect_uri = str(os.getenv("ATHENA_AUTH_REDIRECT_URI") or "").strip()
    if (google_ready or github_ready) and not redirect_uri:
        errors.append("ATHENA_AUTH_REDIRECT_URI is required for Google or GitHub OAuth.")

    session_secret = str(os.getenv("ATHENA_PORTAL_SESSION_SECRET") or "").strip()
    if not session_secret or session_secret == "athena-browser-dev-session":
        errors.append("ATHENA_PORTAL_SESSION_SECRET must be set to a non-default production value.")

    default_institution = str(os.getenv("ATHENA_DEFAULT_INSTITUTION") or "").strip().lower()
    available_keys = {record.institution_key for record in available_institutions}
    if default_institution and default_institution not in available_keys:
        errors.append(
            f"ATHENA_DEFAULT_INSTITUTION={default_institution!r} is not OAuth-ready; clear it or complete that institution configuration."
        )

    authlib_status = "not required"
    if oauth_ready:
        try:
            import authlib  # noqa: F401

            authlib_status = "ok"
        except Exception as exc:
            authlib_status = f"missing ({exc})"
            errors.append("OAuth is configured, but the current Python runtime cannot import authlib.")

    vllm_status = "ok"
    try:
        import vllm  # noqa: F401
    except Exception as exc:
        vllm_status = f"missing ({exc})"
        if system_name.lower() == "windows":
            warnings.append("Native Windows cannot import vLLM; this is expected when WSL/Linux serves the model.")
        else:
            errors.append("Current Linux runtime cannot import vLLM.")

    if (os.getenv("ATHENA_RUNTIME_BACKEND") or "vllm_openai").strip().lower() != "vllm_openai":
        errors.append("ATHENA_RUNTIME_BACKEND must be vllm_openai for the public portal.")
    if not _env_bool("ATHENA_PUBLIC_VLLM_ONLY", True):
        errors.append("ATHENA_PUBLIC_VLLM_ONLY must be enabled for the public portal.")
    if not RUN_BROWSER.exists():
        errors.append(f"Missing browser launcher: {RUN_BROWSER}")

    model_dir = get_public_chat_model_dir()
    if not model_dir.exists():
        errors.append(f"Resolved public model directory does not exist: {model_dir}")

    _scan_public_identity(errors)
    prompt_document = _validate_public_prompt_profile(errors)
    context_profiles = _validate_context_profiles(errors)

    base_url = (os.getenv("ATHENA_VLLM_BASE_URL") or "http://127.0.0.1:8001/v1").strip().rstrip("/")
    api_key = (os.getenv("ATHENA_VLLM_API_KEY") or "athena-local").strip() or "athena-local"
    models_url = f"{base_url}/models"
    live_models = _http_json(models_url, api_key=api_key)
    served_model = ""
    if live_models and isinstance(live_models.get("data"), list) and live_models["data"]:
        served_model = str(live_models["data"][0].get("id") or "").strip()
    if live_models is None:
        warnings.append(f"vLLM endpoint is not reachable yet: {models_url}")
        if system_name.lower() == "windows":
            errors.append("Start the WSL/Linux vLLM server and set ATHENA_VLLM_BASE_URL before public launch.")

    expected_model = str(os.getenv("ATHENA_PUBLIC_MODEL_EXPECTED_ID") or "Qwen3.5-4B").strip()
    if served_model and expected_model and expected_model.lower() not in served_model.lower():
        errors.append(f"Served model {served_model!r} does not match expected public model {expected_model!r}.")

    providers = []
    if google_ready:
        providers.append("google")
    if github_ready:
        providers.append("github")
    if guest_ready:
        providers.append("guest")
    providers.extend(f"institution:{record.institution_key}" for record in available_institutions)

    print("Public Athena V5 runtime preflight")
    print(f"- platform: {system_name}")
    print(f"- env file present: {CONFIG_ENV.exists()}")
    print(f"- advertised sign-in routes: {', '.join(providers) if providers else 'none'}")
    print(f"- authlib import: {authlib_status}")
    print(f"- vllm import: {vllm_status}")
    print(f"- launcher exists: {RUN_BROWSER.exists()}")
    print(f"- public model directory exists: {model_dir.exists()}")
    print(f"- expected public model: {expected_model}")
    if prompt_document is not None:
        print(f"- tutor prompt profile: {prompt_document.name} v{prompt_document.version}")
        print(f"- tutor prompt sha256: {prompt_document.sha256}")
        print(f"- tutor prompt strict validation: {prompt_document.validated}")
    if context_profiles:
        print(f"- context profiles: {', '.join(sorted(context_profiles))}")
        print("- default context safety: native profile; YaRN requires explicit experimental opt-in")
    print(f"- model endpoint reachable: {live_models is not None}")
    if served_model:
        print(f"- served model: {served_model}")
    print(f"- Google institution auto-attach: {_env_bool('ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH', False)}")
    print(f"- public identity files sanitized: {not any('Public identity file' in item for item in errors)}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("\nPreflight failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nPreflight passed. Public auth, model identity, and runtime boundaries are release-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
