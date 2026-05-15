from __future__ import annotations

import json
import shutil
from pathlib import Path


NOTEBOOKS = [
    Path(r"N:\Research\AENAIMO260_0_2_3_BENCHMARKGRADE_V1.ipynb"),
    Path(r"N:\Research\AEN_Valid_Canons\AENAIMO260_0_2_3_BENCHMARKGRADE.ipynb"),
]

OLD_REVISION = "2026-04-22-cb11_5-problem-boundary-reset-token-certificate-r1"
NEW_REVISION = "2026-04-27-cb11_5-boot-memory-preserving-boundary-reset-r2"

HELPERS = '''

def _cb11_5_copy_dialogue_messages(value: Any) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in list(value or []):
        if not isinstance(item, dict):
            continue
        messages.append(
            {
                "role": str(item.get("role", "")),
                "content": str(item.get("content", "")),
            }
        )
    return messages


def _cb11_5_boot_memory_baseline(session: Any) -> dict[str, Any]:
    baseline = getattr(session, "_cb8_boot_memory_baseline", None)
    return dict(baseline or {}) if isinstance(baseline, dict) else {}


def _cb11_5_restore_boot_memory_baseline(session: Any) -> dict[str, Any]:
    baseline = _cb11_5_boot_memory_baseline(session)
    if not baseline:
        return {
            "boot_memory_baseline_present": False,
            "boot_memory_restored": False,
            "boot_memory_dialogue_messages": 0,
            "boot_memory_committed_prompt_tokens": 0,
            "boot_memory_error": "",
        }
    try:
        session.dialogue_messages = _cb11_5_copy_dialogue_messages(baseline.get("dialogue_messages", []))
        session.visible_transcript = _cb11_5_copy_dialogue_messages(baseline.get("visible_transcript", []))
        session.original_problem_text = str(baseline.get("original_problem_text", "") or "")
        session.pending_user_text = ""
        session.committed_prompt_tokens = int(baseline.get("committed_prompt_tokens", 0) or 0)
        session.last_prompt_tokens_used = int(baseline.get("last_prompt_tokens_used", 0) or 0)
        session.last_generated_tokens = int(baseline.get("last_generated_tokens", 0) or 0)
        session.last_raw_text = ""
        session.last_visible_text = ""
        session.last_think_text = ""
        session.rebase_count = 0
        session.last_trimmed_message_count = 0
        session.last_rebase_reason = ""
        session.last_generation_metadata = {}
    except Exception as exc:
        return {
            "boot_memory_baseline_present": True,
            "boot_memory_restored": False,
            "boot_memory_dialogue_messages": 0,
            "boot_memory_committed_prompt_tokens": 0,
            "boot_memory_error": str(exc),
        }
    return {
        "boot_memory_baseline_present": True,
        "boot_memory_restored": True,
        "boot_memory_dialogue_messages": int(len(getattr(session, "dialogue_messages", []) or [])),
        "boot_memory_committed_prompt_tokens": int(getattr(session, "committed_prompt_tokens", 0) or 0),
        "boot_memory_error": "",
    }
'''

NEW_FORCE_RESET = '''def _cb11_5_force_reset_sessions(reason: str) -> dict[str, Any]:
    role_rows: list[dict[str, Any]] = []

    for label, session in _cb11_5_runtime_sessions():
        payload = {
            "label": str(label),
            "reset": False,
            "error": "",
            "boot_memory_baseline_present": False,
            "boot_memory_restored": False,
            "boot_memory_dialogue_messages": 0,
            "boot_memory_committed_prompt_tokens": 0,
        }
        reset_fn = getattr(session, "reset_session", None)
        if callable(reset_fn):
            try:
                reset_fn()
                payload["reset"] = True
                restore_report = _cb11_5_restore_boot_memory_baseline(session)
                payload.update(restore_report)
                if str(restore_report.get("boot_memory_error", "") or ""):
                    payload["error"] = str(restore_report.get("boot_memory_error", ""))
            except Exception as exc:
                payload["error"] = str(exc)
        else:
            payload["error"] = "missing reset_session()"
        role_rows.append(payload)

    all_reset = all(bool(row.get("reset")) for row in role_rows) if role_rows else False
    report = {
        "event": "cb11_5_problem_boundary_session_reset",
        "revision": CB11_5_ARCHITECTURE_CERTIFICATE_REVISION,
        "reason": str(reason),
        "session_reset_happened": bool(all_reset),
        "all_reset": bool(all_reset),
        "boot_memory_preserved": all(
            (not bool(row.get("boot_memory_baseline_present"))) or bool(row.get("boot_memory_restored"))
            for row in role_rows
        ) if role_rows else False,
        "roles": role_rows,
        "printed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(report, flush=True)
    return report
'''

