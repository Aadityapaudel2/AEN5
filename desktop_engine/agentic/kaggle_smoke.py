from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from athena_paths import get_orchestrator_model_dir
from desktop_engine.runtime import AthenaRuntime

from .kaggle_entry import (
    DEFAULT_ANSWER_MODULUS,
    DEFAULT_ANSWER_WIDTH,
    DEFAULT_FALLBACK_ANSWER,
    normalize_submission_answer,
)
from .loop import MathLoopRunner, execute_math_loop, run_single_pass_solver
from .schemas import MathLoopStep, MathProblem


def _configure_stdout() -> None:
    stream = getattr(sys, "stdout", None)
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="backslashreplace")


def _load_problem_text(problem: str, file_path: str) -> str:
    if file_path:
        return Path(file_path).expanduser().resolve().read_text(encoding="utf-8-sig").strip()
    return (problem or "").strip()


def _step_to_terminal_row(step: MathLoopStep) -> dict[str, Any]:
    return {
        "role": step.role,
        "round": step.round_index,
        "status": step.status,
        "latency_ms": step.latency_ms,
        "parsed_output": step.parsed_output,
        "raw_output": step.raw_output,
    }


def run_kaggle_smoke(
    *,
    problem_text: str,
    model_dir: Path | str | None = None,
    strategy: str = "loop",
    max_rounds: int = 2,
    tools_enabled: bool = True,
    answer_modulus: int | None = DEFAULT_ANSWER_MODULUS,
    answer_width: int = DEFAULT_ANSWER_WIDTH,
    fallback_answer: str = DEFAULT_FALLBACK_ANSWER,
) -> dict[str, Any]:
    runtime = AthenaRuntime(model_dir=model_dir or get_orchestrator_model_dir(), tools_enabled=tools_enabled)
    runtime.tools_enabled = bool(tools_enabled)
    runner = MathLoopRunner(runtime=runtime, tools_enabled=tools_enabled)

    if strategy == "baseline":
        draft, step = run_single_pass_solver(
            problem_text,
            runtime=runner.runtime,
            tools_enabled=runner.runtime.tools_enabled,
        )
        raw_answer = draft.final_answer if draft is not None else step.raw_output
        normalized_answer = normalize_submission_answer(
            raw_answer,
            modulus=answer_modulus,
            width=answer_width,
            fallback=fallback_answer,
        )
        return {
            "ok": True,
            "strategy": strategy,
            "model_dir": str(model_dir or get_orchestrator_model_dir()),
            "tools_enabled": bool(tools_enabled),
            "raw_answer": raw_answer,
            "normalized_answer": normalized_answer,
            "verified": False,
            "status": "baseline",
            "rounds_used": 1,
            "steps": [_step_to_terminal_row(step)],
        }

    step_rows: list[dict[str, Any]] = []

    def observer(step: MathLoopStep) -> None:
        step_rows.append(_step_to_terminal_row(step))

    loop_result = execute_math_loop(
        MathProblem(problem_text=problem_text, source_id="smoke"),
        runner.invoke,
        max_rounds=max_rounds,
        repair_role=runner.repair,
        on_step=observer,
    )
    raw_answer = loop_result.final_answer or ""
    if not raw_answer and loop_result.solver_draft is not None:
        raw_answer = loop_result.solver_draft.raw_output
    normalized_answer = normalize_submission_answer(
        raw_answer,
        modulus=answer_modulus,
        width=answer_width,
        fallback=fallback_answer,
    )
    return {
        "ok": True,
        "strategy": strategy,
        "model_dir": str(model_dir or get_orchestrator_model_dir()),
        "tools_enabled": bool(tools_enabled),
        "raw_answer": raw_answer,
        "normalized_answer": normalized_answer,
        "verified": bool(loop_result.verified),
        "status": str(loop_result.status),
        "rounds_used": int(loop_result.rounds_used),
        "error_message": loop_result.error_message,
        "steps": step_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a single headless Kaggle-style math smoke test in the terminal.")
    parser.add_argument("--problem", default="", help="Inline problem text.")
    parser.add_argument("--file", default="", help="Read problem text from a file.")
    parser.add_argument("--model-dir", default=str(get_orchestrator_model_dir()))
    parser.add_argument("--strategy", choices=("baseline", "loop"), default="baseline")
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument("--answer-modulus", type=int, default=DEFAULT_ANSWER_MODULUS)
    parser.add_argument("--answer-width", type=int, default=DEFAULT_ANSWER_WIDTH)
    parser.add_argument("--fallback-answer", default=DEFAULT_FALLBACK_ANSWER)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    problem_text = _load_problem_text(args.problem, args.file)
    if not problem_text:
        raise SystemExit("No problem text provided. Use --problem or --file.")
    summary = run_kaggle_smoke(
        problem_text=problem_text,
        model_dir=args.model_dir,
        strategy=args.strategy,
        max_rounds=args.max_rounds,
        tools_enabled=not args.no_tools,
        answer_modulus=(args.answer_modulus if args.answer_modulus > 0 else None),
        answer_width=max(0, int(args.answer_width)),
        fallback_answer=str(args.fallback_answer),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
