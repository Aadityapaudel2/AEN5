# Auto-extracted by Codex from AENAIMO260_0_2_3_BENCHMARKGRADE_V1.ipynb
# Source cell: 43 / CB11.5 - Architecture Reset and Token Certificate
# Intended use: run/paste after CB11 and after CB8 runtime boot.

# ## 11.5 - Architecture Reset and Token Certificate
#
# Purpose:
# - Prevent cross-problem session contamination.
# - Preserve within-problem role-local continuity.
# - Print architecture-level token/session certificates before each model turn.
# - Reset all role sessions after each finalized problem.


# %%
import time
from typing import Any


CB11_5_ARCHITECTURE_CERTIFICATE_REVISION = (
    "2026-04-28-cb11_5-runtime-baseline-fallback-r5"
)

# Critical architecture policy:
# Keep role sessions alive within a problem.
# Reset only at problem boundaries.
CONTROLLER_RESET_SESSION_EACH_TURN = False

# Show controller JSON reset events.
CONTROLLER_JSON_EVENTS = True


def _cb11_5_runtime_state() -> dict[str, Any]:
    runtime = globals().get("RUNTIME")
    return runtime if isinstance(runtime, dict) else {}


def _cb11_5_boot_memory_required() -> bool:
    runtime = _cb11_5_runtime_state()
    summary = runtime.get("runtime_at_boot_summary")
    certification = runtime.get("runtime_at_boot_certification")
    global_summary = globals().get("RUNTIME_AT_BOOT_SUMMARY")
    return bool(
        runtime.get("runtime_at_boot_passed", False)
        or (isinstance(summary, dict) and summary.get("passed", False))
        or (isinstance(certification, dict) and certification.get("passed", False))
        or (isinstance(global_summary, dict) and global_summary.get("passed", False))
    )


def _cb11_5_runtime_sessions() -> list[tuple[str, Any]]:
    runtime = _cb11_5_runtime_state()
    rows: list[tuple[str, Any]] = []

    for key, label in [
        ("solver_session", "solver/Athena"),
        ("clerk_session", "clerk/Artemis"),
        ("agent_session", "agent/Aria"),
    ]:
        session = runtime.get(key)
        if session is not None:
            rows.append((label, session))

    seen = {id(session) for _, session in rows}
    runtime_sessions = runtime.get("runtime_sessions")
    if isinstance(runtime_sessions, dict):
        for label, session in runtime_sessions.items():
            if session is not None and id(session) not in seen:
                rows.append((str(label), session))
                seen.add(id(session))

    return rows


def _cb11_5_role_key_from_label(label: str) -> str:
    token = str(label or "").strip().split("/", 1)[0].strip().lower()
    aliases = {
        "athena": "solver",
        "solver": "solver",
        "artemis": "clerk",
        "clerk": "clerk",
        "aria": "agent",
        "agent": "agent",
    }
    return aliases.get(token, token)


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


def _cb11_5_boot_memory_baseline(session: Any, *, role_key: str = "") -> dict[str, Any]:
    baseline = getattr(session, "_cb8_boot_memory_baseline", None)
    if isinstance(baseline, dict) and baseline:
        return dict(baseline)
    runtime = _cb11_5_runtime_state()
    baselines = runtime.get("runtime_at_boot_baselines")
    if isinstance(baselines, dict):
        for key in [str(role_key or "").strip(), _cb11_5_role_key_from_label(str(role_key or ""))]:
            candidate = baselines.get(key)
            if isinstance(candidate, dict) and candidate:
                try:
                    setattr(session, "_cb8_boot_memory_baseline", dict(candidate))
                    setattr(session, "_cb8_boot_memory_baseline_ready", True)
                except Exception:
                    pass
                return dict(candidate)
    return {}


def _cb11_5_restore_boot_memory_baseline(session: Any, *, role_key: str = "") -> dict[str, Any]:
    baseline = _cb11_5_boot_memory_baseline(session, role_key=str(role_key or ""))
    if not baseline:
        return {
            "boot_memory_baseline_present": False,
            "boot_memory_restored": False,
            "boot_memory_baseline_stage": "",
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
            "boot_memory_baseline_stage": str(baseline.get("baseline_stage", "") or ""),
            "boot_memory_dialogue_messages": 0,
            "boot_memory_committed_prompt_tokens": 0,
            "boot_memory_error": str(exc),
        }
    return {
        "boot_memory_baseline_present": True,
        "boot_memory_restored": True,
        "boot_memory_baseline_stage": str(baseline.get("baseline_stage", "") or ""),
        "boot_memory_dialogue_messages": int(len(getattr(session, "dialogue_messages", []) or [])),
        "boot_memory_committed_prompt_tokens": int(getattr(session, "committed_prompt_tokens", 0) or 0),
        "boot_memory_error": "",
    }

