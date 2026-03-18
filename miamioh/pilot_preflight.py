from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ENV = REPO_ROOT / "browser" / "config" / "portal_auth.env"
COURSE_ROOT = REPO_ROOT / "institutions" / "miamioh" / "courses" / "250433"
PILOT_OVERRIDES = COURSE_ROOT / "pilot" / "pilot_overrides.json"
CONTENT_CHUNKS = COURSE_ROOT / "derived" / "content_chunks.jsonl"
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


def main() -> int:
    _load_env_file(CONFIG_ENV)

    errors: list[str] = []
    warnings: list[str] = []
    authlib_status = "ok"

    try:
        import authlib  # noqa: F401
    except Exception as exc:
        authlib_status = f"missing ({exc})"
        warnings.append("Current Python runtime cannot import authlib. Ensure the portal is launched from the venv used by run_portal.ps1.")

    for key in REQUIRED_ENV_KEYS:
        if not str(os.getenv(key) or "").strip():
            errors.append(f"Missing required auth secret: {key}")

    if (os.getenv("ATHENA_DEFAULT_INSTITUTION") or "").strip().lower() != "miamioh":
        warnings.append("ATHENA_DEFAULT_INSTITUTION is not set to 'miamioh'.")

    if not PILOT_OVERRIDES.exists():
        errors.append(f"Missing pilot override bundle: {PILOT_OVERRIDES}")
    if not CONTENT_CHUNKS.exists():
        errors.append(f"Missing course chunk bundle: {CONTENT_CHUNKS}")

    pilot_payload = {}
    if PILOT_OVERRIDES.exists():
        try:
            pilot_payload = json.loads(PILOT_OVERRIDES.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"pilot_overrides.json could not be parsed: {exc}")

    next_assessment = ""
    if isinstance(pilot_payload, dict):
        for item in pilot_payload.get("assessment_calendar", []):
            if str(item.get("name") or "").strip() == "Exam #2":
                next_assessment = f"Exam #2 | {item.get('date_text')}"
                break

    print("MiamiOH Athena V5 pilot preflight")
    print(f"- env file: {CONFIG_ENV}")
    print(f"- authlib import: {authlib_status}")
    print(f"- pilot overrides: {PILOT_OVERRIDES.exists()}")
    print(f"- content chunks: {CONTENT_CHUNKS.exists()}")
    if pilot_payload:
        print(f"- course title: {pilot_payload.get('course_title') or pilot_payload.get('course_name')}")
        print(f"- source updated: {pilot_payload.get('source_updated_text')}")
        print(f"- roadmap titles: {', '.join((pilot_payload.get('published_module_titles') or [])[:4])}")
    if next_assessment:
        print(f"- reference assessment check: {next_assessment}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("\nPreflight failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nPreflight passed. The codebase is ready for a live Google sign-in check with MiamiOH auto-detection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
