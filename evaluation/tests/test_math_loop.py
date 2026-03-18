from __future__ import annotations

import unittest

from desktop_engine.agentic.loop import (
    ParsedOutput,
    RoleCallResult,
    execute_math_loop,
    parse_solver_output,
    parse_verifier_output,
)
from desktop_engine.agentic.eval import _answers_match
from desktop_engine.agentic.schemas import MathProblem, SolverDraft


class _FakeInvoker:
    def __init__(self, results: list[RoleCallResult]) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, role: str, system_prompt: str, prompt_text: str) -> RoleCallResult:
        self.calls.append((role, system_prompt, prompt_text))
        if not self._results:
            raise AssertionError("No fake result left for role invocation.")
        return self._results.pop(0)


class _FakeRepairInvoker:
    def __init__(self, results: list[RoleCallResult]) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, role: str, raw_output: str) -> RoleCallResult:
        self.calls.append((role, raw_output))
        if not self._results:
            raise AssertionError("No fake repair result left for role invocation.")
        return self._results.pop(0)


class MathLoopParserTests(unittest.TestCase):
    def test_parse_solver_output_valid(self) -> None:
        parsed = parse_solver_output(
            "FINAL_ANSWER:\n42\nCONFIDENCE:\nhigh\nSOLUTION:\nWe compute 40 + 2 = 42."
        )
        self.assertTrue(parsed.ok)
        self.assertIsInstance(parsed.payload, SolverDraft)
        self.assertEqual(parsed.payload.final_answer, "42")  # type: ignore[union-attr]

    def test_parse_solver_output_invalid(self) -> None:
        parsed = parse_solver_output("Answer: 42")
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.final_answer, "42")  # type: ignore[union-attr]

    def test_parse_solver_output_numeric_confidence_is_normalized(self) -> None:
        parsed = parse_solver_output(
            "FINAL_ANSWER:\n2\nCONFIDENCE:\n1.0\nSOLUTION:\nBurnside count gives 2."
        )
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.final_answer, "2")  # type: ignore[union-attr]
        self.assertEqual(parsed.payload.confidence, "high")  # type: ignore[union-attr]

    def test_parse_verifier_output_valid(self) -> None:
        parsed = parse_verifier_output(
            "VERDICT:\npass\nFINAL_ANSWER_CHECK:\ncorrect\nISSUES:\n- none"
        )
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.verdict, "pass")  # type: ignore[union-attr]

    def test_parse_verifier_output_invalid_becomes_insufficient(self) -> None:
        parsed = parse_verifier_output("Looks good to me.")
        self.assertFalse(parsed.ok)
        self.assertEqual(parsed.payload.verdict, "insufficient")  # type: ignore[union-attr]

    def test_parse_verifier_output_verdict_only_is_accepted(self) -> None:
        parsed = parse_verifier_output("pass")
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.verdict, "pass")  # type: ignore[union-attr]
        self.assertEqual(parsed.payload.final_answer_check, "correct")  # type: ignore[union-attr]

    def test_parse_verifier_output_allows_math_identity_language(self) -> None:
        parsed = parse_verifier_output(
            "VERDICT:\nrevise\nFINAL_ANSWER_CHECK:\nincorrect\nISSUES:\n- The triple-angle identity was used incorrectly."
        )
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.verdict, "revise")  # type: ignore[union-attr]

    def test_parse_verifier_output_relaxes_synonym_marker_values(self) -> None:
        parsed = parse_verifier_output("VERDICT: pass\nFINAL_ANSWER_CHECK: pass\nISSUES: None")
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.verdict, "pass")  # type: ignore[union-attr]
        self.assertEqual(parsed.payload.final_answer_check, "correct")  # type: ignore[union-attr]

    def test_parse_verifier_output_trailing_pass_is_accepted(self) -> None:
        parsed = parse_verifier_output(
            "The reasoning is sound and the final answer is correct.\n\npass"
        )
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.verdict, "pass")  # type: ignore[union-attr]

    def test_parse_verifier_output_positive_natural_language_is_accepted(self) -> None:
        parsed = parse_verifier_output(
            "The provided solution is correct. The arithmetic checks out and the logic is sound.\n\n003"
        )
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.verdict, "pass")  # type: ignore[union-attr]

    def test_parse_solver_output_answer_sentence_is_accepted(self) -> None:
        parsed = parse_solver_output("The result of 7 + 8 is 15.")
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.payload.final_answer, "15")  # type: ignore[union-attr]


