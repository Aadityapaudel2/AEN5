#!/usr/bin/env python3
"""Build a four-run AIME report from the official Apr28 run artifact."""

from __future__ import annotations

import csv
import html
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


OLD_REPORT = Path(r"N:\Research\Updates_to_AEN\AIME_20260427_q1_q30_espn_report")
OFFICIAL = Path(r"N:\Research\colab_outputs\AIME-2026_export_full_dataset_30q_20260428-022518")
OUT = Path(r"N:\Research\Updates_to_AEN\AIME_20260428_official_four_run_report")
TABLES = OUT / "data_analysis" / "tables"
VIZ = OUT / "data_visualizations"
SCRIPTS = OUT / "scripts"

RUN_ORDER = ["frozen", "unrestricted", "current", "official"]
RUN_LABELS = {
    "frozen": "Frozen pruned",
    "unrestricted": "Unrestricted",
    "current": "Apr27 current 0.2.3",
    "official": "Apr28 official boot run",
}
RUN_SHORT = {
    "frozen": "Frozen",
    "unrestricted": "Unrestricted",
    "current": "Current",
    "official": "Official",
}
COLORS = {
    "frozen": "#6b7280",
    "unrestricted": "#1565c0",
    "current": "#6a1b9a",
    "official": "#e65100",
    "green": "#2e7d32",
    "red": "#c62828",
    "amber": "#f9a825",
    "ink": "#1f2933",
    "muted": "#667085",
    "grid": "#d0d5dd",
    "bg": "#fbfaf7",
}
SLICES = [
    ("Q1-Q5", 1, 5),
    ("Q6-Q10", 6, 10),
    ("Q11-Q15", 11, 15),
    ("Q16-Q20", 16, 20),
    ("Q21-Q25", 21, 25),
    ("Q26-Q30", 26, 30),
    ("Q1-Q30", 1, 30),
]
CLASS_MAP = {
    4: ("C1", "object/model setup"),
    7: ("C3", "sequence/recurrence"),
    9: ("C2", "conditional ledger / enumeration"),
    10: ("C4", "geometry closure"),
    11: ("C5", "global count / constructive closure"),
    15: ("C5", "exact-cover completeness"),
    17: ("C3", "endpoint recurrence"),
    18: ("C5", "branch/existence closure"),
    21: ("C4", "answer contract / object"),
    23: ("C4", "geometry/integer constraint"),
    24: ("C5", "count/invariant closure"),
    27: ("C4", "geometry center-distance closure"),
    28: ("C2", "conditional/object ledger"),
    29: ("C3", "state recurrence with recovery"),
    30: ("C5", "modular enumeration completeness"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def as_int(value: Any, default: int = 0) -> int:
    if value in ("", None):
        return default
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return default


def boolish(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def svg_doc(width: int, height: int, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  text {{ font-family: Arial, Helvetica, sans-serif; fill: {COLORS["ink"]}; }}
  .title {{ font-size: 24px; font-weight: 700; }}
  .subtitle {{ font-size: 13px; fill: {COLORS["muted"]}; }}
  .label {{ font-size: 12px; }}
  .small {{ font-size: 10px; fill: {COLORS["muted"]}; }}
  .num {{ font-size: 18px; font-weight: 700; }}
</style>
<rect width="100%" height="100%" fill="{COLORS["bg"]}"/>
{body}
</svg>"""


def t(
    x: float,
    y: float,
    text: Any,
    cls: str = "label",
    anchor: str = "start",
    color: str | None = None,
    weight: str | None = None,
) -> str:
    style = ""
    if color:
        style += f"fill:{color};"
    if weight:
        style += f"font-weight:{weight};"
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}" style="{style}">{esc(text)}</text>'


def rect(
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str,
    stroke: str = "none",
    rx: int = 3,
    opacity: float = 1,
) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" opacity="{opacity}"/>'
    )


def line(x1: float, y1: float, x2: float, y2: float, stroke: str | None = None, sw: int = 1) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke or COLORS["grid"]}" stroke-width="{sw}"/>'
    )


def extract_peer_meta(payload_path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "peer_validation_ready": "",
        "peer_candidates": "",
        "peer_candidate_set": set(),
        "athena_confidence_pct": "",
        "submission_mode": "",
        "max_big_loops": "",
        "reset_session_each_turn": "",
        "peer_statuses": "",
        "peer_none_count": 0,
    }
    if not payload_path.exists():
        return meta
    obj = json.loads(payload_path.read_text(encoding="utf-8"))
    meta["peer_validation_ready"] = obj.get("peer_validation_ready", "")
    meta["athena_confidence_pct"] = obj.get("athena_confidence_pct", "")
    meta["submission_mode"] = obj.get("submission_mode", "")
    config = obj.get("controller_state", {}).get("config", {})
    meta["max_big_loops"] = config.get("max_big_loops", "")
    meta["reset_session_each_turn"] = config.get("reset_session_each_turn", "")

    peer_meta = obj.get("peer_report_meta", {}) or {}
    candidates: list[str] = []
    statuses: list[str] = []
    none_count = 0
    for role in ("Aria", "Artemis"):
        role_meta = peer_meta.get(role, {}) or {}
        candidate = (
            role_meta.get("answer_signal_integer")
            or role_meta.get("candidate_exact_integer")
            or role_meta.get("candidate")
            or ""
        )
        confidence = role_meta.get("answer_signal_confidence_pct") or role_meta.get("confidence_pct") or ""
        slots = (role_meta.get("extracted_fields", {}) or {}).get("report_slots", "")
        status_match = re.search(r"^status:\s*([^\n]+)", slots, flags=re.M)
        status = status_match.group(1).strip() if status_match else ""
        if str(candidate).strip().lower() in ("", "none"):
            none_count += 1
        else:
            meta["peer_candidate_set"].add(str(candidate))
        candidates.append(f"{role}:{candidate}/{confidence}")
        statuses.append(f"{role}:{status}")
    meta["peer_candidates"] = "; ".join(candidates)
    meta["peer_statuses"] = "; ".join(statuses)
    meta["peer_none_count"] = none_count
    return meta


def load_rows() -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prior_rows = read_csv(OLD_REPORT / "data_analysis" / "tables" / "all_runs_q1_q30_long.csv")
    for row in prior_rows:
        run_key = row["run_key"]
        if run_key not in ("frozen", "unrestricted", "current"):
            continue
        rows.append(
            {
                "run_key": run_key,
                "run_label": RUN_LABELS[run_key],
                "idx": as_int(row["idx"]),
                "id": row.get("id", ""),
                "answer": row.get("answer", ""),
                "expected_answer": row.get("expected_answer", ""),
                "correct": boolish(row.get("correct")),
                "valid_answer": True,
                "status": row.get("status", ""),
                "closeout_mode": row.get("closeout_mode", ""),
                "total_tokens": as_int(row.get("total_tokens")),
                "time_taken_seconds": as_float(row.get("time_taken_seconds")),
                "turns": as_int(row.get("turns")),
                "loops": as_int(row.get("loops")),
                "total_prompt_tokens": as_int(row.get("total_prompt_tokens")),
                "total_completion_tokens": as_int(row.get("total_completion_tokens")),
                "peer_validation_ready": "",
                "peer_candidates": "",
                "athena_confidence_pct": "",
            }
        )

    payload_meta: dict[int, dict[str, Any]] = {}
    official_rows = read_csv(OFFICIAL / "AIME-2026_PRIVATE_FULL.csv")
    for row in official_rows:
        idx = as_int(row.get("problem_idx"))
        row_id = row.get("id") or row.get("question_id") or f"aime2025_{idx:02d}"
        meta = extract_peer_meta(OFFICIAL / "result_payloads" / f"{row_id}.json")
        payload_meta[idx] = meta
        rows.append(
            {
                "run_key": "official",
                "run_label": RUN_LABELS["official"],
                "idx": idx,
                "id": row_id,
                "answer": row.get("model_answer_normalized")
                or row.get("model_submitted_answer")
                or row.get("answer", ""),
                "expected_answer": row.get("expected_answer_normalized") or row.get("expected_answer", ""),
                "correct": boolish(row.get("correct")),
                "valid_answer": boolish(row.get("valid_answer")),
                "status": row.get("status", ""),
                "closeout_mode": meta.get("submission_mode") or row.get("status", ""),
                "total_tokens": as_int(row.get("total_tokens")),
                "time_taken_seconds": as_float(row.get("time_taken_seconds")),
                "turns": as_int(row.get("turns")),
                "loops": as_int(row.get("loops")),
                "total_prompt_tokens": as_int(row.get("total_prompt_tokens")),
                "total_completion_tokens": as_int(row.get("total_completion_tokens")),
                "peer_validation_ready": meta.get("peer_validation_ready", ""),
                "peer_candidates": meta.get("peer_candidates", ""),
                "athena_confidence_pct": meta.get("athena_confidence_pct", ""),
            }
        )

    boot = json.loads((OFFICIAL / "runtime_at_boot_summary.json").read_text(encoding="utf-8"))
    return sorted(rows, key=lambda r: (RUN_ORDER.index(r["run_key"]), r["idx"])), payload_meta, boot


def build_comparison(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {(row["idx"], row["run_key"]): row for row in rows}
    comparison: list[dict[str, Any]] = []
    for idx in range(1, 31):
        expected = next(
            (by[(idx, run)]["expected_answer"] for run in RUN_ORDER if by[(idx, run)]["expected_answer"]),
            "",
        )
        out: dict[str, Any] = {"idx": idx, "expected_answer": expected}
        bits: dict[str, bool] = {}
        for run in RUN_ORDER:
            row = by[(idx, run)]
            bits[run] = bool(row["correct"])
            out[f"{run}_answer"] = row["answer"]
            out[f"{run}_correct"] = row["correct"]
            out[f"{run}_valid"] = row.get("valid_answer", True)
            out[f"{run}_tokens"] = row["total_tokens"]
            out[f"{run}_seconds"] = round(row["time_taken_seconds"], 3)

        if bits["official"] and bits["current"]:
            official_vs_current = "same_correct"
        elif not bits["official"] and not bits["current"]:
            official_vs_current = "same_wrong"
        elif bits["official"] and not bits["current"]:
            official_vs_current = "official_fix_vs_current"
        else:
            official_vs_current = "official_regression_vs_current"

        if all(bits.values()):
            four = "all_four_correct"
        elif not any(bits.values()):
            four = "all_four_missed"
        elif official_vs_current in ("official_fix_vs_current", "official_regression_vs_current"):
            four = official_vs_current
        elif bits["official"] and not bits["unrestricted"]:
            four = "official_beats_unrestricted_on_this_problem"
        elif not bits["official"] and bits["unrestricted"]:
            four = "official_regression_vs_unrestricted"
        else:
            four = "mixed_same_outcome"

        out["official_vs_current"] = official_vs_current
        out["four_run_outcome"] = four
        out["class_code"] = CLASS_MAP.get(idx, ("", ""))[0]
        out["class_note"] = CLASS_MAP.get(idx, ("", ""))[1]
        comparison.append(out)
    return comparison


def build_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for run in RUN_ORDER:
        run_rows = [row for row in rows if row["run_key"] == run]
        for label, low, high in SLICES:
            chunk = [row for row in run_rows if low <= row["idx"] <= high]
            correct = sum(1 for row in chunk if row["correct"])
            cases = len(chunk)
            summary.append(
                {
                    "run_key": run,
                    "run_label": RUN_LABELS[run],
                    "slice": label,
                    "cases": cases,
                    "correct": correct,
                    "losses": cases - correct,
                    "accuracy": round(correct / cases, 4) if cases else "",
                    "mean_total_tokens": round(statistics.mean([r["total_tokens"] for r in chunk]), 1)
                    if chunk
                    else "",
                    "mean_seconds": round(statistics.mean([r["time_taken_seconds"] for r in chunk]), 3)
                    if chunk
                    else "",
                    "tokens_per_correct": round(sum(r["total_tokens"] for r in chunk) / correct, 1)
                    if correct
                    else "",
                }
            )
    return summary


def miss_mechanism(idx: int, comparison_row: dict[str, Any], by: dict[tuple[int, str], dict[str, Any]], payload_meta: dict[int, dict[str, Any]]) -> tuple[str, str]:
    official = by[(idx, "official")]
    meta = payload_meta.get(idx, {})
    peer_set = meta.get("peer_candidate_set", set())
    answer = str(official["answer"])
    if not official.get("valid_answer", True):
        mechanism = "invalid_answer_not_blocked"
    elif meta.get("peer_none_count", 0) >= 1:
        mechanism = "mandatory_final_over_peer_blocker"
    elif len(peer_set) > 1:
        mechanism = "wrong_arbitration_under_peer_disagreement"
    elif len(peer_set) == 1 and answer in peer_set:
        mechanism = "wrong_peer_consensus_or_shared_count"
    else:
        mechanism = "wrong_athena_final_selection"

    if comparison_row["official_vs_current"] == "official_regression_vs_current":
        delta = "lost_prior_current_win"
    elif comparison_row["official_vs_current"] == "same_wrong":
        delta = "shared_current_miss"
    else:
        delta = "other"
    return mechanism, delta


def write_tables(
    rows: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    payload_meta: dict[int, dict[str, Any]],
    boot: dict[str, Any],
) -> list[dict[str, Any]]:
    long_fields = [
        "run_key",
        "run_label",
        "idx",
        "id",
        "answer",
        "expected_answer",
        "correct",
        "valid_answer",
        "status",
        "closeout_mode",
        "total_tokens",
        "time_taken_seconds",
        "turns",
        "loops",
        "total_prompt_tokens",
        "total_completion_tokens",
        "peer_validation_ready",
        "peer_candidates",
        "athena_confidence_pct",
    ]
    write_csv(TABLES / "all_four_runs_q1_q30_long.csv", rows, long_fields)

    comp_fields = ["idx", "expected_answer"]
    for run in RUN_ORDER:
        comp_fields += [
            f"{run}_answer",
            f"{run}_correct",
            f"{run}_valid",
            f"{run}_tokens",
            f"{run}_seconds",
        ]
    comp_fields += ["official_vs_current", "four_run_outcome", "class_code", "class_note"]
    write_csv(TABLES / "four_run_q1_q30_comparison.csv", comparison, comp_fields)
    write_csv(
        TABLES / "run_summary_q1_q30_and_slices.csv",
        summary,
        [
            "run_key",
            "run_label",
            "slice",
            "cases",
            "correct",
            "losses",
            "accuracy",
            "mean_total_tokens",
            "mean_seconds",
            "tokens_per_correct",
        ],
    )

    by = {(row["idx"], row["run_key"]): row for row in rows}
    misses: list[dict[str, Any]] = []
    for comp in comparison:
        idx = comp["idx"]
        official = by[(idx, "official")]
        if official["correct"]:
            continue
        mechanism, delta = miss_mechanism(idx, comp, by, payload_meta)
        meta = payload_meta.get(idx, {})
        misses.append(
            {
                "idx": idx,
                "expected_answer": comp["expected_answer"],
                "official_answer": official["answer"],
                "valid_answer": official.get("valid_answer", True),
                "current_answer": comp["current_answer"],
                "current_correct": comp["current_correct"],
                "unrestricted_correct": comp["unrestricted_correct"],
                "frozen_correct": comp["frozen_correct"],
                "delta_bucket": delta,
                "mechanism_bucket": mechanism,
                "class_code": comp.get("class_code", ""),
                "class_note": comp.get("class_note", ""),
                "athena_confidence_pct": official.get("athena_confidence_pct", ""),
                "peer_validation_ready": official.get("peer_validation_ready", ""),
                "peer_candidates": official.get("peer_candidates", ""),
                "peer_statuses": meta.get("peer_statuses", ""),
                "total_tokens": official.get("total_tokens", ""),
                "seconds": round(official.get("time_taken_seconds", 0), 3),
            }
        )
    write_csv(
        TABLES / "official_failure_warning_taxonomy_q1_q30.csv",
        misses,
        [
            "idx",
            "expected_answer",
            "official_answer",
            "valid_answer",
            "current_answer",
            "current_correct",
            "unrestricted_correct",
            "frozen_correct",
            "delta_bucket",
            "mechanism_bucket",
            "class_code",
            "class_note",
            "athena_confidence_pct",
            "peer_validation_ready",
            "peer_candidates",
            "peer_statuses",
            "total_tokens",
            "seconds",
        ],
    )

    official_detail: list[dict[str, Any]] = []
    for idx in range(1, 31):
        row = by[(idx, "official")]
        meta = payload_meta.get(idx, {})
        official_detail.append(
            {
                "idx": idx,
                "id": row["id"],
                "expected_answer": row["expected_answer"],
                "official_answer": row["answer"],
                "correct": row["correct"],
                "valid_answer": row.get("valid_answer", True),
                "status": row["status"],
                "closeout_mode": row["closeout_mode"],
                "athena_confidence_pct": row.get("athena_confidence_pct", ""),
                "peer_validation_ready": row.get("peer_validation_ready", ""),
                "peer_candidates": row.get("peer_candidates", ""),
                "peer_statuses": meta.get("peer_statuses", ""),
                "total_tokens": row["total_tokens"],
                "total_prompt_tokens": row["total_prompt_tokens"],
                "total_completion_tokens": row["total_completion_tokens"],
                "seconds": round(row["time_taken_seconds"], 3),
                "turns": row["turns"],
                "loops": row["loops"],
            }
        )
    write_csv(
        TABLES / "official_q1_q30_detail.csv",
        official_detail,
        [
            "idx",
            "id",
            "expected_answer",
            "official_answer",
            "correct",
            "valid_answer",
            "status",
            "closeout_mode",
            "athena_confidence_pct",
            "peer_validation_ready",
            "peer_candidates",
            "peer_statuses",
            "total_tokens",
            "total_prompt_tokens",
            "total_completion_tokens",
            "seconds",
            "turns",
            "loops",
        ],
    )

    boot_rows: list[dict[str, Any]] = []
    for runtime_label, role_obj in (boot.get("roles") or {}).items():
        memory_study = role_obj.get("memory_study") or {}
        boot_rows.append(
            {
                "runtime_label": runtime_label,
                "role_name": role_obj.get("role_name", ""),
                "passed": role_obj.get("passed", ""),
                "certified_count": role_obj.get("certified_count", ""),
                "probe_count": role_obj.get("probe_count", ""),
                "certification_line_limit": role_obj.get("certification_line_limit", ""),
                "memory_line_count": memory_study.get("memory_line_count", ""),
                "memory_chunk_count": memory_study.get("memory_chunk_count", ""),
                "study_passes": memory_study.get("study_passes", ""),
                "ack_count": memory_study.get("ack_count", ""),
                "ack_success_count": memory_study.get("ack_success_count", ""),
                "committed_prompt_tokens": (role_obj.get("memory_baseline") or {}).get(
                    "committed_prompt_tokens", ""
                ),
                "elapsed_seconds": role_obj.get("elapsed_seconds", ""),
                "certification_source_path": role_obj.get("certification_source_path", ""),
            }
        )
    write_csv(
        TABLES / "official_runtime_at_boot_summary.csv",
        boot_rows,
        [
            "runtime_label",
            "role_name",
            "passed",
            "certified_count",
            "probe_count",
            "certification_line_limit",
            "memory_line_count",
            "memory_chunk_count",
            "study_passes",
            "ack_count",
            "ack_success_count",
            "committed_prompt_tokens",
            "elapsed_seconds",
            "certification_source_path",
        ],
    )
    return misses


def build_visuals(
    rows: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    misses: list[dict[str, Any]],
    boot: dict[str, Any],
) -> None:
    by = {(row["idx"], row["run_key"]): row for row in rows}
    run_total = {run: sum(1 for row in rows if row["run_key"] == run and row["correct"]) for run in RUN_ORDER}
    run_mean_tokens = {
        run: statistics.mean([row["total_tokens"] for row in rows if row["run_key"] == run])
        for run in RUN_ORDER
    }
    run_mean_seconds = {
        run: statistics.mean([row["time_taken_seconds"] for row in rows if row["run_key"] == run])
        for run in RUN_ORDER
    }
    run_tokens_per_correct = {
        run: sum(row["total_tokens"] for row in rows if row["run_key"] == run) / run_total[run]
        for run in RUN_ORDER
    }

    body = [
        t(28, 38, "AIME 2026 Four-Run Scoreboard", "title"),
        t(
            28,
            60,
            "Official run is the Apr28 boot-certified artifact; bars show score out of 30 plus resource profile.",
            "subtitle",
        ),
    ]
    for index, run in enumerate(RUN_ORDER):
        y = 95 + index * 72
        score = run_total[run]
        body += [
            t(28, y + 22, RUN_LABELS[run]),
            rect(230, y, 560, 30, "#eef2f6"),
            rect(230, y, 560 * score / 30, 30, COLORS[run]),
            t(808, y + 22, f"{score}/30", "num"),
            t(
                230,
                y + 50,
                f"avg tokens {run_mean_tokens[run]:,.0f} | avg seconds {run_mean_seconds[run]:.1f} | tokens/correct {run_tokens_per_correct[run]:,.0f}",
                "small",
            ),
        ]
    (VIZ / "four_run_scoreboard_q1_q30.svg").write_text(svg_doc(900, 410, "\n".join(body)), encoding="utf-8")

    cell = 23
    left = 145
    top = 92
    body = [
        t(28, 38, "Q1-Q30 Result Grid", "title"),
        t(28, 60, "Green = correct, red = missed. Numbers inside cells are submitted answers.", "subtitle"),
    ]
    for idx in range(1, 31):
        body.append(t(left + (idx - 1) * cell + cell / 2, 82, str(idx), "small", "middle"))
    for row_index, run in enumerate(RUN_ORDER):
        y = top + row_index * 44
        body.append(t(28, y + 16, RUN_SHORT[run]))
        for idx in range(1, 31):
            row = by[(idx, run)]
            fill = COLORS["green"] if row["correct"] else COLORS["red"]
            body.append(rect(left + (idx - 1) * cell, y, cell - 3, 24, fill, rx=2))
            body.append(
                t(
                    left + (idx - 1) * cell + (cell - 3) / 2,
                    y + 16,
                    str(row["answer"])[:4],
                    "small",
                    "middle",
                    color="white",
                )
            )
    (VIZ / "q1_q30_four_run_result_grid.svg").write_text(svg_doc(900, 310, "\n".join(body)), encoding="utf-8")

    body = [
        t(28, 38, "Chunk Accuracy By Five-Problem Block", "title"),
        t(28, 60, "The official run held early easy wins, then fell behind in Q21-Q25.", "subtitle"),
    ]
    chunks = SLICES[:-1]
    base_x, base_y, chart_w, chart_h = 90, 350, 730, 230
    body += [line(base_x, base_y, base_x + chart_w, base_y), line(base_x, base_y, base_x, base_y - chart_h)]
    for pct in [0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = base_y - chart_h * pct
        body.append(line(base_x, y, base_x + chart_w, y, "#e5e7eb"))
        body.append(t(base_x - 12, y + 4, f"{int(pct * 100)}%", "small", "end"))
    slot = chart_w / len(chunks)
    bw = 18
    for chunk_index, (label, low, high) in enumerate(chunks):
        cx = base_x + chunk_index * slot + 20
        body.append(t(cx + 35, base_y + 28, label, "small", "middle"))
        for run_index, run in enumerate(RUN_ORDER):
            chunk = [row for row in rows if row["run_key"] == run and low <= row["idx"] <= high]
            acc = sum(1 for row in chunk if row["correct"]) / len(chunk)
            height = chart_h * acc
            body.append(rect(cx + run_index * (bw + 4), base_y - height, bw, height, COLORS[run], rx=2))
    for run_index, run in enumerate(RUN_ORDER):
        body += [rect(620, 85 + run_index * 20, 12, 12, COLORS[run]), t(638, 95 + run_index * 20, RUN_SHORT[run], "small")]
    (VIZ / "chunk_accuracy_four_run.svg").write_text(svg_doc(900, 420, "\n".join(body)), encoding="utf-8")

    body = [
        t(28, 38, "Token Efficiency And Score", "title"),
        t(28, 60, "Official is far cheaper than unrestricted, but lower score means it did not buy accuracy back.", "subtitle"),
    ]
    max_tokens = max(run_mean_tokens.values())
    for index, run in enumerate(RUN_ORDER):
        y = 100 + index * 70
        body.append(t(28, y + 21, RUN_SHORT[run]))
        body.append(rect(170, y, 530, 25, "#eef2f6"))
        body.append(rect(170, y, 530 * run_mean_tokens[run] / max_tokens, 25, COLORS[run]))
        body.append(t(715, y + 19, f"{run_mean_tokens[run]:,.0f} avg tokens"))
        body.append(t(170, y + 48, f"score {run_total[run]}/30, tokens per correct {run_tokens_per_correct[run]:,.0f}", "small"))
    (VIZ / "token_efficiency_four_run.svg").write_text(svg_doc(920, 420, "\n".join(body)), encoding="utf-8")

    body = [
        t(28, 38, "Official vs Apr27 Current: Problem-Level Delta", "title"),
        t(28, 60, "Blue = official fixed a current miss; red = official lost a current win; gray = unchanged.", "subtitle"),
    ]
    for comp in comparison:
        idx = comp["idx"]
        x = 70 + (idx - 1) * 26
        y = 110
        relation = comp["official_vs_current"]
        if relation == "official_fix_vs_current":
            fill, label = "#1565c0", "FIX"
        elif relation == "official_regression_vs_current":
            fill, label = COLORS["red"], "LOST"
        elif relation == "same_correct":
            fill, label = COLORS["green"], "WIN"
        else:
            fill, label = "#9aa4b2", "MISS"
        body.append(rect(x, y, 22, 34, fill, rx=3))
        body.append(t(x + 11, y - 7, str(idx), "small", "middle"))
        body.append(t(x + 11, y + 21, label, "small", "middle", color="white"))
    body.append(t(70, 180, "Official fixes: Q4, Q27. Official regressions vs current: Q7, Q11, Q18, Q23, Q24, Q28."))
    (VIZ / "official_vs_current_delta.svg").write_text(svg_doc(900, 230, "\n".join(body)), encoding="utf-8")

    mechanism_counts = Counter(miss["mechanism_bucket"] for miss in misses)
    body = [
        t(28, 38, "Official Miss Playbook", "title"),
        t(28, 60, "Mechanism buckets are inferred from result payload peer reports and scorer validity.", "subtitle"),
    ]
    y = 95
    for mechanism, count in mechanism_counts.most_common():
        body.append(t(40, y + 15, mechanism.replace("_", " ")))
        body.append(rect(320, y, 360, 22, "#eef2f6"))
        fill = "#d97706" if "arbitration" in mechanism or "mandatory" in mechanism else COLORS["red"]
        body.append(rect(320, y, 360 * count / max(mechanism_counts.values()), 22, fill))
        body.append(t(695, y + 16, str(count), "num"))
        y += 42
    miss_list = ", ".join(f"Q{m['idx']}={m['official_answer']} (exp {m['expected_answer']})" for m in misses)
    body.append(t(40, y + 24, f"Miss list: {miss_list}", "small"))
    (VIZ / "official_miss_playbook_q1_q30.svg").write_text(svg_doc(980, y + 70, "\n".join(body)), encoding="utf-8")

    body = [
        t(28, 38, "Late Game Box Score: Q26-Q30", "title"),
        t(28, 60, "Official fixed Q27 but still went 2/5 in Q26-Q30, same as Apr27 current.", "subtitle"),
    ]
    left, top, cell_w, row_h = 135, 100, 110, 42
    for j, idx in enumerate(range(26, 31)):
        body.append(t(left + j * cell_w + cell_w / 2, 90, f"Q{idx}", anchor="middle"))
    for i, run in enumerate(RUN_ORDER):
        y = top + i * row_h
        body.append(t(28, y + 25, RUN_SHORT[run]))
        for j, idx in enumerate(range(26, 31)):
            row = by[(idx, run)]
            fill = COLORS["green"] if row["correct"] else COLORS["red"]
            body.append(rect(left + j * cell_w, y, cell_w - 10, 30, fill))
            body.append(t(left + j * cell_w + (cell_w - 10) / 2, y + 20, row["answer"], anchor="middle", color="white"))
    (VIZ / "late_game_q26_q30_four_run.svg").write_text(svg_doc(760, 330, "\n".join(body)), encoding="utf-8")

    body = [
        t(28, 38, "Cumulative Score Trajectory", "title"),
        t(28, 60, "A ceiling would look like a sustained climb; official flattened after Q14 and lost Q21-Q25.", "subtitle"),
    ]
    x0, y0, width, height = 80, 340, 760, 240
    body += [line(x0, y0, x0 + width, y0), line(x0, y0, x0, y0 - height)]
    for value in [0, 5, 10, 15, 20, 25, 30]:
        y = y0 - height * value / 30
        body.append(line(x0, y, x0 + width, y, "#e5e7eb"))
        body.append(t(x0 - 12, y + 4, str(value), "small", "end"))
    for idx in [1, 5, 10, 15, 20, 25, 30]:
        x = x0 + width * (idx - 1) / 29
        body.append(t(x, y0 + 25, str(idx), "small", "middle"))
    for run in RUN_ORDER:
        points: list[tuple[float, float]] = []
        cumulative = 0
        for idx in range(1, 31):
            if by[(idx, run)]["correct"]:
                cumulative += 1
            x = x0 + width * (idx - 1) / 29
            y = y0 - height * cumulative / 30
            points.append((x, y))
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        body.append(f'<polyline points="{path}" fill="none" stroke="{COLORS[run]}" stroke-width="3"/>')
    for run_index, run in enumerate(RUN_ORDER):
        body += [rect(640, 90 + run_index * 20, 12, 12, COLORS[run]), t(658, 100 + run_index * 20, RUN_SHORT[run], "small")]
    (VIZ / "cumulative_score_trajectory_four_run.svg").write_text(svg_doc(920, 410, "\n".join(body)), encoding="utf-8")

    boot_rows = []
    for runtime_label, role_obj in (boot.get("roles") or {}).items():
        memory_study = role_obj.get("memory_study") or {}
        boot_rows.append(
            {
                "runtime_label": runtime_label,
                "role_name": role_obj.get("role_name", ""),
                "certified_count": role_obj.get("certified_count", ""),
                "probe_count": role_obj.get("probe_count", ""),
                "memory_line_count": memory_study.get("memory_line_count", ""),
                "committed_prompt_tokens": (role_obj.get("memory_baseline") or {}).get("committed_prompt_tokens", ""),
            }
        )
    body = [
        t(28, 38, "Official Boot Gate And Controller Shape", "title"),
        t(28, 60, "The boot gate passed, but solve-time closeout still used one-loop mandatory final arbitration.", "subtitle"),
    ]
    for i, boot_row in enumerate(boot_rows):
        y = 100 + i * 72
        body.append(t(35, y + 18, f"{boot_row['role_name']} ({boot_row['runtime_label']})"))
        body.append(rect(210, y, 150, 25, COLORS["green"]))
        body.append(t(285, y + 18, f"{boot_row['certified_count']}/{boot_row['probe_count']} certified", "small", "middle", color="white"))
        body.append(t(390, y + 18, f"memory lines {boot_row['memory_line_count']} | baseline prompt tokens {boot_row['committed_prompt_tokens']}"))
    body.append(t(35, 345, "Run controller: max_big_loops=1, inner exchanges=3, final closeout mode=athena_mandatory_final_answer_turn in payloads."))
    body.append(t(35, 370, "Interpretation: boot certification worked; the failure mode is downstream arbitration/verification pressure."))
    (VIZ / "official_boot_and_controller_shape.svg").write_text(svg_doc(950, 420, "\n".join(body)), encoding="utf-8")

    body = [
        t(28, 38, "Four-Run Side-By-Side Answers", "title"),
        t(28, 60, "Each cell shows submitted answer; green means correct against the official key.", "subtitle"),
    ]
    headers = ["Q", "Expected"] + [RUN_SHORT[run] for run in RUN_ORDER]
    widths = [40, 70, 125, 125, 125, 125]
    x = 28
    for header, col_width in zip(headers, widths):
        body.append(t(x + col_width / 2, 82, header, "small", "middle", weight="700"))
        x += col_width
    for idx in range(1, 31):
        y = 92 + (idx - 1) * 24
        bg = "#ffffff" if idx % 2 else "#f2f4f7"
        body.append(rect(24, y - 15, 720, 24, bg, rx=0))
        x = 28
        for value, col_width in zip([idx, comparison[idx - 1]["expected_answer"]], widths[:2]):
            body.append(t(x + col_width / 2, y, value, "small", "middle"))
            x += col_width
        for run, col_width in zip(RUN_ORDER, widths[2:]):
            row = by[(idx, run)]
            color = COLORS["green"] if row["correct"] else COLORS["red"]
            body.append(t(x + col_width / 2, y, row["answer"], "small", "middle", color=color, weight="700"))
            x += col_width
    (VIZ / "four_run_side_by_side_answers.svg").write_text(svg_doc(780, 850, "\n".join(body)), encoding="utf-8")


def write_markdown(
    rows: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    misses: list[dict[str, Any]],
    boot: dict[str, Any],
) -> dict[str, Any]:
    by = {(row["idx"], row["run_key"]): row for row in rows}
    run_total = {run: sum(1 for row in rows if row["run_key"] == run and row["correct"]) for run in RUN_ORDER}
    run_mean_tokens = {
        run: statistics.mean([row["total_tokens"] for row in rows if row["run_key"] == run])
        for run in RUN_ORDER
    }
    run_mean_seconds = {
        run: statistics.mean([row["time_taken_seconds"] for row in rows if row["run_key"] == run])
        for run in RUN_ORDER
    }
    official_correct = [comp["idx"] for comp in comparison if comp["official_correct"]]
    official_miss = [comp["idx"] for comp in comparison if not comp["official_correct"]]
    official_fixes = [comp["idx"] for comp in comparison if comp["official_vs_current"] == "official_fix_vs_current"]
    official_regressions = [
        comp["idx"] for comp in comparison if comp["official_vs_current"] == "official_regression_vs_current"
    ]
    official_beats_unrestricted = [
        comp["idx"] for comp in comparison if comp["official_correct"] and not comp["unrestricted_correct"]
    ]
    unrestricted_beats_official = [
        comp["idx"] for comp in comparison if comp["unrestricted_correct"] and not comp["official_correct"]
    ]
    invalids = [miss["idx"] for miss in misses if str(miss["valid_answer"]).lower() == "false"]
    boot_json = json.dumps(boot, sort_keys=True)
    boot_caveat = (
        "The official artifact passed Runtime-at-Boot, but its boot summary references "
        "V32/golden/role certification rows. Treat this run as evidence that the official "
        "boot gate worked for that packaged artifact, not as evidence that the later local "
        "v33 canon root was the Kaggle input."
        if "V32" in boot_json or "golden" in boot_json or "role" in boot_json
        else "The official artifact passed Runtime-at-Boot; no version-label caveat was detected in the boot summary."
    )

    report = f"""# AIME 2026 Official Four-Run Report

## Final Scoreboard

- Unrestricted: {run_total["unrestricted"]}/30.
- Apr27 current 0.2.3: {run_total["current"]}/30.
- Apr28 official boot run: {run_total["official"]}/30.
- Frozen pruned: {run_total["frozen"]}/30.

## Faithful Surprise

The official run did **not** hit the earlier current ceiling. It passed Runtime-at-Boot certification, used about {run_mean_tokens["official"]:,.0f} tokens/problem on average, and landed at **17/30**. That is far cheaper than the unrestricted paper run ({run_mean_tokens["unrestricted"]:,.0f} tokens/problem), but it gave back accuracy.

The good news is real but narrow: official fixed Q4 and Q27 relative to Apr27 current. The bad news is larger: it lost Q7, Q11, Q18, Q23, Q24, and Q28 that Apr27 current had right. Net against current: +2 fixes, -6 regressions, for a four-question drop.

## What Was Right

Official correct problems: {", ".join("Q" + str(i) for i in official_correct)}.

Official-over-unrestricted wins: {", ".join("Q" + str(i) for i in official_beats_unrestricted) or "none"}.

Official fixed current misses: {", ".join("Q" + str(i) for i in official_fixes)}.

## What Was Wrong

Official misses: {", ".join("Q" + str(i) for i in official_miss)}.

Official regressions vs Apr27 current: {", ".join("Q" + str(i) for i in official_regressions)}.

Official regressions vs unrestricted: {", ".join("Q" + str(i) for i in unrestricted_beats_official)}.

Invalid official answer(s): {", ".join("Q" + str(i) for i in invalids) or "none"}.

## Did Runtime-at-Boot Solve The Issue?

No, not as measured by final score. It solved the gate problem: Runtime-at-Boot passed for all three roles, with 25/25 certification probes per role and boot memory baselines captured. But the solve run still closed with one-loop mandatory Athena final arbitration, and several losses show peer disagreement, peer blockers, or high-confidence wrong finalization.

The run therefore looks like a **resource/context win plus a verification/arbitration regression**. It did not prove the model ceiling; it exposed a controller ceiling.

## Boot Dataset Caveat

{boot_caveat}

## Did We Make More Issue?

We made at least one issue more visible: the system can certify boot memory and still submit a bad or invalid final answer under mandatory final closeout. Q9 is the cleanest alarm: official submitted `4133`, outside the AIME answer range, despite answer bounds being present in the controller config.

## Ceiling Read

The empirical ceiling from these four artifacts is still unrestricted at 22/30, then Apr27 current at 21/30. The official run did not hit that ceiling. Its 17/30 says the current bottleneck is not raw context budget; it is final-answer validation, disagreement handling, and allowing enough repair/search when peers are not actually aligned.

## Visuals

- [Four-run scoreboard](data_visualizations/four_run_scoreboard_q1_q30.svg)
- [Q1-Q30 result grid](data_visualizations/q1_q30_four_run_result_grid.svg)
- [Chunk accuracy](data_visualizations/chunk_accuracy_four_run.svg)
- [Token efficiency](data_visualizations/token_efficiency_four_run.svg)
- [Official vs current delta](data_visualizations/official_vs_current_delta.svg)
- [Official miss playbook](data_visualizations/official_miss_playbook_q1_q30.svg)
- [Late-game box score](data_visualizations/late_game_q26_q30_four_run.svg)
- [Cumulative score trajectory](data_visualizations/cumulative_score_trajectory_four_run.svg)
- [Official boot/controller shape](data_visualizations/official_boot_and_controller_shape.svg)
- [Four-run side-by-side answers](data_visualizations/four_run_side_by_side_answers.svg)

## Tables

- `data_analysis/tables/all_four_runs_q1_q30_long.csv`
- `data_analysis/tables/four_run_q1_q30_comparison.csv`
- `data_analysis/tables/run_summary_q1_q30_and_slices.csv`
- `data_analysis/tables/official_q1_q30_detail.csv`
- `data_analysis/tables/official_failure_warning_taxonomy_q1_q30.csv`
- `data_analysis/tables/official_runtime_at_boot_summary.csv`
"""
    (OUT / "OFFICIAL_FOUR_RUN_HEADLINE_REPORT.md").write_text(report, encoding="utf-8")

    visual_index = """# Visual Index

- `four_run_scoreboard_q1_q30.svg`
- `q1_q30_four_run_result_grid.svg`
- `chunk_accuracy_four_run.svg`
- `token_efficiency_four_run.svg`
- `official_vs_current_delta.svg`
- `official_miss_playbook_q1_q30.svg`
- `late_game_q26_q30_four_run.svg`
- `cumulative_score_trajectory_four_run.svg`
- `official_boot_and_controller_shape.svg`
- `four_run_side_by_side_answers.svg`
"""
    (OUT / "VISUAL_INDEX.md").write_text(visual_index, encoding="utf-8")

    manifest = {
        "event": "official_four_run_report_built",
        "official_run_dir": str(OFFICIAL),
        "prior_three_run_report_dir": str(OLD_REPORT),
        "output_dir": str(OUT),
        "scores": {run: run_total[run] for run in RUN_ORDER},
        "official_correct": official_correct,
        "official_misses": official_miss,
        "official_fixes_vs_current": official_fixes,
        "official_regressions_vs_current": official_regressions,
        "mean_tokens": {run: round(run_mean_tokens[run], 1) for run in RUN_ORDER},
        "mean_seconds": {run: round(run_mean_seconds[run], 3) for run in RUN_ORDER},
        "runtime_at_boot_passed": boot.get("passed"),
        "boot_revision": boot.get("revision"),
        "warning": (
            "Official boot log certifies V32/golden/role probe rows; this artifact is not evidence "
            "of the later local v33 canon root unless Kaggle input was updated separately."
        ),
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (SCRIPTS / "README_BUILD.md").write_text(
        "Generated by AthenaV5/tools/build_official_four_run_report.py from official run and prior three-run report tables.\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    for path in (TABLES, VIZ, SCRIPTS):
        path.mkdir(parents=True, exist_ok=True)
    rows, payload_meta, boot = load_rows()
    comparison = build_comparison(rows)
    summary = build_summary(rows)
    misses = write_tables(rows, comparison, summary, payload_meta, boot)
    build_visuals(rows, comparison, summary, misses, boot)
    manifest = write_markdown(rows, comparison, misses, boot)
    manifest["visual_count"] = len(list(VIZ.glob("*.svg")))
    manifest["table_count"] = len(list(TABLES.glob("*.csv")))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
