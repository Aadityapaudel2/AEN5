from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from athena_paths import get_evaluation_testdata_dir, get_orchestrator_model_dir, get_root_dir

from .eval import evaluate_math_loop
from .loop import run_math_loop


def _default_manifest_path() -> Path:
    return get_evaluation_testdata_dir() / "aimo" / "manifest.jsonl"


def _configure_stdout() -> None:
    stream = getattr(sys, "stdout", None)
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="backslashreplace")


def _cmd_solve(args: argparse.Namespace) -> int:
    problem_text = args.problem.strip()
    if args.file:
        problem_text = Path(args.file).expanduser().resolve().read_text(encoding="utf-8-sig").strip()
    if not problem_text:
        raise SystemExit("No problem text provided. Use --problem or --file.")
    result = run_math_loop(
        problem_text,
        model_dir=args.model_dir,
        max_rounds=args.max_rounds,
        tools_enabled=not args.no_tools,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    summary = evaluate_math_loop(
        manifest_path=args.manifest,
        limit=args.limit,
        model_dir=args.model_dir,
        max_rounds=args.max_rounds,
    )
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic math loop utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    solve_parser = subparsers.add_parser("solve", help="Run the 2-body math loop on one problem.")
    solve_parser.add_argument("--problem", default="", help="Inline problem text.")
    solve_parser.add_argument("--file", default="", help="Read problem text from a file.")
    solve_parser.add_argument("--model-dir", default=str(get_orchestrator_model_dir()))
    solve_parser.add_argument("--max-rounds", type=int, default=2)
    solve_parser.add_argument("--no-tools", action="store_true")
    solve_parser.set_defaults(func=_cmd_solve)

    eval_parser = subparsers.add_parser("eval", help="Run baseline vs 2-body loop evaluation on a manifest subset.")
    eval_parser.add_argument("--manifest", default=str(_default_manifest_path()))
    eval_parser.add_argument("--limit", type=int, default=25)
    eval_parser.add_argument("--model-dir", default=str(get_orchestrator_model_dir()))
    eval_parser.add_argument("--max-rounds", type=int, default=2)
    eval_parser.set_defaults(func=_cmd_eval)
    return parser


def main() -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
