from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from athena_paths import get_default_chat_model_dir


CONFIG_ENV = REPO_ROOT / "browser" / "config" / "portal_auth.env"
RUNTIME_ENV = REPO_ROOT / ".local" / "runtime" / "vllm_runtime.env"
INSTITUTION_ROOT = REPO_ROOT / "institutions" / "miamioh"
COURSE_ROOT = INSTITUTION_ROOT / "courses" / "250433"
PILOT_OVERRIDES = COURSE_ROOT / "pilot" / "pilot_overrides.json"
PILOT_PEOPLE = COURSE_ROOT / "pilot" / "pilot_people.json"
CONTENT_CHUNKS = COURSE_ROOT / "derived" / "content_chunks.jsonl"
RUN_BROWSER = REPO_ROOT / "browser" / "run_browser.ps1"
REQUIRED_ENV_KEYS = [
    "ATHENA_GOOGLE_CLIENT_ID",
    "ATHENA_GOOGLE_CLIENT_SECRET",
    "ATHENA_PORTAL_SESSION_SECRET",
]


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


def main() -> int:
    _load_env_file(RUNTIME_ENV)
    _load_env_file(CONFIG_ENV)

    errors: list[str] = []
    warnings: list[str] = []
    system_name = platform.system()

    authlib_status = "ok"
    try:
        import authlib  # noqa: F401
    except Exception as exc:
        authlib_status = f"missing ({exc})"
        errors.append("Current Python runtime cannot import authlib.")

    vllm_status = "ok"
    try:
        import vllm  # noqa: F401
    except Exception as exc:
        vllm_status = f"missing ({exc})"
        if system_name.lower() == "windows":
            warnings.append("Current Python runtime cannot import vllm. This is expected on native Windows if you are using a WSL/Linux vLLM server.")
        else:
            errors.append("Current Python runtime cannot import vllm.")

    for key in REQUIRED_ENV_KEYS:
        if not str(os.getenv(key) or "").strip():
            errors.append(f"Missing required auth secret: {key}")

    if (os.getenv("ATHENA_DEFAULT_INSTITUTION") or "").strip().lower() != "miamioh":
        warnings.append("ATHENA_DEFAULT_INSTITUTION is not set to 'miamioh'.")

    if (os.getenv("ATHENA_RUNTIME_BACKEND") or "vllm_openai").strip().lower() != "vllm_openai":
        warnings.append("ATHENA_RUNTIME_BACKEND is not set to vllm_openai.")

    if not RUN_BROWSER.exists():
        errors.append(f"Missing browser launcher: {RUN_BROWSER}")

    model_dir = get_default_chat_model_dir()
    if not model_dir.exists():
        errors.append(f"Resolved chat model directory does not exist: {model_dir}")

    for path in (PILOT_OVERRIDES, PILOT_PEOPLE, CONTENT_CHUNKS):
        if not path.exists():
            errors.append(f"Missing required bundle file: {path}")

    base_url = (os.getenv("ATHENA_VLLM_BASE_URL") or "http://127.0.0.1:8001/v1").strip().rstrip("/")
    api_key = (os.getenv("ATHENA_VLLM_API_KEY") or "athena-local").strip() or "athena-local"
    models_url = f"{base_url}/models"
    live_models = _http_json(models_url, api_key=api_key)
    if live_models is None:
        warnings.append(f"vLLM endpoint not reachable yet: {models_url}")
        if system_name.lower() == "windows":
            errors.append("Native Windows does not support running vLLM directly. Start a WSL/Linux vLLM server and point ATHENA_VLLM_BASE_URL to it.")

    print("Public Athena V5 runtime preflight")
    print(f"- platform: {system_name}")
    print(f"- env file: {CONFIG_ENV}")
    print(f"- authlib import: {authlib_status}")
    print(f"- vllm import: {vllm_status}")
    print(f"- launcher exists: {RUN_BROWSER.exists()}")
    print(f"- model dir: {model_dir}")
    print(f"- pilot overrides: {PILOT_OVERRIDES.exists()}")
    print(f"- pilot people: {PILOT_PEOPLE.exists()}")
    print(f"- content chunks: {CONTENT_CHUNKS.exists()}")
    print(f"- models endpoint: {models_url}")
    if live_models and isinstance(live_models.get('data'), list) and live_models['data']:
        print(f"- served model: {live_models['data'][0].get('id')}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("\nPreflight failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nPreflight passed. Public Athena V5 is configured for a live vLLM-backed startup check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
