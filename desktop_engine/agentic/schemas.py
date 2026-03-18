from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


RoleName = Literal["solver", "verifier"]
LoopStatus = Literal["solved", "unverified", "failed"]
VerifierVerdict = Literal["pass", "revise", "insufficient"]
ConfidenceLevel = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class MathProblem:
    problem_text: str
    source_id: str = ""
    gold_answer: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SolverDraft:
    final_answer: str
    confidence: ConfidenceLevel
    solution: str
    raw_output: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerifierReport:
    verdict: VerifierVerdict
    final_answer_check: str
    issues: list[str]
    raw_output: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MathLoopStep:
    role: RoleName
    round_index: int
    prompt_text: str
    raw_output: str
    parsed_output: dict[str, Any]
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MathLoopTrace:
    problem_text: str
    steps: list[MathLoopStep] = field(default_factory=list)
    stopped_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_text": self.problem_text,
            "stopped_reason": self.stopped_reason,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class MathLoopResult:
    final_answer: str
    verified: bool
    status: LoopStatus
    rounds_used: int
    trace: MathLoopTrace
    solver_draft: SolverDraft | None = None
    verifier_report: VerifierReport | None = None
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_answer": self.final_answer,
            "verified": self.verified,
            "status": self.status,
            "rounds_used": self.rounds_used,
            "trace": self.trace.to_dict(),
            "solver_draft": self.solver_draft.to_dict() if self.solver_draft is not None else None,
            "verifier_report": self.verifier_report.to_dict() if self.verifier_report is not None else None,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class EvalCaseResult:
    source_id: str
    gold_answer: str
    baseline_answer: str
    loop_answer: str
    baseline_correct: bool
    loop_correct: bool
    verified: bool
    status: LoopStatus
    rounds_used: int
    false_verifier_critique: bool
    baseline_latency_ms: int
    loop_latency_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvalSummary:
    manifest_path: str
    total_cases: int
    exact_accuracy_baseline: float
    exact_accuracy_loop: float
    arithmetic_error_rate_baseline: float
    arithmetic_error_rate_loop: float
    false_verifier_critique_rate: float
    average_rounds_used: float
    average_latency_ms_baseline: float
    average_latency_ms_loop: float
    cases: list[EvalCaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": self.manifest_path,
            "total_cases": self.total_cases,
            "exact_accuracy_baseline": self.exact_accuracy_baseline,
            "exact_accuracy_loop": self.exact_accuracy_loop,
            "arithmetic_error_rate_baseline": self.arithmetic_error_rate_baseline,
            "arithmetic_error_rate_loop": self.arithmetic_error_rate_loop,
            "false_verifier_critique_rate": self.false_verifier_critique_rate,
            "average_rounds_used": self.average_rounds_used,
            "average_latency_ms_baseline": self.average_latency_ms_baseline,
            "average_latency_ms_loop": self.average_latency_ms_loop,
            "cases": [case.to_dict() for case in self.cases],
        }
