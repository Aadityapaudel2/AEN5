from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from athena_paths import get_orchestrator_model_dir
from desktop_engine.runtime import AthenaRuntime

from .loop import MathLoopRunner, execute_math_loop, run_single_pass_solver
from .schemas import MathProblem

DEFAULT_ID_COLUMN_CANDIDATES = ("id", "Id", "problem_id", "problemId")
DEFAULT_PROBLEM_COLUMN_CANDIDATES = ("problem", "question", "prompt", "text")
DEFAULT_OUTPUT_ANSWER_COLUMN = "answer"
DEFAULT_FALLBACK_ANSWER = "0"
DEFAULT_ANSWER_MODULUS = 100000
DEFAULT_ANSWER_WIDTH = 0


@dataclass(frozen=True)
class SubmissionCase:
    row_id: str
    problem_text: str
    source_row: dict[str, str]


@dataclass(frozen=True)
class SubmissionTrace:
    row_id: str
    strategy: str
    raw_answer: str
    normalized_answer: str
    verified: bool
    status: str
    rounds_used: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "strategy": self.strategy,
            "raw_answer": self.raw_answer,
            "normalized_answer": self.normalized_answer,
            "verified": self.verified,
            "status": self.status,
            "rounds_used": self.rounds_used,
        }


def _configure_stdout() -> None:
    stream = getattr(sys, "stdout", None)
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="backslashreplace")


def _read_rows(input_path: Path) -> list[dict[str, str]]:
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    if suffix == ".jsonl":
        rows: list[dict[str, str]] = []
        with input_path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append({str(key): "" if value is None else str(value) for key, value in payload.items()})
        return rows
    if suffix == ".parquet":
        return _read_parquet_rows(input_path)
    raise ValueError(f"Unsupported input format: {input_path.suffix}")


def _read_parquet_rows(input_path: Path) -> list[dict[str, str]]:
    try:
        import pyarrow.parquet as pq  # type: ignore[import-not-found]

        table = pq.read_table(input_path)
        raw_rows = table.to_pylist()
    except Exception:
        try:
            import pandas as pd  # type: ignore[import-not-found]

            raw_rows = pd.read_parquet(input_path).to_dict(orient="records")
        except Exception as exc:
            raise RuntimeError("Reading parquet requires `pyarrow` or `pandas`.") from exc
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if isinstance(row, dict):
            rows.append({str(key): "" if value is None else str(value) for key, value in row.items()})
    return rows


def _infer_column(rows: list[dict[str, str]], explicit: str, candidates: Iterable[str], label: str) -> str:
    if explicit:
        return explicit
    if not rows:
        raise ValueError(f"Cannot infer {label} column from empty input.")
    first = rows[0]
    for candidate in candidates:
        if candidate in first:
            return candidate
    raise ValueError(f"Could not infer {label} column. Provide it explicitly.")


