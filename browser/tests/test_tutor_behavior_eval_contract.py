from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("ATHENA_WEB_LOAD_MODEL", "0")

from browser import tutor_behavior_eval


class TutorBehaviorEvalContractTests(unittest.TestCase):
    def test_release_suite_has_required_scope_and_dimensions(self) -> None:
        self.assertGreaterEqual(len(tutor_behavior_eval.PROBES), 24)
        keys = {probe.key for probe in tutor_behavior_eval.PROBES}
        required = {
            "greeting",
            "broad_math_help",
            "study_start",
            "direct_explanation",
            "guided_hint",
            "full_solution",
            "correct_work",
            "incorrect_work",
            "contradictory_verdict_controller",
            "misconception_diagnosis",
            "educator_opener",
            "educator_exit_ticket",
            "educator_worksheet",
            "educator_answer_key",
            "educator_rubric",
            "educator_differentiation",
            "attached_image_route",
            "unreadable_image",
            "returning_continuation",
            "memory_conflict",
            "memory_prompt_injection",
            "academic_integrity",
            "high_stakes_safety",
            "exact_course_date",
        }
        self.assertTrue(required.issubset(keys), sorted(required - keys))
        self.assertEqual(
            tutor_behavior_eval.DIMENSIONS,
            ("correctness", "initiative", "pedagogical_value", "role_fit", "mechanical_compliance"),
        )

    def test_every_critical_gate_has_probes_and_requires_perfect_pass_rate(self) -> None:
        represented = {
            gate
            for probe in tutor_behavior_eval.PROBES
            for gate in probe.critical_gates
        }
        self.assertEqual(represented, set(tutor_behavior_eval.CRITICAL_GATES))
        attempts = []
        for probe in tutor_behavior_eval.PROBES:
            evaluation = {
                "passed": True,
                "dimension_scores": {name: 2 for name in tutor_behavior_eval.DIMENSIONS},
            }
            attempts.append(
                {
                    "probe_key": probe.key,
                    "stage": probe.stage,
                    "raw_model_evaluation": evaluation,
                    "controller_evaluation": evaluation,
                }
            )
        summary = tutor_behavior_eval._aggregate(
            tutor_behavior_eval.PROBES,
            attempts,
            minimum_pass_rate=0.90,
        )
        self.assertTrue(summary["release_gate_passed"])
        self.assertTrue(all(gate["required_pass_rate"] == 1.0 for gate in summary["critical_gates"].values()))

        critical_key = next(probe.key for probe in tutor_behavior_eval.PROBES if probe.critical_gates)
        for row in attempts:
            if row["probe_key"] == critical_key:
                row["controller_evaluation"] = {
                    "passed": False,
                    "dimension_scores": {name: 1 for name in tutor_behavior_eval.DIMENSIONS},
                }
                break
        failed = tutor_behavior_eval._aggregate(
            tutor_behavior_eval.PROBES,
            attempts,
            minimum_pass_rate=0.90,
        )
        self.assertFalse(failed["release_gate_passed"])

    def test_contradictory_verdict_is_controller_rescue_not_regression(self) -> None:
        probe = next(
            item for item in tutor_behavior_eval.PROBES if item.key == "contradictory_verdict_controller"
        )
        route = tutor_behavior_eval.portal_server._extract_turn_context(probe.prompt)
        raw = tutor_behavior_eval._evaluate_probe(probe, probe.synthetic_raw, route)
        controlled_text = tutor_behavior_eval.portal_server._enforce_public_output_contract(
            probe.prompt,
            probe.synthetic_raw,
        )
        controlled = tutor_behavior_eval._evaluate_probe(probe, controlled_text, route)
        self.assertFalse(raw["passed"])
        self.assertTrue(controlled["passed"])
        self.assertIn("Verdict: Incorrect", controlled_text)

    def test_output_schema_does_not_serialize_api_key(self) -> None:
        source = Path(tutor_behavior_eval.__file__).read_text(encoding="utf-8")
        self.assertIn('"base_url": _redacted_base_url(args.base_url)', source)
        self.assertNotIn('"api_key": args.api_key', source)
        self.assertEqual(tutor_behavior_eval.EVAL_SCHEMA, "neohmlabs.athena.tutor_behavior_eval.v2")

    def test_run_attempt_persists_raw_and_controller_outputs(self) -> None:
        probe = next(item for item in tutor_behavior_eval.PROBES if item.synthetic_raw)
        args = argparse.Namespace(
            base_url="http://127.0.0.1:1/v1",
            api_key="not-serialized",
            model="Qwen3.5-4B",
            max_tokens=96,
            timeout=5.0,
            temperature=0.0,
        )
        attempt = tutor_behavior_eval._run_attempt(probe, args, 1)
        serialized = json.dumps(attempt)
        self.assertIn("raw_model_response", attempt)
        self.assertIn("controller_response", attempt)
        self.assertIn("raw_model_evaluation", attempt)
        self.assertIn("controller_evaluation", attempt)
        self.assertNotIn("not-serialized", serialized)

    def test_question_budget_distinguishes_intake_from_teaching_checks(self) -> None:
        teaching = "Why does the leaf need sunlight? What changes if the light is removed?"
        intake = "What subject are you studying? Which grade level are you in?"
        self.assertEqual(tutor_behavior_eval._intake_question_count(teaching), 0)
        self.assertEqual(tutor_behavior_eval._intake_question_count(intake), 2)

    def test_explain_validator_accepts_mechanism_example_and_transfer(self) -> None:
        probe = next(item for item in tutor_behavior_eval.PROBES if item.key == "direct_explanation")
        route = tutor_behavior_eval.portal_server._extract_turn_context(probe.prompt)
        strong = (
            "Photosynthesis is a process plants power using sunlight. "
            "For example, a sunflower leaf takes in water and carbon dioxide and rearranges them into sugar. "
            "Transfer cue: which part of this example would change if the leaf received no light?"
        )
        weak = (
            "Photosynthesis is a process plants power using sunlight. "
            "For example, a sunflower leaf takes in water and carbon dioxide and rearranges them into sugar."
        )
        strong_result = tutor_behavior_eval._validator_result("explanation_transfer", probe, strong, route)
        weak_result = tutor_behavior_eval._validator_result("explanation_transfer", probe, weak, route)
        self.assertTrue(strong_result[0])
        self.assertFalse(weak_result[0])


if __name__ == "__main__":
    unittest.main()
