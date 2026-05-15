from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
LOCAL_CONFIG = ROOT / ".local" / "config"
LOCAL_RUNTIME = ROOT / ".local" / "runtime"

RUN_UI_PRIVATE = ROOT / "run_ui_private.ps1"
RUN_PORTAL = ROOT / "run_portal.ps1"
RUN_BROWSER = ROOT / "browser" / "run_browser.ps1"
RUN_VLLM = ROOT / "run_vllm.ps1"
ATHENA_PATHS_FILE = ROOT / "athena_paths.py"
AUTHORITATIVE_ROUTES_FILE = LOCAL_CONFIG / "athena_model_routes.json"

PRIVATE_RUNTIME_ENV = LOCAL_RUNTIME / "vllm_private_runtime.env"
PRIVATE_RUNTIME_STATE = LOCAL_RUNTIME / "vllm_private_runtime.json"
PUBLIC_RUNTIME_ENV = LOCAL_RUNTIME / "vllm_runtime.env"
PUBLIC_RUNTIME_STATE = LOCAL_RUNTIME / "vllm_runtime.json"

WATCHED_ENV = [
    "ATHENA_ROOT_DIR",
    "ATHENA_RUNTIME_SCOPE",
    "ATHENA_PRIVATE_MODE",
    "ATHENA_CHAT_MODEL_DIR",
    "ATHENA_PRIVATE_CHAT_MODEL_DIR",
    "ATHENA_PRIVATE_VLLM_SOURCE_MODEL_DIR",
    "ATHENA_PRIVATE_VLLM_EXPORT_ROOT",
    "ATHENA_PUBLIC_CHAT_MODEL_DIR",
    "ATHENA_PUBLIC_VLLM_MODEL_DIR",
    "ATHENA_PUBLIC_VLLM_MODEL_NAME",
    "ATHENA_PUBLIC_VLLM_BASE_URL",
    "ATHENA_VLLM_MODEL_DIR",
    "ATHENA_VLLM_MODEL",
    "ATHENA_VLLM_BASE_URL",
    "ATHENA_VLLM_API_KEY",
]


def _import_athena_paths():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import athena_paths  # type: ignore

    return athena_paths


athena_paths = _import_athena_paths()


@contextmanager
def temporary_env(overrides: dict[str, str | None]):
    old_values = {name: os.environ.get(name) for name in overrides}
    try:
        for name, value in overrides.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in old_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if name:
            values[name] = value
    return values


def read_json_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"}
    return raw if isinstance(raw, dict) else {"_error": "top level JSON was not an object"}


def path_status(raw: object) -> str:
    text = "" if raw is None else str(raw)
    if not text:
        return "<empty>"
    try:
        path = Path(text).expanduser()
        if path.exists():
            kind = "dir" if path.is_dir() else "file"
            return f"{path.resolve()}  [exists:{kind}]"
        return f"{path}  [missing]"
    except Exception:
        return f"{text}  [not-a-local-path]"


def model_markers(raw: object) -> str:
    if not raw:
        return ""
    path = Path(str(raw)).expanduser()
    markers = []
    for name in (
        "config.json",
        "model.safetensors",
        "model.safetensors.index.json",
        "tokenizer.json",
    ):
        markers.append(f"{name}={'yes' if (path / name).exists() else 'no'}")
    return ", ".join(markers)


def print_section(title: str) -> None:
    print()
    print("=" * 88)
    print(title)
    print("=" * 88)


def print_kv(label: str, value: object) -> None:
    print(f"{label:<38} {value}")


def print_path(label: str, value: object) -> None:
    print_kv(label, path_status(value))
    markers = model_markers(value)
    if markers:
        print_kv(label + " markers", markers)


def find_lines(path: Path, patterns: Iterable[str]) -> list[str]:
    if not path.exists():
        return [f"{path}: missing"]
    compiled = [re.compile(pattern) for pattern in patterns]
    hits: list[str] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = raw_line.strip()
        for pattern in compiled:
            if pattern.search(stripped):
                hits.append(f"{path.relative_to(ROOT)}:{line_no}: {stripped}")
                break
    return hits