def _load_sample_submission(path: Path) -> tuple[list[dict[str, str]], str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if len(fieldnames) < 2:
            raise ValueError("sample_submission.csv must contain at least two columns.")
        rows = [dict(row) for row in reader]
    return rows, fieldnames[0], fieldnames[1]


def load_submission_cases(
    input_path: Path | str,
    *,
    id_column: str = "",
    problem_column: str = "",
    sample_submission_path: Path | str | None = None,
) -> tuple[list[SubmissionCase], str, str]:
    input_file = Path(input_path).expanduser().resolve()
    rows = _read_rows(input_file)
    inferred_id = _infer_column(rows, id_column, DEFAULT_ID_COLUMN_CANDIDATES, "id")
    inferred_problem = _infer_column(rows, problem_column, DEFAULT_PROBLEM_COLUMN_CANDIDATES, "problem")
    output_answer_column = DEFAULT_OUTPUT_ANSWER_COLUMN
    if sample_submission_path:
        sample_file = Path(sample_submission_path).expanduser().resolve()
        sample_rows, sample_id_column, sample_answer_column = _load_sample_submission(sample_file)
        input_by_id = {str(row.get(inferred_id, "")).strip(): row for row in rows}
        ordered_rows: list[dict[str, str]] = []
        for row in sample_rows:
            row_id = str(row.get(sample_id_column, "")).strip()
            if not row_id:
                continue
            if row_id not in input_by_id:
                raise KeyError(f"sample_submission id `{row_id}` not found in input rows.")
            ordered_rows.append(input_by_id[row_id])
        rows = ordered_rows
        inferred_id = sample_id_column
        output_answer_column = sample_answer_column
    cases: list[SubmissionCase] = []
    for row in rows:
        row_id = str(row.get(inferred_id, "")).strip()
        problem_text = str(row.get(inferred_problem, "")).strip()
        if not row_id:
            raise ValueError(f"Input row is missing id column `{inferred_id}`.")
        if not problem_text:
            raise ValueError(f"Input row `{row_id}` is missing problem text column `{inferred_problem}`.")
        cases.append(SubmissionCase(row_id=row_id, problem_text=problem_text, source_row=row))
    return cases, inferred_id, output_answer_column


def extract_submission_answer(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""
    answer_line_match = re.search(r"(?im)^\s*answer\s*:\s*(.+?)\s*$", text)
    if answer_line_match:
        return answer_line_match.group(1).strip()
    final_answer_match = re.search(r"(?im)^\s*final_answer\s*:\s*(.+?)\s*$", text)
    if final_answer_match:
        return final_answer_match.group(1).strip()
    matches = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:/\d+)?", text)
    if matches:
        return matches[-1]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def normalize_submission_answer(
    raw_text: str,
    *,
    modulus: int | None = DEFAULT_ANSWER_MODULUS,
    width: int = DEFAULT_ANSWER_WIDTH,
    fallback: str = DEFAULT_FALLBACK_ANSWER,
) -> str:
    extracted = extract_submission_answer(raw_text)
    if not extracted:
        return fallback
    try:
        frac = Fraction(extracted)
    except Exception:
        compact = " ".join(extracted.split())
        return compact or fallback
    if frac.denominator == 1:
        integer_value = int(frac)
        if modulus is not None and modulus > 0:
            integer_value %= int(modulus)
        if width > 0:
            sign = "-" if integer_value < 0 else ""
            digits = str(abs(integer_value)).zfill(width)
            return f"{sign}{digits}"
        return str(integer_value)
    return f"{frac.numerator}/{frac.denominator}"


def solve_submission_case(
    case: SubmissionCase,
    *,
    strategy: str,
    runner: MathLoopRunner,
    max_rounds: int,
) -> tuple[str, bool, str, int]:
    if strategy == "baseline":
        draft, step = run_single_pass_solver(
            case.problem_text,
            runtime=runner.runtime,
            tools_enabled=runner.runtime.tools_enabled,
        )
        raw_answer = draft.final_answer if draft is not None else step.raw_output
        return raw_answer, False, "baseline", 1
    loop_result = execute_math_loop(
        MathProblem(problem_text=case.problem_text, source_id=case.row_id),
        runner.invoke,
        max_rounds=max_rounds,
        repair_role=runner.repair,
    )
    raw_answer = loop_result.final_answer or ""
    if not raw_answer and loop_result.solver_draft is not None:
        raw_answer = loop_result.solver_draft.raw_output
    return raw_answer, bool(loop_result.verified), str(loop_result.status), int(loop_result.rounds_used)


def build_kaggle_submission(
    *,
    input_path: Path | str,
    output_path: Path | str,
    model_dir: Path | str | None = None,
    strategy: str = "loop",
    max_rounds: int = 2,
    tools_enabled: bool = True,
    id_column: str = "",
    problem_column: str = "",
    answer_column: str = "",
    sample_submission_path: Path | str | None = None,
    trace_jsonl_path: Path | str | None = None,
    answer_modulus: int | None = DEFAULT_ANSWER_MODULUS,
    answer_width: int = DEFAULT_ANSWER_WIDTH,
    fallback_answer: str = DEFAULT_FALLBACK_ANSWER,
) -> dict[str, Any]:
    cases, resolved_id_column, resolved_answer_column = load_submission_cases(
        input_path,
        id_column=id_column,
        problem_column=problem_column,
        sample_submission_path=sample_submission_path,
    )
    if answer_column:
        resolved_answer_column = answer_column
    runtime = AthenaRuntime(model_dir=model_dir or get_orchestrator_model_dir(), tools_enabled=tools_enabled)
    runtime.tools_enabled = bool(tools_enabled)
    runner = MathLoopRunner(runtime=runtime, tools_enabled=tools_enabled)
    output_file = Path(output_path).expanduser().resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    trace_file = Path(trace_jsonl_path).expanduser().resolve() if trace_jsonl_path else None
    if trace_file is not None:
        trace_file.parent.mkdir(parents=True, exist_ok=True)
        if trace_file.exists():
            trace_file.unlink()
    traces: list[SubmissionTrace] = []
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[resolved_id_column, resolved_answer_column])
        writer.writeheader()
        for case in cases:
            raw_answer, verified, status, rounds_used = solve_submission_case(
                case,
                strategy=strategy,
                runner=runner,
                max_rounds=max_rounds,
            )
            normalized = normalize_submission_answer(
                raw_answer,
                modulus=answer_modulus,
                width=answer_width,
                fallback=fallback_answer,
            )
            writer.writerow(
                {
                    resolved_id_column: case.row_id,
                    resolved_answer_column: normalized,
                }
            )
            trace = SubmissionTrace(
                row_id=case.row_id,
                strategy=strategy,
                raw_answer=raw_answer,
                normalized_answer=normalized,
                verified=verified,
                status=status,
                rounds_used=rounds_used,
            )
            traces.append(trace)
            if trace_file is not None:
                with trace_file.open("a", encoding="utf-8") as trace_handle:
                    trace_handle.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")
    return {
        "ok": True,
        "input_path": str(Path(input_path).expanduser().resolve()),
        "output_path": str(output_file),
        "total_cases": len(cases),
        "strategy": strategy,
        "model_dir": str(model_dir or get_orchestrator_model_dir()),
        "id_column": resolved_id_column,
        "answer_column": resolved_answer_column,
        "trace_jsonl_path": str(trace_file) if trace_file is not None else "",
        "sample_submission_path": str(Path(sample_submission_path).expanduser().resolve()) if sample_submission_path else "",
        "answer_modulus": answer_modulus,
        "answer_width": answer_width,
        "fallback_answer": fallback_answer,
        "preview": [trace.to_dict() for trace in traces[:5]],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Kaggle-style submission CSV from the agentic math loop.")
    parser.add_argument("--input", required=True, help="Input file (.csv, .jsonl, .parquet) containing problems.")
    parser.add_argument("--output", required=True, help="Output submission CSV path.")
    parser.add_argument("--sample-submission", default="", help="Optional sample_submission.csv to preserve id order and answer column name.")
    parser.add_argument("--model-dir", default=str(get_orchestrator_model_dir()))
    parser.add_argument("--strategy", choices=("baseline", "loop"), default="loop")
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument("--id-column", default="", help="Explicit id column name if inference fails.")
    parser.add_argument("--problem-column", default="", help="Explicit problem/prompt column name if inference fails.")
    parser.add_argument("--answer-column", default="", help="Override answer column name in the output CSV.")
    parser.add_argument("--trace-jsonl", default="", help="Optional debug trace JSONL path.")
    parser.add_argument("--answer-modulus", type=int, default=DEFAULT_ANSWER_MODULUS)
    parser.add_argument("--answer-width", type=int, default=DEFAULT_ANSWER_WIDTH)
    parser.add_argument("--fallback-answer", default=DEFAULT_FALLBACK_ANSWER)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_kaggle_submission(
        input_path=args.input,
        output_path=args.output,
        sample_submission_path=args.sample_submission or None,
        model_dir=args.model_dir,
        strategy=args.strategy,
        max_rounds=args.max_rounds,
        tools_enabled=not args.no_tools,
        id_column=args.id_column,
        problem_column=args.problem_column,
        answer_column=args.answer_column,
        trace_jsonl_path=args.trace_jsonl or None,
        answer_modulus=(args.answer_modulus if args.answer_modulus > 0 else None),
        answer_width=max(0, int(args.answer_width)),
        fallback_answer=str(args.fallback_answer),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())