NEW_MODEL_TURN_GUARD = '''_base_turn = globals().get("_run_model_turn")
if callable(_base_turn) and bool(getattr(_base_turn, "_cb11_5_wrapper", False)):
    _base_turn = globals().get("_CB11_5_BASE_RUN_MODEL_TURN")
if not callable(_base_turn):
    raise NameError("_run_model_turn is not defined. Run Section 07 / CB11 before CB11.5.")
globals()["_CB11_5_BASE_RUN_MODEL_TURN"] = _base_turn
'''

NEW_PROTOCOL_GUARD = '''_base_protocol = globals().get("run_aen_protocol")
if callable(_base_protocol) and bool(getattr(_base_protocol, "_cb11_5_wrapper", False)):
    _base_protocol = globals().get("_CB11_5_BASE_RUN_AEN_PROTOCOL")
if not callable(_base_protocol):
    raise NameError("run_aen_protocol is not defined. Run CB11 before CB11.5.")
globals()["_CB11_5_BASE_RUN_AEN_PROTOCOL"] = _base_protocol
'''


def replace_between(source: str, start: str, end: str, replacement: str) -> str:
    start_index = source.find(start)
    if start_index < 0:
        raise RuntimeError(f"start marker not found: {start!r}")
    end_index = source.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"end marker not found after {start!r}: {end!r}")
    return source[:start_index] + replacement.rstrip() + "\n\n" + source[end_index:]


def patch_source(source: str) -> str:
    source = source.replace(OLD_REVISION, NEW_REVISION)
    if "_cb11_5_restore_boot_memory_baseline" not in source:
        source = source.replace(
            "\ndef _cb11_5_force_reset_sessions(reason: str) -> dict[str, Any]:",
            HELPERS + "\ndef _cb11_5_force_reset_sessions(reason: str) -> dict[str, Any]:",
        )
    source = replace_between(
        source,
        "def _cb11_5_force_reset_sessions(reason: str) -> dict[str, Any]:",
        "def _cb11_5_preview_prompt_tokens(",
        NEW_FORCE_RESET,
    )
    source = replace_between(
        source,
        'if "_CB11_5_BASE_RUN_MODEL_TURN" not in globals():',
        "def _run_model_turn(",
        NEW_MODEL_TURN_GUARD,
    )
    source = replace_between(
        source,
        'if "_CB11_5_BASE_RUN_AEN_PROTOCOL" not in globals():',
        "def run_aen_protocol(problem_text: str) -> dict[str, Any]:",
        NEW_PROTOCOL_GUARD,
    )
    if 'setattr(_run_model_turn, "_cb11_5_wrapper", True)' not in source:
        source = source.replace(
            '\n\n_base_protocol = globals().get("run_aen_protocol")',
            '\n\nsetattr(_run_model_turn, "_cb11_5_wrapper", True)\n\n_base_protocol = globals().get("run_aen_protocol")',
        )
    if 'setattr(run_aen_protocol, "_cb11_5_wrapper", True)' not in source:
        source = source.replace(
            '\n\nprint(\n    {\n        "event": "cb11_5_architecture_certificate_wrapper_installed"',
            '\n\nsetattr(run_aen_protocol, "_cb11_5_wrapper", True)\n\nprint(\n    {\n        "event": "cb11_5_architecture_certificate_wrapper_installed"',
        )
    compile(source, "CB11.5", "exec")
    return source


def patch_notebook(path: Path) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for cell in notebook.get("cells", []):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if "CB11_5_ARCHITECTURE_CERTIFICATE_REVISION" not in source or "def run_aen_protocol(problem_text" not in source:
            continue
        patched = patch_source(source)
        backup = path.with_suffix(path.suffix + ".pre_cb11_5_boot_memory_reset_bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        cell["source"] = patched.splitlines(keepends=True)
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"patched CB11.5: {path}")
        return
    raise RuntimeError(f"CB11.5 AEN cell not found: {path}")


def main() -> int:
    for notebook in NOTEBOOKS:
        patch_notebook(notebook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