def _cb11_5_force_reset_sessions(reason: str) -> dict[str, Any]:
    role_rows: list[dict[str, Any]] = []
    boot_memory_required = bool(_cb11_5_boot_memory_required())

    for label, session in _cb11_5_runtime_sessions():
        role_key = _cb11_5_role_key_from_label(str(label))
        payload = {
            "label": str(label),
            "role_key": str(role_key),
            "reset": False,
            "error": "",
            "boot_memory_required": bool(boot_memory_required),
            "boot_memory_baseline_present": False,
            "boot_memory_restored": False,
            "boot_memory_baseline_stage": "",
            "boot_memory_dialogue_messages": 0,
            "boot_memory_committed_prompt_tokens": 0,
        }
        reset_fn = getattr(session, "reset_session", None)
        if callable(reset_fn):
            try:
                reset_fn()
                payload["reset"] = True
                restore_report = _cb11_5_restore_boot_memory_baseline(session, role_key=str(role_key))
                payload.update(restore_report)
                if boot_memory_required and not bool(restore_report.get("boot_memory_baseline_present", False)):
                    payload["error"] = "missing CB8 boot memory baseline; rerun current CB8 before CB11.5/CB12"
                if str(restore_report.get("boot_memory_error", "") or ""):
                    payload["error"] = str(restore_report.get("boot_memory_error", ""))
            except Exception as exc:
                payload["error"] = str(exc)
        else:
            payload["error"] = "missing reset_session()"
        role_rows.append(payload)

    all_reset = all(bool(row.get("reset")) for row in role_rows) if role_rows else False
    boot_memory_preserved = (
        all(
            bool(row.get("boot_memory_baseline_present", False))
            and bool(row.get("boot_memory_restored", False))
            and not str(row.get("error", "") or "")
            for row in role_rows
        )
        if boot_memory_required and role_rows
        else all(
            (not bool(row.get("boot_memory_baseline_present"))) or bool(row.get("boot_memory_restored"))
            for row in role_rows
        ) if role_rows else False
    )
    report = {
        "event": "cb11_5_problem_boundary_session_reset",
        "revision": CB11_5_ARCHITECTURE_CERTIFICATE_REVISION,
        "reason": str(reason),
        "session_reset_happened": bool(all_reset),
        "all_reset": bool(all_reset),
        "boot_memory_required": bool(boot_memory_required),
        "boot_memory_preserved": bool(boot_memory_preserved),
        "roles": role_rows,
        "printed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(report, flush=True)
    if boot_memory_required and not bool(boot_memory_preserved):
        raise RuntimeError(
            "CB11.5 could not preserve Runtime-at-Boot memory across the problem-boundary reset. "
            "Rerun current CB8, then rerun CB11.5, then CB12."
        )
    return report


def _cb11_5_restore_after_controller_reset(
    *,
    reason: str,
    base_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role_rows: list[dict[str, Any]] = []
    boot_memory_required = bool(_cb11_5_boot_memory_required())

    for label, session in _cb11_5_runtime_sessions():
        role_key = _cb11_5_role_key_from_label(str(label))
        payload = {
            "label": str(label),
            "role_key": str(role_key),
            "boot_memory_required": bool(boot_memory_required),
            "boot_memory_baseline_present": False,
            "boot_memory_restored": False,
            "boot_memory_baseline_stage": "",
            "boot_memory_dialogue_messages": 0,
            "boot_memory_committed_prompt_tokens": 0,
            "error": "",
        }
        restore_report = _cb11_5_restore_boot_memory_baseline(session, role_key=str(role_key))
        payload.update(restore_report)
        if boot_memory_required and not bool(restore_report.get("boot_memory_baseline_present", False)):
            payload["error"] = "missing CB8 boot memory baseline; rerun current CB8 before CB11.5/CB12"
        if str(restore_report.get("boot_memory_error", "") or ""):
            payload["error"] = str(restore_report.get("boot_memory_error", ""))
        role_rows.append(payload)

    boot_memory_preserved = (
        all(
            bool(row.get("boot_memory_baseline_present", False))
            and bool(row.get("boot_memory_restored", False))
            and not str(row.get("error", "") or "")
            for row in role_rows
        )
        if boot_memory_required and role_rows
        else all(
            (not bool(row.get("boot_memory_baseline_present"))) or bool(row.get("boot_memory_restored"))
            for row in role_rows
        ) if role_rows else False
    )
    report = {
        "event": "cb11_5_controller_reset_boot_memory_restore",
        "revision": CB11_5_ARCHITECTURE_CERTIFICATE_REVISION,
        "reason": str(reason),
        "boot_memory_required": bool(boot_memory_required),
        "boot_memory_preserved": bool(boot_memory_preserved),
        "base_all_reset": bool(dict(base_report or {}).get("all_reset", False)),
        "roles": role_rows,
        "printed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(report, flush=True)
    if boot_memory_required and not bool(boot_memory_preserved):
        raise RuntimeError(
            "CB11.5 could not preserve Runtime-at-Boot memory after the controller question reset. "
            "Rerun current CB8, then rerun CB11.5 r5 or newer, then CB12."
        )
    return report


def _cb11_5_preview_prompt_tokens(
    session: Any,
    *,
    prompt: str = "",
    requested_max_tokens: int = 1,
) -> dict[str, Any]:
    preview_fn = globals().get("preview_session_turn_prompt")
    if callable(preview_fn):
        try:
            preview = dict(
                preview_fn(
                    session=session,
                    prompt=str(prompt or ""),
                    requested_max_tokens=max(1, int(requested_max_tokens or 1)),
                )
                or {}
            )
            return {
                "ok": True,
                "prompt_tokens_used": int(preview.get("prompt_tokens_used", 0) or 0),
                "context_limit": int(preview.get("context_limit", getattr(session, "context_limit", 0)) or 0),
                "context_tokens_remaining": int(preview.get("context_tokens_remaining", 0) or 0),
                "resolved_max_tokens": int(preview.get("resolved_max_tokens", 0) or 0),
                "error": "",
            }
        except Exception as exc:
            return {
                "ok": False,
                "prompt_tokens_used": 0,
                "context_limit": int(getattr(session, "context_limit", 0) or 0),
                "context_tokens_remaining": 0,
                "resolved_max_tokens": 0,
                "error": str(exc),
            }

    return {
        "ok": False,
        "prompt_tokens_used": 0,
        "context_limit": int(getattr(session, "context_limit", 0) or 0),
        "context_tokens_remaining": 0,
        "resolved_max_tokens": 0,
        "error": "preview_session_turn_prompt unavailable",
    }


def _cb11_5_session_rows(
    *,
    active_session: Any | None = None,
    active_prompt: str = "",
    requested_max_tokens: int = 1,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for label, session in _cb11_5_runtime_sessions():
        is_active = bool(session is active_session)
        context_limit = int(getattr(session, "context_limit", 0) or 0)
        dialogue_messages = list(getattr(session, "dialogue_messages", []) or [])
        system_prompt = str(getattr(session, "system_prompt", "") or "")

        system_preview = _cb11_5_preview_prompt_tokens(
            session,
            prompt="",
            requested_max_tokens=1,
        )
        turn_preview = _cb11_5_preview_prompt_tokens(
            session,
            prompt=str(active_prompt or "") if is_active else "",
            requested_max_tokens=int(requested_max_tokens or 1),
        )

        committed_prompt_tokens = int(getattr(session, "committed_prompt_tokens", 0) or 0)
        last_prompt_tokens = int(getattr(session, "last_prompt_tokens_used", 0) or 0)
        last_completion_tokens = int(getattr(session, "last_generated_tokens", 0) or 0)

        rows.append(
            {
                "label": str(label),
                "is_active_turn_session": bool(is_active),
                "context_limit": int(context_limit),

                # Current within-problem session state.
                "dialogue_messages_current": int(len(dialogue_messages)),
                "session_history_tokens_current": int(committed_prompt_tokens),

                # Runtime-at-Boot/system-prompt memory.
                "system_prompt_chars": int(len(system_prompt)),
                "system_prompt_tokens_estimate": int(system_preview.get("prompt_tokens_used", 0) or 0),

                # Active turn accounting.
                "active_turn_prompt_tokens_used": int(turn_preview.get("prompt_tokens_used", 0) or 0) if is_active else 0,
                "active_turn_context_remaining": int(turn_preview.get("context_tokens_remaining", 0) or 0) if is_active else 0,
                "active_turn_resolved_max_tokens": int(turn_preview.get("resolved_max_tokens", 0) or 0) if is_active else 0,

                # Previous generated turn diagnostics.
                "last_prompt_tokens": int(last_prompt_tokens),
                "last_completion_tokens": int(last_completion_tokens),
                "last_turn_tokens": int(last_prompt_tokens + last_completion_tokens),

                "preview_error": str(turn_preview.get("error", "") or system_preview.get("error", "") or ""),
            }
        )

    return rows


def _cb11_5_turn_certificate(
    *,
    speaker: str,
    phase: str,
    turn_number: int,
    active_session: Any,
    active_prompt: str,
    generation: dict[str, Any],
) -> dict[str, Any]:
    generation = dict(generation or {})
    requested_max_tokens = int(generation.get("max_tokens", 1) or 1)

    rows = _cb11_5_session_rows(
        active_session=active_session,
        active_prompt=str(active_prompt or ""),
        requested_max_tokens=int(requested_max_tokens),
    )
    active_rows = [row for row in rows if bool(row.get("is_active_turn_session", False))]
    active_row = dict(active_rows[0]) if active_rows else {}

    cert = {
        "event": "cb11_5_pre_turn_architecture_certificate",
        "revision": CB11_5_ARCHITECTURE_CERTIFICATE_REVISION,
        "speaker": str(speaker),
        "phase": str(phase),
        "turn_number": int(turn_number or 0),

        # This must be false in the intended architecture.
        "per_turn_reset_enabled": bool(globals().get("CONTROLLER_RESET_SESSION_EACH_TURN", False)),
        "session_reset_happened_this_turn": False,

        # This is the intended policy.
        "problem_boundary_reset_policy": "before_problem_and_after_problem_only",

        # Active-role state.
        "active_session_label": str(active_row.get("label", "")),
        "active_dialogue_messages_current": int(active_row.get("dialogue_messages_current", 0) or 0),
        "active_session_history_tokens_current": int(active_row.get("session_history_tokens_current", 0) or 0),

        # Runtime-at-Boot/system prompt memory certificate.
        "active_system_prompt_tokens_estimate": int(active_row.get("system_prompt_tokens_estimate", 0) or 0),

        # Active request prompt size.
        "active_turn_prompt_tokens_used": int(active_row.get("active_turn_prompt_tokens_used", 0) or 0),
        "active_turn_context_remaining": int(active_row.get("active_turn_context_remaining", 0) or 0),

        # Distributed context capacity.
        "total_available_tokens": int(sum(int(row.get("context_limit", 0) or 0) for row in rows)),
        "total_system_prompt_tokens_loaded_estimate": int(
            sum(int(row.get("system_prompt_tokens_estimate", 0) or 0) for row in rows)
        ),

        "session_rows": rows,
        "printed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(cert, flush=True)
    return cert


_base_turn = globals().get("_run_model_turn")
if callable(_base_turn) and bool(getattr(_base_turn, "_cb11_5_wrapper", False)):
    _base_turn = globals().get("_CB11_5_BASE_RUN_MODEL_TURN")
if not callable(_base_turn):
    raise NameError("_run_model_turn is not defined. Run Section 07 / CB11 before CB11.5.")
globals()["_CB11_5_BASE_RUN_MODEL_TURN"] = _base_turn

def _run_model_turn(
    *,
    speaker: str,
    phase: str,
    session: Any,
    prompt: str,
    generation: dict[str, Any],
    turn_number: int,
) -> dict[str, Any]:
    # Certificate only. Do NOT reset here.
    _cb11_5_turn_certificate(
        speaker=str(speaker),
        phase=str(phase),
        turn_number=int(turn_number),
        active_session=session,
        active_prompt=str(prompt or ""),
        generation=dict(generation or {}),
    )

    previous_reset_flag = globals().get("CONTROLLER_RESET_SESSION_EACH_TURN", False)
    globals()["CONTROLLER_RESET_SESSION_EACH_TURN"] = False
    try:
        return dict(
            globals()["_CB11_5_BASE_RUN_MODEL_TURN"](
                speaker=speaker,
                phase=phase,
                session=session,
                prompt=prompt,
                generation=generation,
                turn_number=turn_number,
            )
            or {}
        )
    finally:
        globals()["CONTROLLER_RESET_SESSION_EACH_TURN"] = previous_reset_flag


setattr(_run_model_turn, "_cb11_5_wrapper", True)

_base_question_reset = globals().get("_reset_sessions_for_new_question")
if callable(_base_question_reset) and bool(getattr(_base_question_reset, "_cb11_5_wrapper", False)):
    _base_question_reset = globals().get("_CB11_5_BASE_RESET_SESSIONS_FOR_NEW_QUESTION")
if callable(_base_question_reset):
    globals()["_CB11_5_BASE_RESET_SESSIONS_FOR_NEW_QUESTION"] = _base_question_reset

    def _reset_sessions_for_new_question(runtime_state: dict[str, Any]) -> dict[str, Any]:
        base_report = dict(globals()["_CB11_5_BASE_RESET_SESSIONS_FOR_NEW_QUESTION"](runtime_state) or {})
        restore_report = _cb11_5_restore_after_controller_reset(
            reason="controller_question_reset",
            base_report=dict(base_report),
        )
        restore_by_role = {
            str(row.get("role_key", "")): dict(row)
            for row in list(restore_report.get("roles") or [])
            if str(row.get("role_key", "")).strip()
        }
        enriched_roles: list[dict[str, Any]] = []
        for row in list(base_report.get("roles") or []):
            payload = dict(row or {})
            role_key = str(payload.get("role_key", "")).strip().lower()
            restore_row = dict(restore_by_role.get(role_key) or {})
            for key in [
                "boot_memory_required",
                "boot_memory_baseline_present",
                "boot_memory_restored",
                "boot_memory_baseline_stage",
                "boot_memory_dialogue_messages",
                "boot_memory_committed_prompt_tokens",
            ]:
                if key in restore_row:
                    payload[key] = restore_row.get(key)
            restore_error = str(restore_row.get("error", "") or "")
            if restore_error:
                payload["error"] = restore_error
            enriched_roles.append(payload)
        if enriched_roles:
            base_report["roles"] = list(enriched_roles)
        base_report["boot_memory_required"] = bool(restore_report.get("boot_memory_required", False))
        base_report["boot_memory_preserved"] = bool(restore_report.get("boot_memory_preserved", False))
        base_report["cb11_5_boot_memory_restore"] = dict(restore_report)
        return dict(base_report)

    setattr(_reset_sessions_for_new_question, "_cb11_5_wrapper", True)

_base_protocol = globals().get("run_aen_protocol")
if callable(_base_protocol) and bool(getattr(_base_protocol, "_cb11_5_wrapper", False)):
    _base_protocol = globals().get("_CB11_5_BASE_RUN_AEN_PROTOCOL")
if not callable(_base_protocol):
    raise NameError("run_aen_protocol is not defined. Run CB11 before CB11.5.")
globals()["_CB11_5_BASE_RUN_AEN_PROTOCOL"] = _base_protocol

def run_aen_protocol(problem_text: str) -> dict[str, Any]:
    _cb11_5_force_reset_sessions("before_problem")

    try:
        result = dict(globals()["_CB11_5_BASE_RUN_AEN_PROTOCOL"](problem_text) or {})

        token_proof = dict(result.get("token_proof") or {})
        print(
            {
                "event": "cb11_5_problem_finalized_architecture_certificate",
                "revision": CB11_5_ARCHITECTURE_CERTIFICATE_REVISION,
                "question_run_id": str(result.get("question_run_id", "")),
                "status": str(result.get("status", "")),
                "verified": bool(result.get("verified", False)),
                "answer": str(result.get("submission_answer", "")),
                "turns": int(result.get("turn_index", 0) or 0),
                "loops": int(result.get("loop_index", 0) or 0),
                "total_prompt_tokens": int(token_proof.get("total_prompt_tokens", 0) or 0),
                "total_completion_tokens": int(token_proof.get("total_completion_tokens", 0) or 0),
                "total_problem_tokens_used": int(token_proof.get("total_tokens", 0) or 0),
                "problem_boundary_reset_policy": "before_problem_and_after_problem_only",
                "session_rows_before_after_problem_reset": _cb11_5_session_rows(),
            },
            flush=True,
        )

        return result
    finally:
        _cb11_5_force_reset_sessions("after_problem")


setattr(run_aen_protocol, "_cb11_5_wrapper", True)

print(
    {
        "event": "cb11_5_architecture_certificate_wrapper_installed",
        "revision": CB11_5_ARCHITECTURE_CERTIFICATE_REVISION,
        "CONTROLLER_RESET_SESSION_EACH_TURN": bool(CONTROLLER_RESET_SESSION_EACH_TURN),
        "problem_boundary_reset_policy": "before_problem_and_after_problem_only",
        "turn_certificate_does_not_reset": True,
        "controller_question_reset_wrapper_installed": bool(callable(_base_question_reset)),
    },
    flush=True,
)