class MathLoopControllerTests(unittest.TestCase):
    def test_solver_passes_on_first_verification(self) -> None:
        invoker = _FakeInvoker(
            [
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n15\nCONFIDENCE:\nhigh\nSOLUTION:\nCompute 7 + 8 = 15.",
                    tool_events=[{"type": "tool_request"}, {"type": "tool_result"}],
                    latency_ms=12,
                ),
                RoleCallResult(
                    raw_output="VERDICT:\npass\nFINAL_ANSWER_CHECK:\ncorrect\nISSUES:\n- none",
                    tool_events=[],
                    latency_ms=9,
                ),
            ]
        )
        result = execute_math_loop(MathProblem(problem_text="What is 7 + 8?"), invoker, max_rounds=2)
        self.assertEqual(result.status, "solved")
        self.assertTrue(result.verified)
        self.assertEqual(result.final_answer, "15")
        self.assertEqual(len(result.trace.steps), 2)
        self.assertEqual(result.trace.steps[0].tool_events[0]["type"], "tool_request")

    def test_solver_revises_once_then_passes(self) -> None:
        invoker = _FakeInvoker(
            [
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n14\nCONFIDENCE:\nmedium\nSOLUTION:\nMistakenly added to 14.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="VERDICT:\nrevise\nFINAL_ANSWER_CHECK:\nincorrect\nISSUES:\n- The final answer should be 15, not 14.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n15\nCONFIDENCE:\nhigh\nSOLUTION:\nCorrecting the sum gives 15.",
                    tool_events=[],
                    latency_ms=6,
                ),
                RoleCallResult(
                    raw_output="VERDICT:\npass\nFINAL_ANSWER_CHECK:\ncorrect\nISSUES:\n- none",
                    tool_events=[],
                    latency_ms=4,
                ),
            ]
        )
        result = execute_math_loop(MathProblem(problem_text="What is 7 + 8?"), invoker, max_rounds=2)
        self.assertEqual(result.status, "solved")
        self.assertEqual(result.rounds_used, 2)
        self.assertEqual(result.final_answer, "15")

    def test_loop_stops_unverified_after_max_rounds(self) -> None:
        invoker = _FakeInvoker(
            [
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n14\nCONFIDENCE:\nlow\nSOLUTION:\nInitial wrong draft.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="VERDICT:\nrevise\nFINAL_ANSWER_CHECK:\nincorrect\nISSUES:\n- Still wrong.",
                    tool_events=[],
                    latency_ms=4,
                ),
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n14\nCONFIDENCE:\nlow\nSOLUTION:\nRevision is still wrong.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="VERDICT:\nrevise\nFINAL_ANSWER_CHECK:\nincorrect\nISSUES:\n- Still wrong.",
                    tool_events=[],
                    latency_ms=4,
                ),
            ]
        )
        result = execute_math_loop(MathProblem(problem_text="What is 7 + 8?"), invoker, max_rounds=2)
        self.assertEqual(result.status, "unverified")
        self.assertFalse(result.verified)
        self.assertEqual(result.final_answer, "14")

    def test_loop_fails_on_malformed_verifier_output(self) -> None:
        invoker = _FakeInvoker(
            [
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n15\nCONFIDENCE:\nhigh\nSOLUTION:\nCompute 7 + 8 = 15.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="I am the verifier and this looks fine.",
                    tool_events=[],
                    latency_ms=4,
                ),
            ]
        )
        result = execute_math_loop(MathProblem(problem_text="What is 7 + 8?"), invoker, max_rounds=2)
        self.assertEqual(result.status, "failed")
        self.assertFalse(result.verified)
        self.assertIn("verifier", result.error_message)

    def test_loop_accepts_verifier_verdict_only_output(self) -> None:
        invoker = _FakeInvoker(
            [
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n15\nCONFIDENCE:\nhigh\nSOLUTION:\nCompute 7 + 8 = 15.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="pass",
                    tool_events=[],
                    latency_ms=4,
                ),
            ]
        )
        result = execute_math_loop(MathProblem(problem_text="What is 7 + 8?"), invoker, max_rounds=2)
        self.assertEqual(result.status, "solved")
        self.assertTrue(result.verified)
        self.assertEqual(result.final_answer, "15")


class MathLoopEvalNormalizationTests(unittest.TestCase):
    def test_answers_match_zero_padded_integer_embedded_in_text(self) -> None:
        self.assertTrue(_answers_match("003", "$N=3$. 003"))

    def test_solver_malformed_output_can_be_repaired(self) -> None:
        invoker = _FakeInvoker(
            [
                RoleCallResult(
                    raw_output="Computation complete.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="VERDICT:\npass\nFINAL_ANSWER_CHECK:\ncorrect\nISSUES:\n- none",
                    tool_events=[],
                    latency_ms=4,
                ),
            ]
        )
        repair = _FakeRepairInvoker(
            [
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n15\nCONFIDENCE:\nmedium\nSOLUTION:\nCompute 7 + 8 = 15.",
                    tool_events=[],
                    latency_ms=3,
                )
            ]
        )
        result = execute_math_loop(
            MathProblem(problem_text="What is 7 + 8?"),
            invoker,
            max_rounds=2,
            repair_role=repair,
        )
        self.assertEqual(result.status, "solved")
        self.assertTrue(result.verified)
        self.assertEqual(result.final_answer, "15")
        self.assertEqual(len(repair.calls), 1)
        self.assertEqual(result.trace.steps[1].status, "repair_ok")

    def test_verifier_malformed_output_can_be_repaired(self) -> None:
        invoker = _FakeInvoker(
            [
                RoleCallResult(
                    raw_output="FINAL_ANSWER:\n15\nCONFIDENCE:\nhigh\nSOLUTION:\nCompute 7 + 8 = 15.",
                    tool_events=[],
                    latency_ms=5,
                ),
                RoleCallResult(
                    raw_output="Looks correct.",
                    tool_events=[],
                    latency_ms=4,
                ),
            ]
        )
        repair = _FakeRepairInvoker(
            [
                RoleCallResult(
                    raw_output="VERDICT:\npass\nFINAL_ANSWER_CHECK:\ncorrect\nISSUES:\n- none",
                    tool_events=[],
                    latency_ms=3,
                )
            ]
        )
        result = execute_math_loop(
            MathProblem(problem_text="What is 7 + 8?"),
            invoker,
            max_rounds=2,
            repair_role=repair,
        )
        self.assertEqual(result.status, "solved")
        self.assertTrue(result.verified)
        self.assertEqual(len(repair.calls), 1)
        self.assertEqual(result.trace.steps[-1].status, "repair_ok")


if __name__ == "__main__":
    unittest.main()
