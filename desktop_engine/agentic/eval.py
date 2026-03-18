from __future__ import annotations

import argparse
import json
import re
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

from athena_paths import get_evaluation_testdata_dir, get_orchestrator_model_dir, get_root_dir
from desktop_engine.runtime import AthenaRuntime

from .loop import MathLoopRunner, execute_math_loop, run_single_pass_solver
from .schemas import EvalCaseResult, EvalSummary, MathProblem


def evaluate_math_loop(
    manifest_path: Path | str,
    limit: int,
    model_dir: Path | str | None = None,
    max_rounds: int = 2,
) -> EvalSummary:
    manifest = Path(manifest_path).expanduser().resolve()
    rows = _load_manifest_rows(manifest, limit)
    runtime = AthenaRuntime(model_dir=model_dir or get_orchestrator_model_dir(), tools_enabled=True)
    runtime.tools_enabled = True
    runner = MathLoopRunner(runtime=runtime, tools_enabled=True)
    cases: list[EvalCaseResult] = []

    baseline_correct = 0
    loop_correct = 0
    baseline_arithmetic_errors = 0
    loop_arithmetic_errors = 0
    false_verifier_critiques = 0
    total_rounds = 0
    baseline_latency_total = 0
    loop_latency_total = 0
    numeric_gold_cases = 0

    for row in rows:
        problem_text = _read_problem_text(manifest, row)
        gold_answer = _extract_gold_answer(row)
        baseline_draft, baseline_step = run_single_pass_solver(
            problem_text,
            runtime=runtime,
            tools_enabled=True,
        )
        loop_result = execute_math_loop(
            MathProblem(problem_text=problem_text),
            runner.invoke,
            max_rounds=max_rounds,
            repair_role=runner.repair,
        )

        baseline_answer = baseline_draft.final_answer if baseline_draft is not None else ""
        loop_answer = loop_result.final_answer.strip()
        baseline_match = _answers_match(gold_answer, baseline_answer)
        loop_match = _answers_match(gold_answer, loop_answer)

        if baseline_match:
            baseline_correct += 1
        if loop_match:
            loop_correct += 1

        if _looks_numeric(gold_answer):
            numeric_gold_cases += 1
            if baseline_answer and not baseline_match:
                baseline_arithmetic_errors += 1
            if loop_answer and not loop_match:
                loop_arithmetic_errors += 1

        first_solver_answer = ""
        first_verifier_verdict = ""
        for step in loop_result.trace.steps:
            if step.role == "solver" and not first_solver_answer:
                first_solver_answer = str(step.parsed_output.get("final_answer") or "")
            if step.role == "verifier" and not first_verifier_verdict:
                first_verifier_verdict = str(step.parsed_output.get("verdict") or "")
        if first_verifier_verdict == "revise" and _answers_match(gold_answer, first_solver_answer):
            false_verifier_critiques += 1

        loop_latency = sum(step.latency_ms for step in loop_result.trace.steps)
        baseline_latency_total += baseline_step.latency_ms
        loop_latency_total += loop_latency
        total_rounds += loop_result.rounds_used

        cases.append(
            EvalCaseResult(
                source_id=str(row.get("instance_id") or row.get("filename") or row.get("problem_path") or ""),
                gold_answer=gold_answer,
                baseline_answer=baseline_answer,
                loop_answer=loop_answer,
                baseline_correct=baseline_match,
                loop_correct=loop_match,
                verified=loop_result.verified,
                status=loop_result.status,
                rounds_used=loop_result.rounds_used,
                false_verifier_critique=first_verifier_verdict == "revise" and _answers_match(gold_answer, first_solver_answer),
                baseline_latency_ms=baseline_step.latency_ms,
                loop_latency_ms=loop_latency,
            )
        )

    total_cases = len(cases)
    numeric_denominator = numeric_gold_cases or 1
    return EvalSummary(
        manifest_path=str(manifest),
        total_cases=total_cases,
        exact_accuracy_baseline=(baseline_correct / total_cases) if total_cases else 0.0,
        exact_accuracy_loop=(loop_correct / total_cases) if total_cases else 0.0,
        arithmetic_error_rate_baseline=(baseline_arithmetic_errors / numeric_denominator),
        arithmetic_error_rate_loop=(loop_arithmetic_errors / numeric_denominator),
        false_verifier_critique_rate=(false_verifier_critiques / total_cases) if total_cases else 0.0,
        average_rounds_used=(total_rounds / total_cases) if total_cases else 0.0,
        average_latency_ms_baseline=(baseline_latency_total / total_cases) if total_cases else 0.0,
        average_latency_ms_loop=(loop_latency_total / total_cases) if total_cases else 0.0,
        cases=cases,
    )