def print_lines(title: str, path: Path, patterns: Iterable[str]) -> None:
    print()
    print(title)
    for hit in find_lines(path, patterns):
        print(f"  {hit}")


def get_athena_public_paths() -> dict[str, Path]:
    with temporary_env(
        {
            "ATHENA_PRIVATE_MODE": None,
            "ATHENA_RUNTIME_SCOPE": None,
        }
    ):
        return {
            "public_chat_model_dir": athena_paths.get_public_chat_model_dir(),
            "public_vllm_model_dir": athena_paths.get_public_vllm_model_dir(),
            "default_chat_model_dir": athena_paths.get_default_chat_model_dir(),
            "gui_config_path": athena_paths.get_gui_config_path(),
            "system_prompt_path": athena_paths.get_system_prompt_path(),
        }


def get_athena_private_paths() -> dict[str, Path]:
    with temporary_env(
        {
            "ATHENA_PRIVATE_MODE": "1",
            "ATHENA_RUNTIME_SCOPE": "private",
        }
    ):
        return {
            "private_chat_model_dir": athena_paths.get_private_chat_model_dir(),
            "private_vllm_source_model_dir": athena_paths.get_private_vllm_source_model_dir(),
            "private_vllm_export_root": athena_paths.get_private_vllm_export_root(),
            "default_chat_model_dir": athena_paths.get_default_chat_model_dir(),
            "gui_config_path": athena_paths.get_gui_config_path(),
            "system_prompt_path": athena_paths.get_system_prompt_path(),
        }


def resolve_run_ui_private_default() -> dict[str, Path | str]:
    private_paths = get_athena_private_paths()
    source_model_dir = athena_paths.get_authoritative_private_model_dir()
    served_model_name = source_model_dir.name
    export_root = private_paths["private_vllm_export_root"]
    export_model_dir = export_root / served_model_name
    return {
        "setter_file": "athena_paths.py authoritative route -> run_ui_private.ps1",
        "source_model_dir": source_model_dir,
        "served_model_name": served_model_name,
        "export_root": export_root,
        "vllm_model_dir_passed_to_run_vllm": export_model_dir,
        "runtime_env_file": PRIVATE_RUNTIME_ENV,
        "runtime_state_file": PRIVATE_RUNTIME_STATE,
        "base_url_default": "http://127.0.0.1:8002/v1",
        "runtime_name": "private",
    }


def resolve_run_portal_default() -> dict[str, Path | str]:
    model_dir = athena_paths.get_authoritative_public_model_dir()
    return {
        "setter_file": "browser/run_browser.ps1 + athena_paths.py authoritative route",
        "source_model_dir": model_dir,
        "served_model_name_default": model_dir.name,
        "runtime_env_file": PUBLIC_RUNTIME_ENV,
        "runtime_state_file": PUBLIC_RUNTIME_STATE,
        "base_url_default": "http://127.0.0.1:8001/v1",
        "runtime_name": "shared",
    }


def print_runtime_files(label: str, env_path: Path, state_path: Path) -> None:
    print()
    print(f"{label} persisted runtime files")
    env_values = read_env_file(env_path)
    state_values = read_json_file(state_path)
    print_path("env file", env_path)
    for key in ("ATHENA_VLLM_BASE_URL", "ATHENA_VLLM_MODEL_DIR", "ATHENA_VLLM_MODEL", "ATHENA_VLLM_API_KEY"):
        if key in env_values:
            value = env_values[key]
            if key.endswith("MODEL_DIR"):
                print_path(f"env:{key}", value)
            else:
                print_kv(f"env:{key}", value)
    print_path("state file", state_path)
    for key in (
        "model_dir",
        "served_model",
        "base_url",
        "models_url",
        "launcher",
        "pid",
        "max_model_len",
        "max_input_tokens_per_turn",
        "started_at",
    ):
        if key in state_values:
            value = state_values[key]
            if key == "model_dir":
                print_path(f"state:{key}", value)
            else:
                print_kv(f"state:{key}", value)


