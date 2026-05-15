# Auto-extracted by Aster from AENAIMO260_0_2_3_FINAL_CB5_CB8_CLOSED_BOOK_WORKING_20260427.ipynb
# Source cell: 36 / CB08 - Load Athena-Artemis-Aria Sessions
# Intended use: replace/run this CB cell in notebook order.

"""## 08 - Load Athena-Artemis-Aria Sessions


"""

import json
import os
import csv
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

CB08_RUNTIME_REVISION = "2026-04-27-cb08-runtimeatboot-controller-section-wrapper-v1.4.9-clean-information-ack"
CB08_JSON_LOGS = bool(globals().get("CB08_JSON_LOGS", False))


if TYPE_CHECKING:
    # Injected by earlier notebook cells; declared only for static analyzers.
    TORCH_DTYPE_NAME: str
    VLLM_HOST: str
    VLLM_TENSOR_PARALLEL_SIZE: int
    AUTO_REMAP_SERVER_PORT_ON_MODEL_MISMATCH: bool
    PORT_REMAP_START: int
    PORT_REMAP_END: int
    SERVER_START_TIMEOUT_SEC: int
    CLIENT_TIMEOUT_SECONDS: int
    ACTIVE_RUNTIME_PROFILE: str
    PRELOAD_MODEL_WEIGHTS: bool

    SOLVER_MODEL_DIR: str
    SOLVER_MODEL_NAME: str
    SOLVER_RUNTIME_CONTEXT_WINDOW_TOKENS: int
    SOLVER_SERVER_PORT: int
    SOLVER_GPU_MEMORY_UTILIZATION: str
    SOLVER_KV_CACHE_DTYPE: str | None
    SOLVER_REASONING_PARSER: str | None
    SOLVER_ATTENTION_BACKEND: str | None
    SOLVER_LANGUAGE_MODEL_ONLY: bool
    SOLVER_CPU_OFFLOAD_GB: str | None
    SOLVER_ENFORCE_EAGER: bool
    SOLVER_COMPILATION_MODE: int | None
    SOLVER_CUDAGRAPH_MODE: str | None
    SOLVER_DISABLE_COMPILE_CACHE: bool
    SOLVER_DISABLE_HYBRID_KV_CACHE_MANAGER: bool
    SOLVER_ENABLE_THINKING: bool
    SOLVER_ALLOW_ATTACH_MODEL_MISMATCH: bool
    SOLVER_HF_OVERRIDES: dict[str, Any]
    SOLVER_ENV_OVERRIDES: dict[str, Any]

    CLERK_MODEL_DIR: str
    CLERK_MODEL_NAME: str
    CLERK_RUNTIME_CONTEXT_WINDOW_TOKENS: int
    CLERK_SERVER_PORT: int
    CLERK_GPU_MEMORY_UTILIZATION: str
    CLERK_KV_CACHE_DTYPE: str | None
    CLERK_REASONING_PARSER: str | None
    CLERK_ATTENTION_BACKEND: str | None
    CLERK_LANGUAGE_MODEL_ONLY: bool
    CLERK_CPU_OFFLOAD_GB: str | None
    CLERK_ENFORCE_EAGER: bool
    CLERK_COMPILATION_MODE: int | None
    CLERK_CUDAGRAPH_MODE: str | None
    CLERK_DISABLE_COMPILE_CACHE: bool
    CLERK_DISABLE_HYBRID_KV_CACHE_MANAGER: bool
    CLERK_ENABLE_THINKING: bool
    CLERK_ALLOW_ATTACH_MODEL_MISMATCH: bool
    CLERK_HF_OVERRIDES: dict[str, Any]
    CLERK_ENV_OVERRIDES: dict[str, Any]

    AGENT_MODEL_DIR: str
    AGENT_MODEL_NAME: str
    AGENT_RUNTIME_CONTEXT_WINDOW_TOKENS: int
    AGENT_SERVER_PORT: int
    AGENT_GPU_MEMORY_UTILIZATION: str
    AGENT_KV_CACHE_DTYPE: str | None
    AGENT_REASONING_PARSER: str | None
    AGENT_ATTENTION_BACKEND: str | None
    AGENT_LANGUAGE_MODEL_ONLY: bool
    AGENT_CPU_OFFLOAD_GB: str | None
    AGENT_ENFORCE_EAGER: bool
    AGENT_COMPILATION_MODE: int | None
    AGENT_CUDAGRAPH_MODE: str | None
    AGENT_DISABLE_COMPILE_CACHE: bool
    AGENT_DISABLE_HYBRID_KV_CACHE_MANAGER: bool
    AGENT_ENABLE_THINKING: bool
    AGENT_ALLOW_ATTACH_MODEL_MISMATCH: bool
    AGENT_HF_OVERRIDES: dict[str, Any]
    AGENT_ENV_OVERRIDES: dict[str, Any]


def _require_cb07_5_global(name: str) -> Any:
    if name in globals():
        return globals()[name]
    raise NameError(
        f"{name} is not available in notebook globals. "
        "Run CB7.5 before CB08 when runtime support helpers are unavailable."
    )


_CB07_5_REVISION_FALLBACK = str(
    globals().get(
        "CB07_5_DYNAMIC_REVISION",
        globals().get("CB07_CONTROLLER_REVISION", "2026-04-26-aenaimo260-0.2.3"),
    )
)
CB07_5_MEMORY_RUNTIME_REVISION = str(globals().get("CB07_5_MEMORY_RUNTIME_REVISION", _CB07_5_REVISION_FALLBACK))
CB07_5_RUNTIME_CONTEXT_REVISION = str(globals().get("CB07_5_RUNTIME_CONTEXT_REVISION", _CB07_5_REVISION_FALLBACK))


def _cb8_clean(value: Any) -> str:
    cleaner = globals().get("clean_dialogue_text") or globals().get("clean_text")
    if callable(cleaner):
        try:
            return str(cleaner(value)).strip()
        except Exception:
            pass
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _cb8_role_key(runtime_label: str) -> str:
    token = str(runtime_label or "").strip().lower()
    if token in {"athena", "solver"}:
        return "solver"
    if token in {"artemis", "clerk"}:
        return "clerk"
    if token in {"aria", "agent"}:
        return "agent"
    return token or "solver"


def _cb8_runtime_root() -> str:
    root = globals().get("RUNTIME_AT_BOOT_DATASET_ROOT") or globals().get("CANONICAL_RUNTIME_AT_BOOT_DATASET_ROOT")
    return str(root or "").strip()


def _cb8_default_role_boot_paths() -> dict[str, str]:
    root = Path(_cb8_runtime_root()) if _cb8_runtime_root() else Path("")
    return {
        "solver": str(globals().get("ATHENA_BOOT_PATH", root / "boot" / "athena" / "Athena_epistemic_boot_100_final_hq.ndjson")),
        "clerk": str(globals().get("ARTEMIS_BOOT_PATH", root / "boot" / "artemis" / "Artemis_problem_proof_boot_100_final_hq.ndjson")),
        "agent": str(globals().get("ARIA_BOOT_PATH", root / "boot" / "aria" / "Aria_problem_proof_boot_100_final.ndjson")),
    }


def _cb8_cert_path_from_boot_path(path_value: Any, filename: str) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""
    return str(Path(raw).expanduser().with_name(filename))


def _cb8_default_role_certification_paths(role_paths: dict[str, str]) -> dict[str, str]:
    return {
        "solver": str(
            globals().get("ATHENA_BOOT_CERTIFICATION_PATH")
            or _cb8_cert_path_from_boot_path(role_paths.get("solver", ""), "Athena_epistemic_boot_100_final_certification_hq.ndjson")
        ),
        "clerk": str(
            globals().get("ARTEMIS_BOOT_CERTIFICATION_PATH")
            or _cb8_cert_path_from_boot_path(role_paths.get("clerk", ""), "Artemis_problem_proof_boot_100_final_hq_mcq.ndjson")
        ),
        "agent": str(
            globals().get("ARIA_BOOT_CERTIFICATION_PATH")
            or _cb8_cert_path_from_boot_path(role_paths.get("agent", ""), "Aria_problem_proof_boot_100_final_mcq_2q.ndjson")
        ),
    }

def _cb8_session_for_label(runtime: dict[str, Any], runtime_label: str) -> Any:
    key = _cb8_role_key(runtime_label)
    runtime_sessions = dict(runtime.get("runtime_sessions") or {}) if isinstance(runtime.get("runtime_sessions"), dict) else {}
    if key in runtime_sessions:
        return runtime_sessions[key]
    return runtime.get(f"{key}_session")


def _cb8_read_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidate = Path(str(path or "")).expanduser()
    if not str(path or "").strip() or not candidate.exists():
        return rows
    for raw_line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(dict(payload))
    return rows


def _cb8_first_text(*values: Any) -> str:
    for value in values:
        text = _cb8_clean(value)
        if text:
            return text
    return ""