def _load_manifest_rows(manifest_path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
            if len(rows) >= max(1, int(limit)):
                break
    return rows


def _read_problem_text(manifest_path: Path, row: dict[str, Any]) -> str:
    rel_path = str(row.get("problem_path") or "").strip()
    if not rel_path:
        raise FileNotFoundError("Manifest row missing problem_path")
    problem_path = (manifest_path.parent / rel_path).resolve()
    return problem_path.read_text(encoding="utf-8-sig").strip()


def _extract_gold_answer(row: dict[str, Any]) -> str:
    snapshot = (
        row.get("canon_metadata", {})
        if isinstance(row.get("canon_metadata"), dict)
        else {}
    )
    instance_snapshot = snapshot.get("instance_snapshot", {}) if isinstance(snapshot, dict) else {}
    final_answer = instance_snapshot.get("final_answer", {}) if isinstance(instance_snapshot, dict) else {}
    normalized = final_answer.get("normalized") if isinstance(final_answer, dict) else None
    if normalized not in (None, ""):
        return str(normalized).strip()
    raw = row.get("answer")
    return str(raw).strip()


def _answers_match(gold: str, predicted: str) -> bool:
    gold_norm = _normalize_answer(gold)
    pred_norm = _normalize_answer(predicted)
    if not gold_norm or not pred_norm:
        return False
    if gold_norm == pred_norm:
        return True
    gold_fraction = _parse_fractional(gold_norm)
    pred_fraction = _parse_fractional(pred_norm)
    return gold_fraction is not None and pred_fraction is not None and gold_fraction == pred_fraction


def _normalize_answer(text: str) -> str:
    value = str(text or "").strip()
    value = value.replace("$", "").replace("\\(", "").replace("\\)", "")
    value = value.replace("\\boxed{", "").replace("}", "")
    value = value.strip()
    value = " ".join(value.split())
    tail = _extract_tail_numeric(value)
    return tail or value


def _parse_fractional(text: str) -> Fraction | None:
    probe = text.strip()
    if not probe:
        return None
    if probe.lower().startswith("answer:"):
        probe = probe.split(":", 1)[1].strip()
    try:
        return Fraction(probe)
    except Exception:
        return None


def _looks_numeric(text: str) -> bool:
    return _parse_fractional(text) is not None


def _extract_tail_numeric(text: str) -> str:
    matches = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:/\d+)?", text)
    if not matches:
        return ""
    return matches[-1]


def _default_manifest_path() -> Path:
    return get_evaluation_testdata_dir() / "aimo" / "manifest.jsonl"


def _configure_stdout() -> None:
    stream = getattr(sys, "stdout", None)
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="backslashreplace")


def main() -> None:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="Evaluate the 2-body math loop on local testdata.")
    parser.add_argument("--manifest", default=str(_default_manifest_path()))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--model-dir", default=str(get_orchestrator_model_dir()))
    parser.add_argument("--max-rounds", type=int, default=2)
    args = parser.parse_args()

    summary = evaluate_math_loop(
        manifest_path=args.manifest,
        limit=args.limit,
        model_dir=args.model_dir,
        max_rounds=args.max_rounds,
    )
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
