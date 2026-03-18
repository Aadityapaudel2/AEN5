from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop_engine.agentic.kaggle_entry import (
    extract_submission_answer,
    load_submission_cases,
    normalize_submission_answer,
)


class KaggleEntryFormattingTests(unittest.TestCase):
    def test_extract_submission_answer_prefers_answer_line(self) -> None:
        value = extract_submission_answer("Step 1\nAnswer: 193")
        self.assertEqual(value, "193")

    def test_normalize_submission_answer_aimo3_defaults_to_plain_integer(self) -> None:
        value = normalize_submission_answer("Answer: 9")
        self.assertEqual(value, "9")

    def test_normalize_submission_answer_zero_pads_mod_1000(self) -> None:
        value = normalize_submission_answer("Answer: 9", modulus=1000, width=3)
        self.assertEqual(value, "009")

    def test_normalize_submission_answer_reduces_aimo3_modulus(self) -> None:
        value = normalize_submission_answer("FINAL_ANSWER: 100003")
        self.assertEqual(value, "3")

    def test_normalize_submission_answer_reduces_modulus_with_padding_when_requested(self) -> None:
        value = normalize_submission_answer("FINAL_ANSWER: 1003", modulus=1000, width=3)
        self.assertEqual(value, "003")

    def test_normalize_submission_answer_uses_fallback(self) -> None:
        value = normalize_submission_answer("")
        self.assertEqual(value, "0")


class KaggleEntryCaseLoadingTests(unittest.TestCase):
    def test_load_submission_cases_respects_sample_submission_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            input_csv = base / "test.csv"
            sample_csv = base / "sample_submission.csv"

            with input_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "problem"])
                writer.writeheader()
                writer.writerow({"id": "b", "problem": "Problem B"})
                writer.writerow({"id": "a", "problem": "Problem A"})

            with sample_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "answer"])
                writer.writeheader()
                writer.writerow({"id": "a", "answer": ""})
                writer.writerow({"id": "b", "answer": ""})

            cases, id_column, answer_column = load_submission_cases(input_csv, sample_submission_path=sample_csv)
            self.assertEqual(id_column, "id")
            self.assertEqual(answer_column, "answer")
            self.assertEqual([case.row_id for case in cases], ["a", "b"])


class KaggleEntryBuildTests(unittest.TestCase):
    def test_build_kaggle_submission_writes_aimo3_answers_by_default(self) -> None:
        from desktop_engine.agentic.kaggle_entry import build_kaggle_submission

        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            input_csv = base / "test.csv"
            output_csv = base / "submission.csv"

            with input_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "problem"])
                writer.writeheader()
                writer.writerow({"id": "row-1", "problem": "Compute 2+7."})

            with patch("desktop_engine.agentic.kaggle_entry.AthenaRuntime", return_value=SimpleNamespace(tools_enabled=True)), \
                 patch("desktop_engine.agentic.kaggle_entry.MathLoopRunner", side_effect=lambda runtime, tools_enabled: SimpleNamespace(runtime=runtime)), \
                 patch("desktop_engine.agentic.kaggle_entry.solve_submission_case", return_value=("Answer: 9", False, "baseline", 1)):
                summary = build_kaggle_submission(
                    input_path=input_csv,
                    output_path=output_csv,
                    strategy="baseline",
                )

            self.assertTrue(summary["ok"])
            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"id": "row-1", "answer": "9"}])


if __name__ == "__main__":
    unittest.main()