def _cb8_probes_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    row_data = dict(row or {})
    raw_probes = [dict(item) for item in list(row_data.get("probes") or []) if isinstance(item, dict)]
    probe_sources = raw_probes if raw_probes else [dict(row_data)]
    probe_total = len(probe_sources)
    normalized: list[dict[str, Any]] = []
    for probe_ordinal, probe in enumerate(probe_sources, start=1):
        prompt = _cb8_first_text(
            probe.get("probe_prompt"),
            probe.get("question"),
            row_data.get("probe_prompt"),
            row_data.get("question"),
        )
        expected = _cb8_first_text(
            probe.get("expected_answer"),
            probe.get("probe_answer"),
            probe.get("answer"),
            row_data.get("expected_answer"),
            row_data.get("probe_answer"),
            row_data.get("answer"),
        ).upper()[:1]
        options = [str(item) for item in list(probe.get("options") or row_data.get("options") or [])]
        probe_id = _cb8_first_text(
            probe.get("probe_id"),
            probe.get("probe_source_id"),
            probe.get("id"),
            row_data.get("probe_id"),
            row_data.get("probe_source_id"),
            row_data.get("id"),
            row_data.get("line_id"),
            f"line_{probe_ordinal}",
        )
        normalized.append(
            {
                "probe_id": probe_id,
                "probe_ordinal": int(probe_ordinal),
                "probe_total": int(probe_total),
                "probe_prompt": prompt,
                "expected_answer": expected,
                "options": options,
                "probe_ready": bool(prompt and expected in {"A", "B", "C", "D"}),
            }
        )
    return normalized


def _cb8_probe_from_row(row: dict[str, Any]) -> dict[str, Any]:
    probes = _cb8_probes_from_row(row)
    return probes[0] if probes else {"probe_ready": False}

def _cb8_choice(value: Any) -> str:
    text = _cb8_clean(value).upper()
    match = re.search(r"\b([ABCD])\b", text)
    if match:
        return str(match.group(1))
    return text[:1] if text[:1] in {"A", "B", "C", "D"} else ""


def _cb8_json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(dict(payload or {}), ensure_ascii=False, separators=(",", ":")), flush=True)


def _cb8_boot_memory_ack_text() -> str:
    ack_text = _cb8_clean(globals().get("BOOT_MEMORY_ACK_TEXT", "AEN_BOOT_INFORMATION_ASSIMILATED"))
    return ack_text or "AEN_BOOT_INFORMATION_ASSIMILATED"


def _cb8_execute_controller_turn(session: Any, prompt: str, generation_profile: dict[str, Any]) -> dict[str, Any]:
    previous_stream_flag = globals().get("ENABLE_TOKEN_STREAMING")
    previous_stream_prefix = globals().get("STREAM_PRINT_ROLE_PREFIX")
    silent_stream = bool(globals().get("BOOT_SILENT_CONTROLLER_STREAM", False))
    try:
        if silent_stream:
            globals()["ENABLE_TOKEN_STREAMING"] = False
            globals()["STREAM_PRINT_ROLE_PREFIX"] = False
        return dict(session.execute_user_turn(str(prompt), dict(generation_profile or {})) or {})
    finally:
        if silent_stream:
            if previous_stream_flag is None:
                globals().pop("ENABLE_TOKEN_STREAMING", None)
            else:
                globals()["ENABLE_TOKEN_STREAMING"] = previous_stream_flag
            if previous_stream_prefix is None:
                globals().pop("STREAM_PRINT_ROLE_PREFIX", None)
            else:
                globals()["STREAM_PRINT_ROLE_PREFIX"] = previous_stream_prefix


def _cb8_line_limit(key: str, fallback: int = 25) -> int:
    names = {
        "solver": "ATHENA_BOOT_CERTIFICATION_LINE_LIMIT",
        "clerk": "ARTEMIS_BOOT_CERTIFICATION_LINE_LIMIT",
        "agent": "ARIA_BOOT_CERTIFICATION_LINE_LIMIT",
    }
    try:
        requested = max(
            0,
            int(
                globals().get(
                    names.get(key, ""),
                    globals().get("BOOT_CERTIFICATION_LINE_LIMIT", fallback),
                )
                or fallback
            ),
        )
    except Exception:
        requested = int(fallback)
    try:
        cap = max(0, int(globals().get("BOOT_CERTIFICATION_MAX_TEST_LINES", fallback) or fallback))
    except Exception:
        cap = int(fallback)
    return min(int(requested), int(cap)) if cap > 0 else int(requested)


def _cb8_boot_memory_records(key: str) -> list[dict[str, Any]]:
    rows = _cb8_read_jsonl(str(ROLE_BOOT_PATHS.get(key) or ""))
    records: list[dict[str, Any]] = []
    for line_no, row in enumerate(rows, start=1):
        text = _cb8_first_text(
            row.get("text"),
            row.get("study_text"),
            row.get("content"),
            row.get("memory"),
            row.get("record"),
        )
        if not text:
            continue
        line_id = _cb8_first_text(row.get("line_id"), row.get("id"), f"{key}_boot_{line_no}")
        records.append(
            {
                "line_no": int(line_no),
                "line_id": str(line_id),
                "text": str(text),
            }
        )
    return records


