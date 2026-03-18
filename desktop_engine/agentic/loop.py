from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from athena_paths import get_orchestrator_model_dir
from desktop_engine.events import EngineEvent
from desktop_engine.runtime import AthenaRuntime

from .prompts import (
    SOLVER_SYSTEM_PROMPT,
    VERIFIER_SYSTEM_PROMPT,
    build_solver_prompt,
    build_verifier_prompt,
)
from .schemas import (
    ConfidenceLevel,
    MathLoopResult,
    MathLoopStep,
    MathLoopTrace,
    MathProblem,
    SolverDraft,
    VerifierReport,
)

AGENTIC_MAX_NEW_TOKENS = 1024
IDENTITY_DRIFT_RE = re.compile(
    r"\b(renamed|role override|claim to be|my identity|your identity|identity remains fixed|i will not be renamed|you are mistaken;\s*i am)\b",
    re.IGNORECASE,
)

SOLVER_OUTPUT_RE = re.compile(
    r"^\s*FINAL_ANSWER:\s*(?P<final>.*?)^\s*CONFIDENCE:\s*(?P<confidence>.+?)\s*^\s*SOLUTION:\s*(?P<solution>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
VERIFIER_OUTPUT_RE = re.compile(
    r"^\s*VERDICT:\s*(?P<verdict>pass|revise|insufficient)\s*^\s*FINAL_ANSWER_CHECK:\s*(?P<check>correct|incorrect|unclear)\s*^\s*ISSUES:\s*(?P<issues>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class RoleCallResult:
    raw_output: str
    tool_events: list[dict[str, Any]]
    latency_ms: int


@dataclass(frozen=True)
class ParsedOutput:
    ok: bool
    payload: SolverDraft | VerifierReport | None
    error: str = ""


RoleInvoker = Callable[[str, str, str], RoleCallResult]
RepairInvoker = Callable[[str, str], RoleCallResult]
StepObserver = Callable[[MathLoopStep], None]


SOLVER_REPAIR_SYSTEM_PROMPT = (
    "You are a strict output normalizer for a mathematical solver. "
    "Convert the supplied draft into this exact marker format only:\n"
    "FINAL_ANSWER:\nCONFIDENCE:\nSOLUTION:\n"
    "If the draft gives an answer but no explicit confidence, use medium. "
    "Do not add commentary outside the required markers."
)


VERIFIER_REPAIR_SYSTEM_PROMPT = (
    "You are a strict output normalizer for a mathematical verifier. "
    "Convert the supplied verifier draft into this exact marker format only:\n"
    "VERDICT:\nFINAL_ANSWER_CHECK:\nISSUES:\n"
    "If the draft is too unclear to classify, use VERDICT: insufficient and FINAL_ANSWER_CHECK: unclear. "
    "Do not add commentary outside the required markers."
)


class MathLoopRunner:
    def __init__(self, *, model_dir: Path | str | None = None, tools_enabled: bool = True, runtime: AthenaRuntime | None = None):
        if runtime is None:
            runtime = AthenaRuntime(model_dir=model_dir or get_orchestrator_model_dir(), tools_enabled=tools_enabled)
        self.runtime = runtime
        self.runtime.tools_enabled = bool(tools_enabled)
        self.runtime.temperature = 0.0
        self.runtime.top_p = 1.0
        self.runtime.top_k = 0
        self.runtime.max_new_tokens = min(int(self.runtime.max_new_tokens), AGENTIC_MAX_NEW_TOKENS)

    def invoke(self, role: str, system_prompt: str, prompt_text: str) -> RoleCallResult:
        return self._invoke(role, system_prompt, prompt_text, tools_enabled=self.runtime.tools_enabled)

    def repair(self, role: str, raw_output: str) -> RoleCallResult:
        if role == "solver":
            system_prompt = SOLVER_REPAIR_SYSTEM_PROMPT
            prompt_text = (
                "Rewrite this solver draft into the exact required marker format.\n\n"
                "Draft:\n"
                f"{raw_output.strip()}"
            )
        else:
            system_prompt = VERIFIER_REPAIR_SYSTEM_PROMPT
            prompt_text = (
                "Rewrite this verifier draft into the exact required marker format.\n\n"
                "Draft:\n"
                f"{raw_output.strip()}"
            )
        return self._invoke(role, system_prompt, prompt_text, tools_enabled=False)

    def _invoke(self, role: str, system_prompt: str, prompt_text: str, *, tools_enabled: bool) -> RoleCallResult:
        events: list[EngineEvent] = []
        started_at = perf_counter()
        previous_tools = self.runtime.tools_enabled
        self.runtime.tools_enabled = bool(tools_enabled)

        def listener(event: EngineEvent) -> None:
            events.append(event)

        try:
            result = self.runtime.stream_turn(
                prompt=prompt_text,
                history=[],
                on_event=listener,
                system_prompt_override=system_prompt,
            )
        finally:
            self.runtime.tools_enabled = previous_tools
        tool_events = [
            event.to_dict()
            for event in events
            if event.type in {"tool_request", "tool_result"}
        ]
        latency_ms = int((perf_counter() - started_at) * 1000)
        return RoleCallResult(raw_output=result.assistant, tool_events=tool_events, latency_ms=latency_ms)


def parse_solver_output(raw_output: str) -> ParsedOutput:
    if _looks_identity_heavy(raw_output):
        return ParsedOutput(False, None, "solver output drifted into identity or dialogue content")
    normalized = (raw_output or "").strip()
    match = SOLVER_OUTPUT_RE.match(normalized)
    if not match:
        relaxed_draft = _parse_relaxed_solver_output(normalized)
        if relaxed_draft is not None:
            return ParsedOutput(True, relaxed_draft)
        return ParsedOutput(False, None, "solver output missing required markers")
    final_answer = match.group("final").strip()
    confidence = _normalize_confidence(match.group("confidence"))
    solution = match.group("solution").strip()
    if not final_answer or not solution:
        return ParsedOutput(False, None, "solver output had empty required sections")
    if confidence is None:
        return ParsedOutput(False, None, "solver confidence was invalid")
    draft = SolverDraft(
        final_answer=final_answer,
        confidence=confidence,  # type: ignore[arg-type]
        solution=solution,
        raw_output=raw_output.strip(),
    )
    return ParsedOutput(True, draft)


def parse_verifier_output(raw_output: str) -> ParsedOutput:
    if _looks_identity_heavy(raw_output):
        return ParsedOutput(False, None, "verifier output drifted into identity or dialogue content")
    normalized = (raw_output or "").strip()
    match = VERIFIER_OUTPUT_RE.match(normalized)
    if not match:
        relaxed_report = _parse_relaxed_verifier_output(normalized)
        if relaxed_report is not None:
            return ParsedOutput(True, relaxed_report)
        report = VerifierReport(
            verdict="insufficient",
            final_answer_check="unclear",
            issues=["verifier output missing required markers"],
            raw_output=normalized,
        )
        return ParsedOutput(False, report, "verifier output missing required markers")
    verdict = match.group("verdict").strip().lower()
    final_answer_check = match.group("check").strip().lower()
    issues = _parse_issue_lines(match.group("issues"))
    report = VerifierReport(
        verdict=verdict,  # type: ignore[arg-type]
        final_answer_check=final_answer_check,
        issues=issues,
        raw_output=raw_output.strip(),
    )
    return ParsedOutput(True, report)


def execute_math_loop(
    problem: MathProblem,
    invoke_role: RoleInvoker,
    *,
    max_rounds: int = 2,
    repair_role: RepairInvoker | None = None,
    on_step: StepObserver | None = None,
) -> MathLoopResult:
    steps: list[MathLoopStep] = []
    solver_draft: SolverDraft | None = None
    verifier_report: VerifierReport | None = None

    for round_index in range(1, max(1, int(max_rounds)) + 1):
        solver_prompt = build_solver_prompt(
            problem.problem_text,
            revision_index=round_index - 1,
            prior_draft=solver_draft,
            verifier_report=verifier_report,
        )
        solver_call = invoke_role("solver", SOLVER_SYSTEM_PROMPT, solver_prompt)
        parsed_solver = parse_solver_output(solver_call.raw_output)
        solver_step = MathLoopStep(
            role="solver",
            round_index=round_index,
            prompt_text=solver_prompt,
            raw_output=solver_call.raw_output,
            parsed_output=_parsed_payload_dict(parsed_solver),
            tool_events=solver_call.tool_events,
            latency_ms=solver_call.latency_ms,
            status="ok" if parsed_solver.ok else "failed",
        )
        steps.append(solver_step)
        if on_step is not None:
            on_step(solver_step)
        if not parsed_solver.ok and repair_role is not None:
            repair_call = repair_role("solver", solver_call.raw_output)
            parsed_solver = parse_solver_output(repair_call.raw_output)
            repair_solver_step = MathLoopStep(
                role="solver",
                round_index=round_index,
                prompt_text="repair_solver_output",
                raw_output=repair_call.raw_output,
                parsed_output=_parsed_payload_dict(parsed_solver),
                tool_events=repair_call.tool_events,
                latency_ms=repair_call.latency_ms,
                status="repair_ok" if parsed_solver.ok else "repair_failed",
            )
            steps.append(repair_solver_step)
            if on_step is not None:
                on_step(repair_solver_step)
        if not parsed_solver.ok or not isinstance(parsed_solver.payload, SolverDraft):
            return MathLoopResult(
                final_answer="",
                verified=False,
                status="failed",
                rounds_used=round_index,
                trace=MathLoopTrace(problem_text=problem.problem_text, steps=steps, stopped_reason=parsed_solver.error),
                error_message=parsed_solver.error,
            )
        solver_draft = parsed_solver.payload

        verifier_prompt = build_verifier_prompt(problem.problem_text, solver_draft)
        verifier_call = invoke_role("verifier", VERIFIER_SYSTEM_PROMPT, verifier_prompt)
        parsed_verifier = parse_verifier_output(verifier_call.raw_output)
        verifier_step = MathLoopStep(
            role="verifier",
            round_index=round_index,
            prompt_text=verifier_prompt,
            raw_output=verifier_call.raw_output,
            parsed_output=_parsed_payload_dict(parsed_verifier),
            tool_events=verifier_call.tool_events,
            latency_ms=verifier_call.latency_ms,
            status="ok" if parsed_verifier.ok else "failed",
        )
        steps.append(verifier_step)
        if on_step is not None:
            on_step(verifier_step)
        if not parsed_verifier.ok and repair_role is not None:
            repair_call = repair_role("verifier", verifier_call.raw_output)
            parsed_verifier = parse_verifier_output(repair_call.raw_output)
            repair_verifier_step = MathLoopStep(
                role="verifier",
                round_index=round_index,
                prompt_text="repair_verifier_output",
                raw_output=repair_call.raw_output,
                parsed_output=_parsed_payload_dict(parsed_verifier),
                tool_events=repair_call.tool_events,
                latency_ms=repair_call.latency_ms,
                status="repair_ok" if parsed_verifier.ok else "repair_failed",
            )
            steps.append(repair_verifier_step)
            if on_step is not None:
                on_step(repair_verifier_step)
        if not isinstance(parsed_verifier.payload, VerifierReport):
            return MathLoopResult(
                final_answer=solver_draft.final_answer,
                verified=False,
                status="failed",
                rounds_used=round_index,
                trace=MathLoopTrace(problem_text=problem.problem_text, steps=steps, stopped_reason=parsed_verifier.error),
                solver_draft=solver_draft,
                error_message=parsed_verifier.error,
            )
        verifier_report = parsed_verifier.payload
        if not parsed_verifier.ok:
            return MathLoopResult(
                final_answer=solver_draft.final_answer,
                verified=False,
                status="failed",
                rounds_used=round_index,
                trace=MathLoopTrace(problem_text=problem.problem_text, steps=steps, stopped_reason=parsed_verifier.error),
                solver_draft=solver_draft,
                verifier_report=verifier_report,
                error_message=parsed_verifier.error,
            )

        if verifier_report.verdict == "pass":
            return MathLoopResult(
                final_answer=solver_draft.final_answer,
                verified=True,
                status="solved",
                rounds_used=round_index,
                trace=MathLoopTrace(problem_text=problem.problem_text, steps=steps, stopped_reason="verifier_pass"),
                solver_draft=solver_draft,
                verifier_report=verifier_report,
            )

        if verifier_report.verdict == "insufficient":
            return MathLoopResult(
                final_answer=solver_draft.final_answer,
                verified=False,
                status="failed",
                rounds_used=round_index,
                trace=MathLoopTrace(problem_text=problem.problem_text, steps=steps, stopped_reason="verifier_insufficient"),
                solver_draft=solver_draft,
                verifier_report=verifier_report,
                error_message="verifier returned insufficient",
            )

        if round_index >= max(1, int(max_rounds)):
            return MathLoopResult(
                final_answer=solver_draft.final_answer,
                verified=False,
                status="unverified",
                rounds_used=round_index,
                trace=MathLoopTrace(problem_text=problem.problem_text, steps=steps, stopped_reason="max_rounds_reached"),
                solver_draft=solver_draft,
                verifier_report=verifier_report,
            )

    return MathLoopResult(
        final_answer=solver_draft.final_answer if solver_draft is not None else "",
        verified=False,
        status="failed",
        rounds_used=max(1, int(max_rounds)),
        trace=MathLoopTrace(problem_text=problem.problem_text, steps=steps, stopped_reason="loop_exhausted"),
        solver_draft=solver_draft,
        verifier_report=verifier_report,
        error_message="loop exhausted unexpectedly",
    )


def run_math_loop(
    problem_text: str,
    *,
    model_dir: Path | str | None = None,
    max_rounds: int = 2,
    tools_enabled: bool = True,
    on_step: StepObserver | None = None,
) -> MathLoopResult:
    runner = MathLoopRunner(model_dir=model_dir, tools_enabled=tools_enabled)
    problem = MathProblem(problem_text=(problem_text or "").strip())
    return execute_math_loop(
        problem,
        runner.invoke,
        max_rounds=max_rounds,
        repair_role=runner.repair,
        on_step=on_step,
    )


def run_single_pass_solver(
    problem_text: str,
    *,
    model_dir: Path | str | None = None,
    tools_enabled: bool = True,
    runtime: AthenaRuntime | None = None,
) -> tuple[SolverDraft | None, MathLoopStep]:
    runner = MathLoopRunner(model_dir=model_dir, tools_enabled=tools_enabled, runtime=runtime)
    prompt_text = build_solver_prompt(problem_text, revision_index=0)
    call = runner.invoke("solver", SOLVER_SYSTEM_PROMPT, prompt_text)
    parsed = parse_solver_output(call.raw_output)
    if not parsed.ok:
        repair_call = runner.repair("solver", call.raw_output)
        parsed = parse_solver_output(repair_call.raw_output)
        if parsed.ok:
            step = MathLoopStep(
                role="solver",
                round_index=1,
                prompt_text="repair_solver_output",
                raw_output=repair_call.raw_output,
                parsed_output=_parsed_payload_dict(parsed),
                tool_events=repair_call.tool_events,
                latency_ms=repair_call.latency_ms,
                status="repair_ok",
            )
            payload = parsed.payload if isinstance(parsed.payload, SolverDraft) else None
            return payload, step
    step = MathLoopStep(
        role="solver",
        round_index=1,
        prompt_text=prompt_text,
        raw_output=call.raw_output,
        parsed_output=_parsed_payload_dict(parsed),
        tool_events=call.tool_events,
        latency_ms=call.latency_ms,
        status="ok" if parsed.ok else "failed",
    )
    payload = parsed.payload if isinstance(parsed.payload, SolverDraft) else None
    return payload, step


def _parse_issue_lines(body: str) -> list[str]:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return ["none"]
    issues: list[str] = []
    for line in lines:
        if line.startswith("-"):
            cleaned = line[1:].strip()
        else:
            cleaned = line.strip()
        if cleaned:
            issues.append(cleaned)
    return issues or ["none"]


def _parse_relaxed_solver_output(raw_output: str) -> SolverDraft | None:
    text = raw_output.strip()
    if not text:
        return None

    answer_match = re.search(r"(?im)^\s*(?:final answer|answer)\s*:\s*(.+?)\s*$", text)
    final_answer = answer_match.group(1).strip() if answer_match else ""
    if not final_answer:
        tail_match = re.search(r"(?:=|is)\s*(.+?)(?:[.!]\s*)?$", text, re.IGNORECASE | re.DOTALL)
        if tail_match:
            candidate = " ".join(tail_match.group(1).strip().split())
            if candidate and len(candidate) <= 64:
                final_answer = candidate
    if not final_answer:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            last_line = lines[-1]
            if len(last_line) <= 64 and _looks_answer_like(last_line):
                final_answer = last_line
    if not final_answer:
        return None
    return SolverDraft(
        final_answer=final_answer,
        confidence="medium",
        solution=text,
        raw_output=raw_output,
    )


def _parse_relaxed_verifier_output(raw_output: str) -> VerifierReport | None:
    stripped = raw_output.strip()
    probe = stripped.lower()
    if not probe:
        return None
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    line_map: dict[str, str] = {}
    for line in stripped.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_norm = key.strip().lower()
        value_norm = value.strip()
        if key_norm and value_norm:
            line_map[key_norm] = value_norm
    if "verdict" in line_map:
        verdict = _normalize_verdict(line_map["verdict"])
        answer_check = _normalize_answer_check(line_map.get("final_answer_check", ""))
        if verdict is not None:
            if answer_check is None:
                answer_check = {
                    "pass": "correct",
                    "revise": "incorrect",
                    "insufficient": "unclear",
                }[verdict]
            issues_text = line_map.get("issues", "")
            issues = ["none"] if not issues_text or issues_text.lower() == "none" else _parse_issue_lines(issues_text)
            return VerifierReport(
                verdict=verdict,  # type: ignore[arg-type]
                final_answer_check=answer_check,
                issues=issues,
                raw_output=raw_output,
            )
    if lines:
        last_line = lines[-1].strip().lower().rstrip(".")
        if last_line in {"pass", "revise", "insufficient"}:
            verdict = last_line
            check = {
                "pass": "correct",
                "revise": "incorrect",
                "insufficient": "unclear",
            }[verdict]
            issues = {
                "pass": ["none"],
                "revise": ["verifier requested revision but did not specify issues"],
                "insufficient": ["verifier did not provide enough detail"],
            }[verdict]
            return VerifierReport(
                verdict=verdict,  # type: ignore[arg-type]
                final_answer_check=check,
                issues=issues,
                raw_output=raw_output,
            )
    heuristic_verdict = _infer_verifier_verdict_from_text(probe)
    if heuristic_verdict is not None:
        verdict, answer_check, issues = heuristic_verdict
        return VerifierReport(
            verdict=verdict,  # type: ignore[arg-type]
            final_answer_check=answer_check,
            issues=issues,
            raw_output=raw_output,
        )
    if probe in {"pass", "revise", "insufficient"}:
        check = {
            "pass": "correct",
            "revise": "incorrect",
            "insufficient": "unclear",
        }[probe]
        issues = {
            "pass": ["none"],
            "revise": ["verifier requested revision but did not specify issues"],
            "insufficient": ["verifier did not provide enough detail"],
        }[probe]
        return VerifierReport(
            verdict=probe,  # type: ignore[arg-type]
            final_answer_check=check,
            issues=issues,
            raw_output=raw_output,
        )
    return None


def _normalize_verdict(value: str) -> str | None:
    probe = value.strip().lower()
    if probe in {"pass", "revise", "insufficient"}:
        return probe
    return None


def _normalize_confidence(value: str) -> str | None:
    probe = value.strip().lower()
    mapping = {
        "high": "high",
        "medium": "medium",
        "med": "medium",
        "low": "low",
        "1.0": "high",
        "0.9": "high",
        "0.8": "high",
        "0.7": "medium",
        "0.6": "medium",
        "0.5": "medium",
        "0.4": "medium",
        "0.3": "low",
        "0.2": "low",
        "0.1": "low",
        "0": "low",
    }
    if probe in mapping:
        return mapping[probe]
    numeric_match = re.fullmatch(r"\d+(?:\.\d+)?", probe)
    if numeric_match:
        try:
            score = float(probe)
        except ValueError:
            return None
        if score >= 0.8:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"
    return None


def _normalize_answer_check(value: str) -> str | None:
    probe = value.strip().lower()
    mapping = {
        "correct": "correct",
        "pass": "correct",
        "incorrect": "incorrect",
        "wrong": "incorrect",
        "revise": "incorrect",
        "unclear": "unclear",
        "insufficient": "unclear",
    }
    return mapping.get(probe)


def _infer_verifier_verdict_from_text(probe: str) -> tuple[str, str, list[str]] | None:
    positive_markers = (
        "answer is correct",
        "reasoning is sound",
        "no issues",
        "no concrete flaw",
        "the draft is clear",
        "the final answer is correct",
        "the provided solution is correct",
        "logic is sound",
        "checks out",
    )
    negative_markers = (
        "critical error",
        "arithmetic error",
        "concrete flaw",
        "final answer is incorrect",
        "reasoning is incorrect",
        "must revise",
    )
    unclear_markers = (
        "unable to evaluate",
        "too malformed",
        "insufficient",
        "unclear",
    )
    if any(marker in probe for marker in positive_markers):
        return ("pass", "correct", ["none"])
    if any(marker in probe for marker in negative_markers):
        return ("revise", "incorrect", ["verifier described a concrete issue outside the strict marker format"])
    if any(marker in probe for marker in unclear_markers):
        return ("insufficient", "unclear", ["verifier could not evaluate the draft"])
    return None


def _looks_answer_like(text: str) -> bool:
    probe = text.strip()
    if not probe:
        return False
    if re.search(r"\d", probe):
        return True
    lowered = probe.lower()
    symbolic_markers = ("=", "/", "\\sqrt", "sqrt", "\\frac", "pi", "∞", "^", "(", ")", "[", "]")
    if any(marker in lowered for marker in symbolic_markers):
        return True
    if re.fullmatch(r"[a-zA-Z]", probe):
        return True
    return False


def _looks_identity_heavy(raw_output: str) -> bool:
    text = (raw_output or "").strip()
    if not text:
        return False
    probe = text[:400]
    return bool(IDENTITY_DRIFT_RE.search(probe))


def _parsed_payload_dict(parsed: ParsedOutput) -> dict[str, Any]:
    payload = parsed.payload
    if hasattr(payload, "to_dict"):
        data = payload.to_dict()  # type: ignore[assignment]
    elif payload is None:
        data = {}
    else:
        data = {"value": payload}
    if parsed.error:
        data = dict(data)
        data["parse_error"] = parsed.error
    return data