def debug_main() -> int:
    private_script = resolve_run_ui_private_default()
    public_script = resolve_run_portal_default()
    athena_public = get_athena_public_paths()
    athena_private = get_athena_private_paths()

    print_section("Athena path verification")
    print_path("project root", ROOT)
    print_path("athena_paths.py", ATHENA_PATHS_FILE)
    print_path("authoritative routes file", athena_paths.get_authoritative_model_routes_path())
    print_kv("note", "This script prints resolution only. It does not start vLLM or the portal.")

    print_section("Authoritative route state")
    routes = athena_paths.get_authoritative_model_routes()
    print_path("routes file", routes["routes_file"])
    print_path("authoritative private route", routes["private_model_dir"])
    print_path("authoritative public route", routes["public_model_dir"])
    raw_routes = read_json_file(Path(routes["routes_file"]))
    if raw_routes:
        print_kv("routes raw json", json.dumps(raw_routes, indent=2))

    print_section("Current process environment")
    for name in WATCHED_ENV:
        value = os.environ.get(name, "")
        if name.endswith("DIR") or name.endswith("ROOT"):
            print_path(f"env:{name}", value)
        else:
            print_kv(f"env:{name}", value or "<unset>")

    print_section("Private desktop: run_ui_private.ps1")
    print_kv("authoritative setter", private_script["setter_file"])
    print_kv("uses athena_paths.py for source?", "yes")
    print_kv("default source rule", "authoritative_private_model_dir unless -ModelDir is passed")
    print_path("private source model dir", private_script["source_model_dir"])
    print_kv("served model name", private_script["served_model_name"])
    print_path("private export root", private_script["export_root"])
    print_path("vLLM model dir passed to run_vllm", private_script["vllm_model_dir_passed_to_run_vllm"])
    print_kv("runtime name", private_script["runtime_name"])
    print_kv("default base url", private_script["base_url_default"])
    print_path("runtime env file", private_script["runtime_env_file"])
    print_path("runtime state file", private_script["runtime_state_file"])

    print()
    print("Private athena_paths.py values available to run_ui_private.ps1")
    for key, value in athena_private.items():
        print_path(f"athena_paths.{key}", value)

    print_lines(
        "Private setter lines",
        RUN_UI_PRIVATE,
        [
            r"^\$AthenaPathsScript\s*=",
            r"^\$ResolvedModelDir\s*=",
            r"function Resolve-AthenaPathQuery",
            r"function Resolve-PrivateSourceModelDir",
            r"authoritative_private_model_dir",
            r"^\$ResolvedServedModelName\s*=",
            r"Export-PrivateVllmModel",
            r"\$env:ATHENA_CHAT_MODEL_DIR\s*=",
            r"\$env:ATHENA_VLLM_MODEL_DIR\s*=",
            r"Invoke-SharedVllmBootstrap",
            r"Write-Host \"scope=private model=",
        ],
    )

    print_section("Public portal: run_portal.ps1 -> browser/run_browser.ps1")
    print_kv("authoritative setter", public_script["setter_file"])
    print_kv("run_portal model setter?", "no; it delegates to browser/run_browser.ps1")
    print_kv("public model rule", "athena_paths authoritative_public_model_dir first")
    print_kv("model env override rule", "ATHENA_PUBLIC_* model overrides require ATHENA_ALLOW_MODEL_ENV_OVERRIDES=1")
    print_kv("stale runtime env policy", "generic ATHENA_VLLM_MODEL is ignored; public model ID defaults to route folder name")
    print_path("public source/vLLM model dir", public_script["source_model_dir"])
    print_kv("served model name default", public_script["served_model_name_default"])
    print_kv("runtime name", public_script["runtime_name"])
    print_kv("default base url", public_script["base_url_default"])
    print_path("runtime env file", public_script["runtime_env_file"])
    print_path("runtime state file", public_script["runtime_state_file"])

    print()
    print("Public athena_paths.py values available to browser/run_browser.ps1")
    for key, value in athena_public.items():
        print_path(f"athena_paths.{key}", value)

    print_lines(
        "Public delegator lines",
        RUN_PORTAL,
        [
            r"browser\\run_browser\.ps1",
            r"-LoadModel:\$LoadModel",
        ],
    )
    print_lines(
        "Public setter lines",
        RUN_BROWSER,
        [
            r"^\$SharedRuntimeEnvFile\s*=",
            r"^\$SharedVllmLauncher\s*=",
            r"^\$AllowModelEnvOverrides\s*=",
            r"^\$ExplicitPublicVllmModelName\s*=",
            r"^\$ExplicitVllmBaseUrl\s*=",
            r"^\$ExplicitPublicVllmBaseUrl\s*=",
            r"Import-EnvFile -FilePath \$SharedRuntimeEnvFile",
            r"Remove-Item -Path \"Env:ATHENA_VLLM",
            r"function Resolve-VllmModelDir",
            r"authoritative_public_model_dir",
            r"ATHENA_PUBLIC_VLLM_MODEL_DIR",
            r"ATHENA_PUBLIC_CHAT_MODEL_DIR",
            r"public_vllm_model_dir",
            r"public_chat_model_dir",
            r"\$modelDir = Resolve-VllmModelDir",
            r"\$env:ATHENA_CHAT_MODEL_DIR\s*=",
            r"public_resolved_model_dir",
            r"public_served_model",
            r"Invoke-SharedVllmBootstrap -ResolvedModelDir \$modelDir",
        ],
    )

    print_section("Shared launcher used by both public and private")
    print_kv("shared file", RUN_VLLM.relative_to(ROOT))
    print_kv("shared role", "starts/reuses vLLM and writes runtime env/state")
    print_kv("important distinction", "public passes source model dir; private passes exported runtime copy")
    print_lines(
        "Shared run_vllm.ps1 model-resolution lines",
        RUN_VLLM,
        [
            r"function Resolve-ModelDir",
            r"\$env:ATHENA_VLLM_MODEL_DIR",
            r"\$env:ATHENA_CHAT_MODEL_DIR",
            r"models\\Qwen3\.5-4B",
            r"Write-RuntimeEnv",
            r"Write-RuntimeState",
            r"--model",
            r"linux_model_dir=",
            r"runtime_env=",
        ],
    )

    print_section("Persisted runtime files from last launches")
    print_runtime_files("private", PRIVATE_RUNTIME_ENV, PRIVATE_RUNTIME_STATE)
    print_runtime_files("public/shared", PUBLIC_RUNTIME_ENV, PUBLIC_RUNTIME_STATE)

    print_section("Bottom line")
    print("PRIVATE:")
    print("  athena_paths.py is the authoritative private source setter.")
    print("  run_ui_private.ps1 asks athena_paths.py for authoritative_private_model_dir unless -ModelDir is passed.")
    print("  It exports that source to .local\\runtime\\vllm_private_models\\<served_model> and serves the export.")
    print()
    print("PUBLIC:")
    print("  run_portal.ps1 is not the model setter.")
    print("  browser\\run_browser.ps1 resolves the model through athena_paths.py authoritative_public_model_dir.")
    print("  ATHENA_PUBLIC_* model env vars are ignored unless ATHENA_ALLOW_MODEL_ENV_OVERRIDES=1.")
    print()
    print("SHARED:")
    print("  run_vllm.ps1 is the common serving launcher.")
    print("  It accepts the model dir already chosen by the public/private wrapper.")
    return 0


def canonical_line() -> str:
    private_path = athena_paths.get_authoritative_private_model_dir()
    public_path = athena_paths.get_authoritative_public_model_dir()
    return f'CANONICAL_PATHS private="{private_path}" public="{public_path}"'


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify canonical Athena model paths.")
    parser.add_argument("--debug", action="store_true", help="Print the full path-resolution diagnostic report.")
    args = parser.parse_args()

    if args.debug:
        return debug_main()

    print(canonical_line())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