def _cb8_memory_chunks(records: list[dict[str, Any]], *, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0
    limit = max(1000, int(max_chars))
    for record in records:
        entry = (
            f"BOOT_RECORD line_no={int(record.get('line_no', 0))} "
            f"line_id={record.get('line_id', '')}\n"
            f"{_cb8_clean(record.get('text', ''))}"
        ).strip()
        if not entry:
            continue
        entry_chars = len(entry) + 2
        if current and current_chars + entry_chars > limit:
            chunks.append("\n\n".join(current).strip())
            current = []
            current_chars = 0
        current.append(entry)
        current_chars += entry_chars
    if current:
        chunks.append("\n\n".join(current).strip())
    return chunks


def _cb8_study_boot_memory_layer(
    session: Any,
    *,
    key: str,
    role_name: str,
    generation_profile: dict[str, Any],
) -> dict[str, Any]:
    records = _cb8_boot_memory_records(str(key))
    try:
        chunk_chars = max(1000, int(globals().get("BOOT_MEMORY_STUDY_CHUNK_CHARS", 24000) or 24000))
    except Exception:
        chunk_chars = 24000
    chunks = _cb8_memory_chunks(records, max_chars=int(chunk_chars))
    study_profile = dict(generation_profile or {})
    try:
        ack_tokens = max(1, int(globals().get("BOOT_MEMORY_STUDY_MAX_TOKENS", 16) or 16))
    except Exception:
        ack_tokens = 16
    for token_key in ("max_tokens", "max_new_tokens"):
        if token_key in study_profile:
            try:
                study_profile[token_key] = min(max(1, int(study_profile.get(token_key) or ack_tokens)), int(ack_tokens))
            except Exception:
                study_profile[token_key] = int(ack_tokens)
    study_profile.setdefault("max_tokens", int(ack_tokens))
    study_profile.setdefault("temperature", 0)
    if hasattr(session, "reset_session"):
        try:
            session.reset_session()
        except Exception:
            pass
    ack_texts: list[str] = []
    started = time.perf_counter()
    for chunk_index, chunk in enumerate(chunks, start=1):
        if bool(globals().get("BOOT_PRINT_MEMORY_STUDY_CHUNKS", False)):
            _cb8_json_print(
                {
                    "event": "runtime_at_boot_memory_study_chunk",
                    "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
                    "runtime_label": str(key),
                    "role_name": str(role_name),
                    "chunk_index": int(chunk_index),
                    "chunk_count": int(len(chunks)),
                    "memory_line_count": int(len(records)),
                    "chunk_chars": int(len(chunk)),
                    "boot_records_verbatim": str(chunk),
                }
            )
        prompt = (
            f"You are {role_name}.\n"
            "Runtime-at-Boot memory study layer.\n"
            "Read and retain the following boot records as active operating memory for this benchmark session.\n"
            "These records are canonical memory context; do not solve a benchmark problem yet.\n"
            f"Reply exactly: {_cb8_boot_memory_ack_text()}\n\n"
            f"Chunk {chunk_index} of {len(chunks)}:\n{chunk}"
        ).strip()
        response_payload = _cb8_execute_controller_turn(session, prompt, dict(study_profile))
        ack_texts.append(
            _cb8_clean(
                response_payload.get("visible_text")
                or response_payload.get("raw_text")
                or response_payload.get("output_text")
                or response_payload.get("response_text")
                or response_payload.get("text")
            )
        )
    report = {
        "event": "runtime_at_boot_memory_study",
        "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
        "runtime_label": str(key),
        "role_name": str(role_name),
        "status": "studied" if records else "empty",
        "memory_studied": bool(records),
        "memory_line_count": int(len(records)),
        "memory_chunk_count": int(len(chunks)),
        "ack_count": int(len(ack_texts)),
        "ack_text": str(_cb8_boot_memory_ack_text()),
        "ack_texts": list(ack_texts) if bool(globals().get("BOOT_PRINT_MEMORY_ACK_TEXTS", False)) else [],
        "elapsed_seconds": round(float(time.perf_counter() - started), 4),
    }
    _cb8_json_print(report)
    return report


def _cb8_copy_dialogue_messages(value: Any) -> list[dict[str, str]]:
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


def _cb8_capture_boot_memory_baseline(session: Any, memory_report: dict[str, Any]) -> dict[str, Any]:
    baseline = {
        "event": "runtime_at_boot_memory_baseline_captured",
        "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
        "memory_report": dict(memory_report or {}),
        "dialogue_messages": _cb8_copy_dialogue_messages(getattr(session, "dialogue_messages", [])),
        "visible_transcript": _cb8_copy_dialogue_messages(getattr(session, "visible_transcript", [])),
        "original_problem_text": str(getattr(session, "original_problem_text", "") or ""),
        "committed_prompt_tokens": int(getattr(session, "committed_prompt_tokens", 0) or 0),
        "last_prompt_tokens_used": int(getattr(session, "last_prompt_tokens_used", 0) or 0),
        "last_generated_tokens": int(getattr(session, "last_generated_tokens", 0) or 0),
    }
    try:
        setattr(session, "_cb8_boot_memory_baseline", dict(baseline))
        setattr(session, "_cb8_boot_memory_baseline_ready", True)
    except Exception:
        pass
    _cb8_json_print(
        {
            "event": "runtime_at_boot_memory_baseline_captured",
            "runtime_label": str(dict(memory_report or {}).get("runtime_label", "")),
            "role_name": str(dict(memory_report or {}).get("role_name", "")),
            "memory_line_count": int(dict(memory_report or {}).get("memory_line_count", 0) or 0),
            "dialogue_messages": int(len(baseline["dialogue_messages"])),
            "committed_prompt_tokens": int(baseline["committed_prompt_tokens"]),
        }
    )
    return dict(baseline)


ROLE_BOOT_PATHS = dict(globals().get("ROLE_BOOT_PATHS") or _cb8_default_role_boot_paths())
ROLE_BOOT_CERTIFICATION_PATHS = dict(
    globals().get("ROLE_BOOT_CERTIFICATION_PATHS") or _cb8_default_role_certification_paths(ROLE_BOOT_PATHS)
)
RUNTIME_AT_BOOT_DATASET_ROOT = str(globals().get("RUNTIME_AT_BOOT_DATASET_ROOT", _cb8_runtime_root()) or _cb8_runtime_root())


def _cb8_default_apply_context_runtime_boot_overrides(global_state: dict[str, Any]) -> dict[str, Any]:
    report = {
        "event": "context_runtime_boot_context",
        "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
        "enabled": True,
        "status": "session_memory_layer_pending",
        "reason": "CB8 studies Runtime-at-Boot records into each role session before MCQ certification; system prompts and prompt files are untouched.",
        "boot_paths": {key: str(path) for key, path in ROLE_BOOT_PATHS.items()},
        "certification_paths": {key: str(path) for key, path in ROLE_BOOT_CERTIFICATION_PATHS.items()},
        "certification_test_line_cap": int(_cb8_line_limit("solver")),
        "boot_memory_ack_text": str(_cb8_boot_memory_ack_text()),
        "boot_print_memory_study_chunks": bool(globals().get("BOOT_PRINT_MEMORY_STUDY_CHUNKS", False)),
        "boot_print_certification_prompts": bool(globals().get("BOOT_PRINT_CERTIFICATION_PROMPTS", False)),
        "boot_print_certification_full_text": bool(globals().get("BOOT_PRINT_CERTIFICATION_FULL_TEXT", False)),
        "boot_silent_controller_stream": bool(globals().get("BOOT_SILENT_CONTROLLER_STREAM", False)),
    }
    global_state["CONTEXT_RUNTIME_BOOT_APPLIED"] = True
    global_state["CONTEXT_RUNTIME_BOOT_PACK_STATUS"] = dict(report)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")), flush=True)
    return report


def _cb8_default_run_context_runtime_boot_validation(global_state: dict[str, Any], *, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = runtime
    report = {
        "event": "context_runtime_boot_validation",
        "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
        "enabled": False,
        "status": "not_required",
        "pass_rate": 1.0,
    }
    global_state["CONTEXT_RUNTIME_BOOT_VALIDATION"] = dict(report)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")), flush=True)
    return report


def _cb8_default_run_boot_certification_gate(
    runtime: dict[str, Any],
    *,
    runtime_label: str,
    generation_profile: dict[str, Any],
    line_limit: int | None = None,
    max_attempts_per_line: int | None = None,
    reset_session_after_gate: bool = True,
) -> dict[str, Any]:
    key = _cb8_role_key(runtime_label)
    role_names = {"solver": "Athena", "clerk": "Artemis", "agent": "Aria"}
    role_name = role_names.get(key, key)
    session = _cb8_session_for_label(dict(runtime or {}), key)
    if session is None:
        raise RuntimeError(f"No runtime session is available for {role_name}.")
    source_path = str(ROLE_BOOT_CERTIFICATION_PATHS.get(key) or ROLE_BOOT_PATHS.get(key) or "")
    rows = _cb8_read_jsonl(source_path)
    effective_limit = _cb8_line_limit(key) if line_limit is None else max(0, int(line_limit))
    if effective_limit > 0:
        rows = rows[:effective_limit]
    max_attempts = max(1, int(max_attempts_per_line or globals().get("BOOT_MAX_ATTEMPTS_PER_LINE", 3) or 3))
    log_rows: list[dict[str, Any]] = []
    certified_count = 0
    certified_probe_count = 0
    attempted_probe_count = 0
    blocked_reason = ""
    started = time.perf_counter()
    memory_report: dict[str, Any] = {}
    memory_baseline: dict[str, Any] = {}
    try:
        memory_report = dict(
            _cb8_study_boot_memory_layer(
                session,
                key=str(key),
                role_name=str(role_name),
                generation_profile=dict(generation_profile or {}),
            )
            or {}
        )
        memory_baseline = dict(_cb8_capture_boot_memory_baseline(session, memory_report) or {})
        for line_no, row in enumerate(rows, start=1):
            probes = _cb8_probes_from_row(row)
            if not probes or not all(bool(probe.get("probe_ready")) for probe in probes):
                blocked_reason = f"Boot line {row.get('line_id', line_no)} has no ready deterministic probe."
                break
            study_text = _cb8_clean(row.get("text") or row.get("study_text") or "")
            line_certified = True
            for probe in probes:
                attempted_probe_count += 1
                options = "\n".join(
                    f"{chr(65 + idx)}. {option}"
                    for idx, option in enumerate(list(probe.get("options") or []))
                )
                prompt = (
                    f"You are {role_name}.\n"
                    "Runtime-at-Boot certification test layer.\n"
                    "Use the studied boot memory plus the verbatim certification line below.\n"
                    "Answer the multiple-choice question and reply with exactly one capital letter.\n"
                    "Allowed replies: A, B, C, D.\n"
                    "No explanation.\n\n"
                    f"Certification Line Verbatim Context:\n{study_text}\n\n"
                    f"Question:\n{probe.get('probe_prompt', '')}\n\n"
                    f"Options:\n{options}"
                ).strip()
                if bool(globals().get("BOOT_PRINT_CERTIFICATION_PROMPTS", False)):
                    _cb8_json_print(
                        {
                            "event": "runtime_at_boot_cert_prompt",
                            "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
                            "runtime_label": str(key),
                            "role_name": str(role_name),
                            "line_no": int(line_no),
                            "line_id": str(row.get("line_id", "")),
                            "probe_id": str(probe.get("probe_id", "")),
                            "probe_ordinal": int(probe.get("probe_ordinal", 1)),
                            "line_probe_count": int(probe.get("probe_total", len(probes))),
                            "certification_line_verbatim": str(study_text),
                            "question": str(probe.get("probe_prompt", "")),
                            "options": list(probe.get("options") or []),
                            "prompt_verbatim": str(prompt),
                        }
                    )
                correct = False
                provided = ""
                for attempt_no in range(1, max_attempts + 1):
                    turn_started = time.perf_counter()
                    response_payload = _cb8_execute_controller_turn(session, prompt, dict(generation_profile or {}))
                    response_text = _cb8_clean(
                        response_payload.get("visible_text")
                        or response_payload.get("raw_text")
                        or response_payload.get("output_text")
                        or response_payload.get("response_text")
                        or response_payload.get("text")
                    )
                    provided = _cb8_choice(response_text)
                    correct = bool(provided and provided == str(probe.get("expected_answer", "")).strip().upper()[:1])
                    log_rows.append(
                        {
                            "role": str(role_name),
                            "runtime_label": str(key),
                            "line_no": int(line_no),
                            "line_id": str(row.get("line_id", "")),
                            "probe_id": str(probe.get("probe_id", "")),
                            "probe_no": int(probe.get("probe_ordinal", 1)),
                            "probe_total": int(probe.get("probe_total", len(probes))),
                            "probe_ordinal": int(probe.get("probe_ordinal", 1)),
                            "line_probe_count": int(probe.get("probe_total", len(probes))),
                            "question": str(probe.get("probe_prompt", "")),
                            "attempt_no": int(attempt_no),
                            "provided_answer": str(provided),
                            "expected_answer": str(probe.get("expected_answer", "")),
                            "correct": bool(correct),
                            "status": "certified" if correct else "retry_or_failed",
                            "elapsed_seconds": round(float(time.perf_counter() - turn_started), 4),
                        }
                    )
                    if bool(globals().get("BOOT_PRINT_CERTIFICATION_LINES", True)):
                        full_text_enabled = bool(globals().get("BOOT_PRINT_CERTIFICATION_FULL_TEXT", False))
                        _cb8_json_print(
                            {
                                "event": "runtime_at_boot_cert_line",
                                "runtime_label": str(key),
                                "role_name": str(role_name),
                                "line_no": int(line_no),
                                "line_id": str(row.get("line_id", "")),
                                "probe_id": str(probe.get("probe_id", "")),
                                "probe_ordinal": int(probe.get("probe_ordinal", 1)),
                                "line_probe_count": int(probe.get("probe_total", len(probes))),
                                "attempt_no": int(attempt_no),
                                "provided_answer": str(provided),
                                "expected_answer": str(probe.get("expected_answer", "")),
                                "correct": bool(correct),
                                "status": "certified" if correct else "retry_or_failed",
                                "elapsed_seconds": log_rows[-1].get("elapsed_seconds"),
                                "certification_line_verbatim": str(study_text) if full_text_enabled else "",
                                "question": str(probe.get("probe_prompt", "")) if full_text_enabled else "",
                                "options": list(probe.get("options") or []) if full_text_enabled else [],
                                "response_text": str(response_text) if full_text_enabled else "",
                            }
                        )
                    if correct:
                        certified_probe_count += 1
                        break
                if not correct:
                    line_certified = False
                    blocked_reason = (
                        f"Boot line {row.get('line_id', line_no)} probe "
                        f"{probe.get('probe_ordinal', 1)}/{probe.get('probe_total', len(probes))} failed certification."
                    )
                    break
            if line_certified:
                certified_count += 1
            else:
                break
        status = "certified" if rows and certified_count == len(rows) and not blocked_reason else "blocked"
        if not rows:
            status = "empty"
        return {
            "event": "runtime_at_boot_gate",
            "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
            "runtime_label": str(key),
            "role_name": str(role_name),
            "status": str(status),
            "passed": bool(status in {"certified", "empty"}),
            "line_count": int(len(rows)),
            "certified_count": int(certified_count),
            "probe_count": int(attempted_probe_count),
            "certified_probe_count": int(certified_probe_count),
            "blocked_reason": str(blocked_reason),
            "certification_source_path": str(source_path),
            "certification_line_limit": int(effective_limit),
            "max_attempts_per_line": int(max_attempts),
            "memory_study": dict(memory_report),
            "memory_baseline": {
                "captured": bool(memory_baseline),
                "dialogue_messages": int(len(list(memory_baseline.get("dialogue_messages") or []))),
                "committed_prompt_tokens": int(memory_baseline.get("committed_prompt_tokens", 0) or 0),
            },
            "memory_studied": bool(memory_report.get("memory_studied", False)),
            "memory_line_count": int(memory_report.get("memory_line_count", 0) or 0),
            "memory_chunk_count": int(memory_report.get("memory_chunk_count", 0) or 0),
            "log_rows": list(log_rows),
            "state": {
                "runtime_label": str(key),
                "role_name": str(role_name),
                "status": str(status),
                "line_count": int(len(rows)),
                "certified_count": int(certified_count),
                "probe_count": int(attempted_probe_count),
                "certified_probe_count": int(certified_probe_count),
                "blocked_reason": str(blocked_reason),
                "memory_studied": bool(memory_report.get("memory_studied", False)),
                "memory_line_count": int(memory_report.get("memory_line_count", 0) or 0),
            },
            "elapsed_seconds": round(float(time.perf_counter() - started), 4),
        }
    finally:
        if bool(reset_session_after_gate) and hasattr(session, "reset_session"):
            try:
                session.reset_session()
            except Exception:
                pass


def _cb8_default_append_boot_certified_memory_to_session(session: Any, report: dict[str, Any]) -> str:
    _ = session
    memory_report = dict(dict(report or {}).get("memory_study") or {})
    if not memory_report:
        return ""
    return str(memory_report.get("status", ""))


apply_context_runtime_boot_overrides = cast(
    Callable[..., dict[str, Any]],
    globals().get("apply_context_runtime_boot_overrides") or _cb8_default_apply_context_runtime_boot_overrides,
)
run_context_runtime_boot_validation = cast(
    Callable[..., dict[str, Any]],
    globals().get("run_context_runtime_boot_validation") or _cb8_default_run_context_runtime_boot_validation,
)
run_boot_certification_gate = cast(
    Callable[..., dict[str, Any]],
    globals().get("run_boot_certification_gate") or _cb8_default_run_boot_certification_gate,
)
append_boot_certified_memory_to_session = cast(
    Callable[..., str],
    globals().get("append_boot_certified_memory_to_session") or _cb8_default_append_boot_certified_memory_to_session,
)


DEPENDENCY_BLOCK_HINTS = {
    "cleanup_runtime": "CB6",
    "preload_model_weights": "CB6",
    "load_vllm_openai_session": "CB6",
}

CB8_RUNTIME_REQUIREMENT_NOTE = "CB8 depends on CB4, CB6, CB6.5, CB7, and CB7.5 only."
RUNTIME_BOOT_ARTIFACT_DIR = Path(
    str(
        globals().get(
            "LOCAL_SMOKE_ARTIFACT_DIR",
            "kaggle_aimo3/AENAIMO260_0_2_3/artifacts",
        )
    )
)


def _cb8_missing_state_message(detail: str) -> str:
    return (
        f"{detail} "
        "Run CB4, CB6, and CB6.5 in this kernel, then rerun CB8. "
        + str(CB8_RUNTIME_REQUIREMENT_NOTE)
    )


def _extract_missing_name(exc: NameError) -> str:
    message = str(exc)
    marker = "name '"
    if marker in message:
        tail = message.split(marker, 1)[1]
        return str(tail.split("'", 1)[0]).strip() or "<unknown>"
    return "<unknown>"


def _require_notebook_callable(name: str, value: Any | None = None) -> Callable[..., Any]:
    if value is None:
        value = globals().get(name)
    if callable(value):
        return cast(Callable[..., Any], value)
    hinted_block = DEPENDENCY_BLOCK_HINTS.get(str(name))
    if hinted_block:
        raise NameError(_cb8_missing_state_message(f"{name} is not defined in this kernel. Run {hinted_block} first, then rerun CB8."))
    raise NameError(_cb8_missing_state_message(f"{name} is not defined."))


def require_cb08_dependencies() -> None:
    missing: list[str] = []
    for name in DEPENDENCY_BLOCK_HINTS:
        if not callable(globals().get(name)):
            missing.append(name)
    if missing:
        raise RuntimeError(_cb8_missing_state_message(f"CB8 dependencies are missing in this kernel: {missing}."))


def resolve_runtime_label(role_or_alias: str, fallback: str) -> str:
    resolver = globals().get("runtime_label_for_role")
    if callable(resolver):
        try:
            label = str(resolver(str(role_or_alias), default=str(fallback))).strip()
            if label:
                return label
        except Exception:
            pass
    return str(fallback).strip() or str(role_or_alias).strip() or "solver"


def resolve_role_name(runtime_label: str, fallback: str) -> str:
    resolver = globals().get("role_name_for_runtime_label")
    if callable(resolver):
        try:
            name = str(resolver(str(runtime_label), default=str(fallback))).strip()
            if name:
                return name
        except Exception:
            pass
    return str(fallback).strip() or str(runtime_label).strip()


SOLVER_RUNTIME_LABEL = resolve_runtime_label("solver", "solver")
CLERK_RUNTIME_LABEL = resolve_runtime_label("clerk", "clerk")
AGENT_RUNTIME_LABEL = resolve_runtime_label("agent", "agent")

SOLVER_DISPLAY_NAME = resolve_role_name(SOLVER_RUNTIME_LABEL, str(globals().get("SOLVER_ROLE_NAME", "Athena")))
CLERK_DISPLAY_NAME = resolve_role_name(CLERK_RUNTIME_LABEL, str(globals().get("CLERK_ROLE_NAME", "Artemis")))
AGENT_DISPLAY_NAME = resolve_role_name(AGENT_RUNTIME_LABEL, str(globals().get("AGENT_ROLE_NAME", "Aria")))


def initialize_cb08_role_prompts() -> dict[str, str]:
    identity_builder = globals().get("build_role_identity_prompt")
    prompts = {
        str(SOLVER_RUNTIME_LABEL): (
            str(identity_builder(str(SOLVER_RUNTIME_LABEL))).strip()
            if callable(identity_builder)
            else f"You are {SOLVER_DISPLAY_NAME}."
        ),
        str(CLERK_RUNTIME_LABEL): (
            str(identity_builder(str(CLERK_RUNTIME_LABEL))).strip()
            if callable(identity_builder)
            else f"You are {CLERK_DISPLAY_NAME}."
        ),
        str(AGENT_RUNTIME_LABEL): (
            str(identity_builder(str(AGENT_RUNTIME_LABEL))).strip()
            if callable(identity_builder)
            else f"You are {AGENT_DISPLAY_NAME}."
        ),
    }
    globals()["ATHENA_SESSION_PROMPT"] = str(prompts[str(SOLVER_RUNTIME_LABEL)])
    globals()["ARTEMIS_SESSION_PROMPT"] = str(prompts[str(CLERK_RUNTIME_LABEL)])
    globals()["ARIA_SESSION_PROMPT"] = str(prompts[str(AGENT_RUNTIME_LABEL)])
    globals()["AGENT_SESSION_PROMPT"] = str(prompts[str(AGENT_RUNTIME_LABEL)])
    globals()["SOLVER_CONVERSATION_SYSTEM_PROMPT"] = str(prompts[str(SOLVER_RUNTIME_LABEL)])
    globals()["CLERK_CONVERSATION_SYSTEM_PROMPT"] = str(prompts[str(CLERK_RUNTIME_LABEL)])
    globals()["AGENT_CONVERSATION_SYSTEM_PROMPT"] = str(prompts[str(AGENT_RUNTIME_LABEL)])
    return prompts


def resolve_runtime_device() -> str:
    device = str(
        globals().get("VLLM_TARGET_DEVICE")
        or os.environ.get("VLLM_TARGET_DEVICE")
        or "cuda"
    ).strip().lower()
    return device or "cuda"


def normalize_cuda_visible_devices(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    tokens = [str(token).strip() for token in text.split(",") if str(token).strip()]
    if not tokens:
        return ""
    valid: list[str] = []
    for token in tokens:
        if token.isdigit() or token.startswith("GPU-") or token.startswith("MIG-"):
            valid.append(token)
    if not valid:
        return ""
    return ",".join(valid)


def build_runtime_env_overrides(env_overrides: dict[str, Any]) -> dict[str, str]:
    target_device = resolve_runtime_device()
    merged: dict[str, str] = {
        "TRANSFORMERS_NO_TF": "1",
        "TRANSFORMERS_NO_FLAX": "1",
        "USE_TF": "0",
        "USE_FLAX": "0",
        "TOKENIZERS_PARALLELISM": "false",
        "VLLM_TARGET_DEVICE": str(target_device),
        "VLLM_DEVICE": str(target_device),
        "VLLM_LOGGING_LEVEL": str(
            globals().get("VLLM_LOGGING_LEVEL") or os.environ.get("VLLM_LOGGING_LEVEL") or "INFO"
        ).strip()
        or "INFO",
    }
    cuda_visible_devices = normalize_cuda_visible_devices(
        globals().get("CUDA_VISIBLE_DEVICES") or os.environ.get("CUDA_VISIBLE_DEVICES") or ""
    )
    if str(cuda_visible_devices).strip():
        merged["CUDA_VISIBLE_DEVICES"] = str(cuda_visible_devices)
    for key, value in dict(env_overrides or {}).items():
        merged[str(key)] = str(value)
    return merged


def build_session_spec(
    *,
    runtime_label: str,
    model_dir: str,
    served_model_name: str,
    context_limit: int,
    system_prompt: str,
    server_port: int,
    gpu_memory_utilization: str,
    kv_cache_dtype: str | None,
    reasoning_parser: str | None,
    attention_backend: str | None,
    language_model_only: bool,
    cpu_offload_gb: str | None,
    enforce_eager: bool,
    compilation_mode: int | None,
    cudagraph_mode: str | None,
    disable_compile_cache: bool,
    disable_hybrid_kv_cache_manager: bool,
    enable_thinking: bool,
    allow_attach_model_mismatch: bool,
    hf_overrides: dict[str, Any] | None,
    env_overrides: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_label": str(runtime_label),
        "runtime_backend": "vllm_openai",
        "model_dir": str(model_dir),
        "served_model_name": str(served_model_name),
        "device": resolve_runtime_device(),
        "context_limit": int(context_limit),
        "torch_dtype": TORCH_DTYPE_NAME,
        "system_prompt": str(system_prompt),
        "server_host": VLLM_HOST,
        "server_port": int(server_port),
        "server_base_url": f"http://{VLLM_HOST}:{int(server_port)}/v1",
        "tensor_parallel_size": int(VLLM_TENSOR_PARALLEL_SIZE),
        "gpu_memory_utilization": str(gpu_memory_utilization),
        "kv_cache_dtype": kv_cache_dtype,
        "reasoning_parser": reasoning_parser,
        "attention_backend": attention_backend,
        "language_model_only": bool(language_model_only),
        "trust_remote_code": True,
        "cpu_offload_gb": cpu_offload_gb,
        "enforce_eager": bool(enforce_eager),
        "compilation_mode": compilation_mode,
        "cudagraph_mode": cudagraph_mode,
        "disable_compile_cache": bool(disable_compile_cache),
        "disable_hybrid_kv_cache_manager": bool(disable_hybrid_kv_cache_manager),
        "enable_thinking": False,
        "allow_attach_model_mismatch": bool(allow_attach_model_mismatch),
        "hf_overrides": dict(hf_overrides or {}),
        "auto_remap_server_port_on_model_mismatch": bool(AUTO_REMAP_SERVER_PORT_ON_MODEL_MISMATCH),
        "port_remap_start": int(PORT_REMAP_START),
        "port_remap_end": int(PORT_REMAP_END),
        "env_overrides": build_runtime_env_overrides(env_overrides),
        "server_start_timeout_sec": int(SERVER_START_TIMEOUT_SEC),
        "client_timeout_seconds": int(CLIENT_TIMEOUT_SECONDS),
        "force_restart_managed_runtime": bool(globals().get("MANAGED_VLLM_FORCE_RESTART", False)),
    }


def print_runtime_spec(event_name: str, label: str, spec: dict[str, Any]) -> None:
    rope_parameters = (
        dict(dict(dict(spec.get("hf_overrides") or {}).get("text_config") or {}).get("rope_parameters") or {})
        if isinstance(spec.get("hf_overrides"), dict)
        else {}
    )
    payload = {
        "event": event_name,
        "label": str(label),
        "runtime_profile": ACTIVE_RUNTIME_PROFILE,
        "runtime_label": str(spec["runtime_label"]),
        "model_dir": str(spec["model_dir"]),
        "served_model_name": str(spec["served_model_name"]),
        "device": str(spec.get("device", "")),
        "context_limit": int(spec["context_limit"]),
        "server_base_url": str(spec["server_base_url"]),
        "gpu_memory_utilization": str(spec["gpu_memory_utilization"]),
        "enable_thinking": bool(spec.get("enable_thinking", False)),
        "hf_overrides_enabled": bool(dict(spec.get("hf_overrides") or {})),
        "rope_type": str(rope_parameters.get("rope_type", "")),
        "rope_factor": rope_parameters.get("factor"),
        "original_max_position_embeddings": rope_parameters.get("original_max_position_embeddings"),
        "system_prompt_chars": len(str(spec["system_prompt"])),
    }
    if bool(CB08_JSON_LOGS):
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
    else:
        print(payload, flush=True)


def print_runtime_memory_attachment_report(*, label: str, session: Any) -> dict[str, Any]:
    prompt = str(getattr(session, "system_prompt", "") or "")
    tokenizer = getattr(session, "tokenizer", None)
    chars_per_token = int(max(1, int(globals().get("CONTEXT_RUNTIME_BOOT_APPROX_CHARS_PER_TOKEN", 4) or 4)))

    def _estimate_tokens(text: str) -> int:
        cleaned = str(text or "")
        if not cleaned:
            return 0
        if tokenizer is not None:
            try:
                encoded = tokenizer(cleaned, add_special_tokens=False)
                if isinstance(encoded, dict):
                    return int(len(list(encoded.get("input_ids") or [])))
                input_ids = getattr(encoded, "input_ids", None)
                if input_ids is not None:
                    return int(len(list(input_ids or [])))
            except Exception:
                pass
        return int(max(1, (len(cleaned) + chars_per_token - 1) // chars_per_token))

    expected = [str(item) for item in list(dict(globals().get("CONTEXT_RUNTIME_BOOT_LINES") or {}).get(str(label)) or []) if str(item).strip()]
    expected_memory_block = "\n".join(f"- {line}" for line in expected)
    matched = sum(1 for line in expected if line in prompt)
    source_stats = dict(dict(globals().get("CONTEXT_RUNTIME_BOOT_SOURCE_STATS") or {}).get(str(label)) or {})
    injection_mode = str(
        dict(globals().get("CONTEXT_RUNTIME_BOOT_CONFIG") or {}).get(
            "injection_mode",
            globals().get("CONTEXT_RUNTIME_BOOT_INJECTION_MODE", "text_only"),
        )
    )
    report = {
        "event": "context_runtime_memory_attachment",
        "runtime_label": str(label),
        "boot_path": str(ROLE_BOOT_PATHS.get(str(label), "")),
        "boot_injection_mode": str(injection_mode),
        "boot_source_line_count": int(source_stats.get("raw_line_count", 0)),
        "boot_source_chars": int(source_stats.get("raw_chars", 0)),
        "line_count": int(len(expected)),
        "line_matches": int(matched),
        "selected_memory_chars": int(len(expected_memory_block)),
        "selected_memory_tokens_est": int(_estimate_tokens(expected_memory_block)),
        "system_prompt_chars": len(prompt),
        "system_prompt_tokens_est": int(_estimate_tokens(prompt)),
    }
    if bool(CB08_JSON_LOGS):
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")), flush=True)
    else:
        print(report, flush=True)
    return dict(report)


def validate_runtime_spec(label: str, spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    model_path = Path(str(spec.get("model_dir") or ""))
    if not model_path.exists():
        errors.append(f"{label}: model_dir does not exist: {model_path}")
    elif not (model_path / "config.json").exists():
        errors.append(f"{label}: missing config.json under {model_path}")
    if int(spec.get("context_limit", 0) or 0) <= 0:
        errors.append(f"{label}: context_limit must be > 0")
    if not str(spec.get("system_prompt") or "").strip():
        errors.append(f"{label}: system_prompt is empty")
    if int(spec.get("server_port", 0) or 0) <= 0:
        errors.append(f"{label}: server_port must be > 0")
    if not str(spec.get("device") or "").strip():
        errors.append(f"{label}: device is empty")
    return errors


def _runtime_at_boot_required_labels() -> list[str]:
    raw = globals().get("RUNTIME_AT_BOOT_REQUIRED_RUNTIME_LABELS")
    if raw is None:
        raw = ["clerk", "agent", "solver"]
    if isinstance(raw, str):
        labels = [str(raw).strip()] if str(raw).strip() else []
    else:
        labels = [str(item).strip() for item in list(raw or []) if str(item).strip()]
    return labels or ["clerk", "agent", "solver"]


def _build_runtime_boot_generation_profile(runtime_label: str) -> dict[str, Any]:
    _ = str(runtime_label).strip().lower()
    return {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 4,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
    }


def _write_runtime_boot_log_csv(*, run_id: str, boot_reports: dict[str, Any]) -> str:
    artifact_dir = Path(RUNTIME_BOOT_ARTIFACT_DIR)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifact_dir / "runtime_boot_log.csv"
    fieldnames = [
        "run_id",
        "role",
        "runtime_label",
        "line_no",
        "line_id",
        "probe_id",
        "probe_no",
        "probe_total",
        "probe_ordinal",
        "line_probe_count",
        "question",
        "expected_answer",
        "attempt_no",
        "provided_answer",
        "correct",
        "status",
        "elapsed_seconds",
    ]
    rows: list[dict[str, Any]] = []
    for runtime_label, report in dict(boot_reports or {}).items():
        for row in list(dict(report or {}).get("log_rows") or []):
            payload = dict(row)
            payload["run_id"] = str(run_id)
            payload["runtime_label"] = str(runtime_label)
            rows.append({name: payload.get(name, "") for name in fieldnames})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(csv_path.resolve())




def _emit_runtime_at_boot_certification(summary: dict[str, Any], runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    def _cert_int(value: Any) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    def _cert_float(value: Any) -> float:
        try:
            return round(float(value), 4)
        except Exception:
            return 0.0

    payload = dict(summary or {})
    roles = dict(payload.get("roles") or {})
    role_rows: list[dict[str, Any]] = []
    for fallback_label, raw_report in roles.items():
        report = dict(raw_report or {})
        role_rows.append(
            {
                "runtime_label": str(report.get("runtime_label") or fallback_label),
                "role_name": str(report.get("role_name") or fallback_label),
                "status": str(report.get("status", "")),
                "passed": bool(report.get("passed", False)),
                "line_count": _cert_int(report.get("line_count", 0)),
                "certified_count": _cert_int(report.get("certified_count", 0)),
                "probe_count": _cert_int(report.get("probe_count", 0)),
                "certified_probe_count": _cert_int(report.get("certified_probe_count", 0)),
                "memory_studied": bool(report.get("memory_studied", False)),
                "memory_line_count": _cert_int(report.get("memory_line_count", 0)),
                "memory_baseline_captured": bool(dict(report.get("memory_baseline") or {}).get("captured", False)),
                "blocked_reason": str(report.get("blocked_reason", "") or ""),
                "elapsed_seconds": _cert_float(report.get("elapsed_seconds", 0)),
            }
        )
    certificate = {
        "event": "runtime_at_boot_certification",
        "revision": str(payload.get("revision", CB07_5_RUNTIME_CONTEXT_REVISION)),
        "run_id": str(payload.get("run_id", "")),
        "passed": bool(payload.get("passed", False)),
        "status": str(payload.get("status", "")),
        "blocked_reason": str(payload.get("blocked_reason", "") or ""),
        "required_runtime_labels": list(payload.get("required_runtime_labels") or []),
        "roles": role_rows,
        "total_certified_count": sum(_cert_int(row.get("certified_count", 0)) for row in role_rows),
        "total_line_count": sum(_cert_int(row.get("line_count", 0)) for row in role_rows),
        "total_certified_probe_count": sum(_cert_int(row.get("certified_probe_count", 0)) for row in role_rows),
        "total_probe_count": sum(_cert_int(row.get("probe_count", 0)) for row in role_rows),
        "total_memory_line_count": sum(_cert_int(row.get("memory_line_count", 0)) for row in role_rows),
        "boot_log_csv_path": str(payload.get("boot_log_csv_path", "") or ""),
        "elapsed_seconds": _cert_float(payload.get("elapsed_seconds", 0)),
    }
    if isinstance(runtime, dict):
        runtime["runtime_at_boot_certification"] = dict(certificate)
    globals()["RUNTIME_AT_BOOT_CERTIFICATION"] = dict(certificate)
    print(json.dumps(certificate, ensure_ascii=False, separators=(",", ":")), flush=True)
    return certificate

def run_runtime_at_boot_gate(runtime: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(runtime, dict):
        raise TypeError("runtime must be a dictionary")
    required_labels = _runtime_at_boot_required_labels()
    started = time.perf_counter()
    run_id = time.strftime("rab-%Y%m%d-%H%M%S")
    role_reports: dict[str, dict[str, Any]] = {}
    passed = True
    for runtime_label in required_labels:
        report = dict(
            run_boot_certification_gate(
                runtime,
                runtime_label=str(runtime_label),
                generation_profile=_build_runtime_boot_generation_profile(str(runtime_label)),
                reset_session_after_gate=False,
            )
            or {}
        )
        role_reports[str(runtime_label)] = dict(report)
        if not bool(report.get("passed", False)):
            passed = False
            break
    csv_path = _write_runtime_boot_log_csv(run_id=str(run_id), boot_reports=role_reports)
    blocked_reason = ""
    if not passed:
        for report in role_reports.values():
            blocked_reason = str(dict(report or {}).get("blocked_reason", "") or "").strip()
            if blocked_reason:
                break
    summary = {
        "event": "runtime_at_boot_summary",
        "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
        "run_id": str(run_id),
        "required_runtime_labels": list(required_labels),
        "passed": bool(passed),
        "status": "passed" if passed else "failed",
        "blocked_reason": str(blocked_reason),
        "roles": dict(role_reports),
        "boot_log_csv_path": str(csv_path),
        "elapsed_seconds": round(float(time.perf_counter() - started), 4),
    }
    runtime["runtime_at_boot_run_id"] = str(run_id)
    runtime["runtime_at_boot_required_labels"] = list(required_labels)
    runtime["runtime_at_boot_reports"] = dict(role_reports)
    runtime["runtime_at_boot_passed"] = bool(passed)
    runtime["runtime_at_boot_status"] = str(summary["status"])
    runtime["runtime_at_boot_log_csv_path"] = str(csv_path)
    runtime["runtime_at_boot_summary"] = dict(summary)
    runtime["runtime_at_boot_log"] = [
        dict(row)
        for report in role_reports.values()
        for row in list(dict(report or {}).get("log_rows") or [])
    ]
    globals()["RUNTIME_AT_BOOT_SUMMARY"] = dict(summary)
    globals()["RUNTIME_AT_BOOT_REPORTS"] = dict(role_reports)
    _emit_runtime_at_boot_certification(summary, runtime)
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return summary


def _finalize_runtime_at_boot_summary(
    runtime: dict[str, Any],
    *,
    role_reports: dict[str, Any],
    required_labels: list[str],
    run_id: str | None = None,
    started_at: float | None = None,
) -> dict[str, Any]:
    started = float(started_at if started_at is not None else time.perf_counter())
    resolved_run_id = str(run_id or time.strftime("rab-%Y%m%d-%H%M%S"))
    csv_path = _write_runtime_boot_log_csv(run_id=str(resolved_run_id), boot_reports=dict(role_reports or {}))
    passed = bool(role_reports) and all(bool(dict(report or {}).get("passed", False)) for report in role_reports.values())
    blocked_reason = ""
    if not passed:
        for report in role_reports.values():
            blocked_reason = str(dict(report or {}).get("blocked_reason", "") or "").strip()
            if blocked_reason:
                break
    summary = {
        "event": "runtime_at_boot_summary",
        "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
        "run_id": str(resolved_run_id),
        "required_runtime_labels": list(required_labels),
        "passed": bool(passed),
        "status": "passed" if passed else "failed",
        "blocked_reason": str(blocked_reason),
        "roles": dict(role_reports),
        "boot_log_csv_path": str(csv_path),
        "elapsed_seconds": round(float(time.perf_counter() - started), 4),
    }
    runtime["runtime_at_boot_run_id"] = str(resolved_run_id)
    runtime["runtime_at_boot_required_labels"] = list(required_labels)
    runtime["runtime_at_boot_reports"] = dict(role_reports)
    runtime["runtime_at_boot_passed"] = bool(passed)
    runtime["runtime_at_boot_status"] = str(summary["status"])
    runtime["runtime_at_boot_log_csv_path"] = str(csv_path)
    runtime["runtime_at_boot_summary"] = dict(summary)
    runtime["runtime_at_boot_log"] = [
        dict(row)
        for report in role_reports.values()
        for row in list(dict(report or {}).get("log_rows") or [])
    ]
    globals()["RUNTIME_AT_BOOT_SUMMARY"] = dict(summary)
    globals()["RUNTIME_AT_BOOT_REPORTS"] = dict(role_reports)
    _emit_runtime_at_boot_certification(summary, runtime)
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return dict(summary)


def _raise_if_runtime_at_boot_failed(runtime: dict[str, Any]) -> None:
    summary = dict(runtime.get("runtime_at_boot_summary") or {})
    if bool(summary.get("passed", False)):
        return
    blocked_reason = str(summary.get("blocked_reason", "") or "").strip()
    status = str(summary.get("status", "failed") or "failed").strip() or "failed"
    detail = f"Runtime-at-boot failed in CB8 (status={status})."
    if blocked_reason:
        detail = f"{detail} blocked_reason={blocked_reason}"
    raise RuntimeError(
        detail
        + " Resolve the failing boot/runtime certification issue before running benchmark cells."
    )


def start_aen_runtime(
    *,
    preload_solver: bool | None = None,
    preload_clerk: bool | None = None,
    preload_agent: bool | None = None,
) -> dict[str, Any]:
    global RUNTIME
    try:
        require_cb08_dependencies()
        cleanup_runtime = _require_notebook_callable("cleanup_runtime")
        preload_model_weights = _require_notebook_callable("preload_model_weights")
        load_vllm_openai_session = _require_notebook_callable("load_vllm_openai_session")

        if bool(globals().get("CLERK_ALIAS_SOLVER", False)):
            raise RuntimeError("CB8 does not support clerk alias mode. Set CLERK_ALIAS_SOLVER=False in CB4.")
        if not bool(globals().get("CLERK_ENABLED", False)) or not bool(globals().get("AGENT_ENABLED", False)):
            raise RuntimeError("CB8 requires CLERK_ENABLED=True and AGENT_ENABLED=True in CB4.")

        role_identity_prompts = dict(initialize_cb08_role_prompts())
        context_runtime_apply_report = dict(apply_context_runtime_boot_overrides(globals()) or {})

        preload_solver = bool(PRELOAD_MODEL_WEIGHTS) if preload_solver is None else bool(preload_solver)
        preload_clerk = bool(PRELOAD_MODEL_WEIGHTS) if preload_clerk is None else bool(preload_clerk)
        preload_agent = bool(PRELOAD_MODEL_WEIGHTS) if preload_agent is None else bool(preload_agent)

        cleanup_runtime()
        solver_spec = build_session_spec(
            runtime_label=str(SOLVER_RUNTIME_LABEL),
            model_dir=str(SOLVER_MODEL_DIR),
            served_model_name=str(SOLVER_MODEL_NAME),
            context_limit=int(SOLVER_RUNTIME_CONTEXT_WINDOW_TOKENS),
            system_prompt=str(globals().get("SOLVER_CONVERSATION_SYSTEM_PROMPT", "")),
            server_port=int(SOLVER_SERVER_PORT),
            gpu_memory_utilization=str(SOLVER_GPU_MEMORY_UTILIZATION),
            kv_cache_dtype=SOLVER_KV_CACHE_DTYPE,
            reasoning_parser=SOLVER_REASONING_PARSER,
            attention_backend=SOLVER_ATTENTION_BACKEND,
            language_model_only=bool(SOLVER_LANGUAGE_MODEL_ONLY),
            cpu_offload_gb=SOLVER_CPU_OFFLOAD_GB,
            enforce_eager=bool(SOLVER_ENFORCE_EAGER),
            compilation_mode=SOLVER_COMPILATION_MODE,
            cudagraph_mode=SOLVER_CUDAGRAPH_MODE,
            disable_compile_cache=bool(SOLVER_DISABLE_COMPILE_CACHE),
            disable_hybrid_kv_cache_manager=bool(SOLVER_DISABLE_HYBRID_KV_CACHE_MANAGER),
            enable_thinking=bool(SOLVER_ENABLE_THINKING),
            allow_attach_model_mismatch=bool(SOLVER_ALLOW_ATTACH_MODEL_MISMATCH),
            hf_overrides=dict(SOLVER_HF_OVERRIDES),
            env_overrides=dict(SOLVER_ENV_OVERRIDES),
        )
        clerk_spec = build_session_spec(
            runtime_label=str(CLERK_RUNTIME_LABEL),
            model_dir=str(CLERK_MODEL_DIR),
            served_model_name=str(CLERK_MODEL_NAME),
            context_limit=int(CLERK_RUNTIME_CONTEXT_WINDOW_TOKENS),
            system_prompt=str(globals().get("CLERK_CONVERSATION_SYSTEM_PROMPT", "")),
            server_port=int(CLERK_SERVER_PORT),
            gpu_memory_utilization=str(CLERK_GPU_MEMORY_UTILIZATION),
            kv_cache_dtype=CLERK_KV_CACHE_DTYPE,
            reasoning_parser=CLERK_REASONING_PARSER,
            attention_backend=CLERK_ATTENTION_BACKEND,
            language_model_only=bool(CLERK_LANGUAGE_MODEL_ONLY),
            cpu_offload_gb=CLERK_CPU_OFFLOAD_GB,
            enforce_eager=bool(CLERK_ENFORCE_EAGER),
            compilation_mode=CLERK_COMPILATION_MODE,
            cudagraph_mode=CLERK_CUDAGRAPH_MODE,
            disable_compile_cache=bool(CLERK_DISABLE_COMPILE_CACHE),
            disable_hybrid_kv_cache_manager=bool(CLERK_DISABLE_HYBRID_KV_CACHE_MANAGER),
            enable_thinking=bool(CLERK_ENABLE_THINKING),
            allow_attach_model_mismatch=bool(CLERK_ALLOW_ATTACH_MODEL_MISMATCH),
            hf_overrides=dict(CLERK_HF_OVERRIDES),
            env_overrides=dict(CLERK_ENV_OVERRIDES),
        )
        agent_spec = build_session_spec(
            runtime_label=str(AGENT_RUNTIME_LABEL),
            model_dir=str(AGENT_MODEL_DIR),
            served_model_name=str(AGENT_MODEL_NAME),
            context_limit=int(AGENT_RUNTIME_CONTEXT_WINDOW_TOKENS),
            system_prompt=str(globals().get("AGENT_CONVERSATION_SYSTEM_PROMPT", "")),
            server_port=int(AGENT_SERVER_PORT),
            gpu_memory_utilization=str(AGENT_GPU_MEMORY_UTILIZATION),
            kv_cache_dtype=AGENT_KV_CACHE_DTYPE,
            reasoning_parser=AGENT_REASONING_PARSER,
            attention_backend=AGENT_ATTENTION_BACKEND,
            language_model_only=bool(AGENT_LANGUAGE_MODEL_ONLY),
            cpu_offload_gb=AGENT_CPU_OFFLOAD_GB,
            enforce_eager=bool(AGENT_ENFORCE_EAGER),
            compilation_mode=AGENT_COMPILATION_MODE,
            cudagraph_mode=AGENT_CUDAGRAPH_MODE,
            disable_compile_cache=bool(AGENT_DISABLE_COMPILE_CACHE),
            disable_hybrid_kv_cache_manager=bool(AGENT_DISABLE_HYBRID_KV_CACHE_MANAGER),
            enable_thinking=bool(AGENT_ENABLE_THINKING),
            allow_attach_model_mismatch=bool(AGENT_ALLOW_ATTACH_MODEL_MISMATCH),
            hf_overrides=dict(AGENT_HF_OVERRIDES),
            env_overrides=dict(AGENT_ENV_OVERRIDES),
        )

        for label, spec in [
            (str(SOLVER_RUNTIME_LABEL), solver_spec),
            (str(CLERK_RUNTIME_LABEL), clerk_spec),
            (str(AGENT_RUNTIME_LABEL), agent_spec),
        ]:
            errors = validate_runtime_spec(str(label), dict(spec))
            print_runtime_spec("runtime_load_spec", str(label), dict(spec))
            if errors:
                raise RuntimeError("; ".join(errors))

        RUNTIME = {
            "runtime_sessions": {},
            "solver_effective_spec": dict(solver_spec),
            "clerk_effective_spec": dict(clerk_spec),
            "agent_effective_spec": dict(agent_spec),
            "runtime_profile": ACTIVE_RUNTIME_PROFILE,
            "solver_enabled": True,
            "clerk_enabled": True,
            "agent_enabled": True,
            "solver_context_limit": int(solver_spec["context_limit"]),
            "clerk_context_limit": int(clerk_spec["context_limit"]),
            "agent_context_limit": int(agent_spec["context_limit"]),
            "role_identity_prompts": dict(role_identity_prompts),
            "boot_paths": {key: str(path) for key, path in ROLE_BOOT_PATHS.items()},
            "runtime_boot_execution_order": ["clerk", "agent", "solver"],
            "context_runtime_boot_context_injection": dict(context_runtime_apply_report),
            "context_runtime_memory_attachment": {},
        }
        required_labels = [str(label) for label in _runtime_at_boot_required_labels()]
        boot_started = time.perf_counter()
        boot_run_id = time.strftime("rab-%Y%m%d-%H%M%S")
        boot_role_reports: dict[str, dict[str, Any]] = {}

        def _load_and_certify_role(
            *,
            runtime_label: str,
            spec: dict[str, Any],
            preload_enabled: bool,
            session_key: str,
            context_limit_key: str,
        ) -> bool:
            if bool(preload_enabled):
                preload_model_weights(str(spec["model_dir"]))
            session = load_vllm_openai_session(spec)
            RUNTIME[session_key] = session
            RUNTIME["runtime_sessions"][str(runtime_label)] = session
            RUNTIME[context_limit_key] = int(spec["context_limit"])
            attachment_report = print_runtime_memory_attachment_report(label=str(runtime_label), session=session)
            RUNTIME["context_runtime_memory_attachment"][str(runtime_label)] = dict(attachment_report)
            if str(runtime_label) not in required_labels:
                return True
            report = dict(
                run_boot_certification_gate(
                    RUNTIME,
                    runtime_label=str(runtime_label),
                    generation_profile=_build_runtime_boot_generation_profile(str(runtime_label)),
                    reset_session_after_gate=False,
                )
                or {}
            )
            boot_role_reports[str(runtime_label)] = dict(report)
            append_boot_certified_memory_to_session(session, report)
            return bool(report.get("passed", False))

        boot_plan = [
            {
                "status_key": "clerk",
                "runtime_label": str(CLERK_RUNTIME_LABEL),
                "spec": dict(clerk_spec),
                "preload_enabled": bool(preload_clerk),
                "session_key": "clerk_session",
                "context_limit_key": "clerk_context_limit",
            },
            {
                "status_key": "agent",
                "runtime_label": str(AGENT_RUNTIME_LABEL),
                "spec": dict(agent_spec),
                "preload_enabled": bool(preload_agent),
                "session_key": "agent_session",
                "context_limit_key": "agent_context_limit",
            },
            {
                "status_key": "solver",
                "runtime_label": str(SOLVER_RUNTIME_LABEL),
                "spec": dict(solver_spec),
                "preload_enabled": bool(preload_solver),
                "session_key": "solver_session",
                "context_limit_key": "solver_context_limit",
            },
        ]
        boot_statuses = {"solver": False, "clerk": False, "agent": False}
        boot_chain_ok = True
        for boot_step in boot_plan:
            if not boot_chain_ok:
                break
            boot_ok = _load_and_certify_role(
                runtime_label=str(boot_step["runtime_label"]),
                spec=dict(boot_step["spec"]),
                preload_enabled=bool(boot_step["preload_enabled"]),
                session_key=str(boot_step["session_key"]),
                context_limit_key=str(boot_step["context_limit_key"]),
            )
            boot_statuses[str(boot_step["status_key"])] = bool(boot_ok)
            boot_chain_ok = bool(boot_ok)

        solver_ok = bool(boot_statuses["solver"])
        clerk_ok = bool(boot_statuses["clerk"])
        agent_ok = bool(boot_statuses["agent"])

        if solver_ok and clerk_ok and agent_ok:
            RUNTIME["context_runtime_boot_validation"] = dict(run_context_runtime_boot_validation(globals(), runtime=RUNTIME) or {})
        else:
            RUNTIME["context_runtime_boot_validation"] = {
                "event": "context_runtime_boot_validation",
                "revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
                "enabled": False,
                "status": "skipped_after_boot_failure",
            }
        RUNTIME["runtime_at_boot_summary"] = dict(
            _finalize_runtime_at_boot_summary(
                RUNTIME,
                role_reports=dict(boot_role_reports),
                required_labels=list(required_labels),
                run_id=str(boot_run_id),
                started_at=float(boot_started),
            )
            or {}
        )
        _raise_if_runtime_at_boot_failed(RUNTIME)
        return RUNTIME
    except NameError as exc:
        missing_name = _extract_missing_name(exc)
        raise RuntimeError(_cb8_missing_state_message(f"CB8 is missing notebook state for {missing_name!r}.")) from exc


if os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
    runtime = dict(globals().get("RUNTIME") or {})
    _cb8_runtime_summary = {
        "cb8_revision": str(CB08_RUNTIME_REVISION),
        "runtime_profile": ACTIVE_RUNTIME_PROFILE,
        "deprecated_blocks_required": False,
        "competition_rerun": True,
        "runtime_start_mode": "deferred_to_predict",
        "runtime_at_boot_status": str(runtime.get("runtime_at_boot_status", "deferred")),
        "runtime_at_boot_passed": bool(runtime.get("runtime_at_boot_passed", False)),
    }
else:
    runtime = start_aen_runtime()
    _cb8_runtime_summary = {
        "cb8_revision": str(CB08_RUNTIME_REVISION),
        "runtime_profile": ACTIVE_RUNTIME_PROFILE,
        "deprecated_blocks_required": False,
        "runtime_labels": {
            "solver": str(SOLVER_RUNTIME_LABEL),
            "clerk": str(CLERK_RUNTIME_LABEL),
            "agent": str(AGENT_RUNTIME_LABEL),
        },
        "role_identity_prompts": dict(RUNTIME.get("role_identity_prompts") or {}),
        "solver_context_limit": int(RUNTIME["solver_context_limit"]),
        "clerk_context_limit": int(RUNTIME["clerk_context_limit"]),
        "agent_context_limit": int(RUNTIME["agent_context_limit"]),
        "context_runtime_revision": str(CB07_5_RUNTIME_CONTEXT_REVISION),
        "context_runtime_injection_status": str(dict(RUNTIME.get("context_runtime_boot_context_injection") or {}).get("status", "none")),
        "context_runtime_validation_status": str(dict(RUNTIME.get("context_runtime_boot_validation") or {}).get("status", "none")),
        "context_runtime_validation_pass_rate": float(dict(RUNTIME.get("context_runtime_boot_validation") or {}).get("pass_rate", 0.0) or 0.0),
        "runtime_at_boot_status": str(RUNTIME.get("runtime_at_boot_status", "not_started")),
        "runtime_at_boot_passed": bool(RUNTIME.get("runtime_at_boot_passed", False)),
        "runtime_at_boot_log_csv_path": str(RUNTIME.get("runtime_at_boot_log_csv_path", "")),
        "runtime_at_boot_dataset_root": str(RUNTIME_AT_BOOT_DATASET_ROOT),
        "boot_paths": {key: str(path) for key, path in ROLE_BOOT_PATHS.items()},
        "boot_revision": str(CB07_5_MEMORY_RUNTIME_REVISION),
    }
if bool(CB08_JSON_LOGS):
    print(json.dumps(_cb8_runtime_summary, ensure_ascii=False, separators=(",", ":")))
else:
    print(_cb8_runtime_summary)
