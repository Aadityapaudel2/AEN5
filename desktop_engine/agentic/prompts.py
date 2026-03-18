from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desktop_engine.agentic.schemas import SolverDraft, VerifierReport


SOLVER_SYSTEM_PROMPT = dedent(
    """
    You are a rigorous mathematical solver.

    Stay on the given problem only.
    Use the calculator tool whenever exact arithmetic, modular arithmetic, long expressions, or brittle numeric checks are involved.
    Never discuss identity, roleplay, persona, or dialogue mechanics.
    Be concise. Do not restate the full problem. Keep the solution focused on the minimum reasoning needed.

    Output exactly these top-level markers in this order:
    FINAL_ANSWER:
    CONFIDENCE:
    SOLUTION:

    `CONFIDENCE` must be one of: high, medium, low.
    `FINAL_ANSWER` must be concise.
    `SOLUTION` must contain only the reasoning needed to support the answer.
    Prefer at most 8 short lines in `SOLUTION` unless the problem truly requires more.
    """
).strip()


VERIFIER_SYSTEM_PROMPT = dedent(
    """
    You are a rigorous mathematical verifier.

    Check the solver draft against the original problem.
    Use the calculator tool whenever exact arithmetic or symbolic-style checking is brittle.
    Never solve a different problem, never debate identity, and never continue conversational chatter.
    Be concise. Focus on whether the final answer is correct and whether there is a concrete flaw that matters.

    Output exactly these top-level markers in this order:
    VERDICT:
    FINAL_ANSWER_CHECK:
    ISSUES:

    `VERDICT` must be one of: pass, revise, insufficient.
    `FINAL_ANSWER_CHECK` must be one of: correct, incorrect, unclear.
    `ISSUES` must be a short bullet list or `- none`.
    If the draft is acceptable, keep `ISSUES` as `- none`.
    """
).strip()


def build_solver_prompt(
    problem_text: str,
    *,
    revision_index: int,
    prior_draft: "SolverDraft | None" = None,
    verifier_report: "VerifierReport | None" = None,
) -> str:
    parts = [
        "Problem:",
        problem_text.strip(),
        "",
        "Task:",
    ]
    if revision_index <= 0 or prior_draft is None or verifier_report is None:
        parts.append("Produce the strongest candidate solution you can.")
    else:
        parts.extend(
            [
                f"Revise the candidate solution. This is revision round {revision_index}.",
                "",
                "Previous draft final answer:",
                prior_draft.final_answer.strip(),
                "",
                "Previous draft solution:",
                prior_draft.solution.strip(),
                "",
                "Verifier issues to address:",
                "\n".join(f"- {issue}" for issue in verifier_report.issues) if verifier_report.issues else "- none",
            ]
        )
    parts.extend(
        [
            "",
            "Return only the required marker-based output.",
            "Use the calculator tool if exact arithmetic or a brittle check is involved.",
            "Keep the solution concise and avoid re-copying the full problem statement.",
        ]
    )
    return "\n".join(parts).strip()


def build_verifier_prompt(problem_text: str, draft: "SolverDraft") -> str:
    return "\n".join(
        [
            "Problem:",
            problem_text.strip(),
            "",
            "Solver final answer:",
            draft.final_answer.strip(),
            "",
            "Solver confidence:",
            draft.confidence,
            "",
            "Solver solution:",
            draft.solution.strip(),
            "",
            "Task:",
            "Check whether the final answer is correct and whether the reasoning has a concrete flaw that matters.",
            "If the answer and reasoning are good enough, pass.",
            "If a concrete flaw, missing justification, or arithmetic error matters, revise.",
            "If the draft is too malformed to evaluate, mark insufficient.",
            "Return only the required marker-based output.",
            "Keep the verification concise. If the draft is correct, a brief pass is enough.",
        ]
    ).strip()
