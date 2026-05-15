from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import athena_paths


class AthenaPathingContractTests(unittest.TestCase):
    def test_launcher_scripts_query_canonical_path_module(self) -> None:
        repo_root = Path(athena_paths.__file__).resolve().parent
        run_vllm = (repo_root / "run_vllm.ps1").read_text(encoding="utf-8")
        run_browser = (repo_root / "browser" / "run_browser.ps1").read_text(encoding="utf-8")
        run_private = (repo_root / "run_ui_private.ps1").read_text(encoding="utf-8")

        self.assertIn("public_vllm_model_dir", run_vllm)
        self.assertIn("public_chat_model_dir", run_vllm)
        self.assertIn("private_vllm_source_model_dir", run_vllm)
        self.assertIn("private_chat_model_dir", run_vllm)
        self.assertIn("public_vllm_model_dir", run_browser)
        self.assertIn("public_chat_model_dir", run_browser)
        self.assertIn("private_vllm_source_model_dir", run_private)

    def test_launcher_scripts_do_not_hardcode_model_directories(self) -> None:
        repo_root = Path(athena_paths.__file__).resolve().parent
        run_vllm = (repo_root / "run_vllm.ps1").read_text(encoding="utf-8")
        run_browser = (repo_root / "browser" / "run_browser.ps1").read_text(encoding="utf-8")
        run_private = (repo_root / "run_ui_private.ps1").read_text(encoding="utf-8")

        disallowed_literals = (
            r"models\Qwen3.5-4B",
            r"models\Qwen3.5-2B",
            r"exclusive\AthenaV1",
            r"models\tuned\AthenaV1",
        )
        for literal in disallowed_literals:
            self.assertNotIn(literal, run_vllm)
            self.assertNotIn(literal, run_browser)
            self.assertNotIn(literal, run_private)

    def test_public_getter_prefers_public_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp).resolve()
            with patch.dict(os.environ, {"ATHENA_PUBLIC_CHAT_MODEL_DIR": str(expected)}, clear=False):
                self.assertEqual(athena_paths.get_public_chat_model_dir(), expected)

    def test_private_getter_prefers_private_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp).resolve()
            with patch.dict(os.environ, {"ATHENA_PRIVATE_CHAT_MODEL_DIR": str(expected)}, clear=False):
                self.assertEqual(athena_paths.get_private_chat_model_dir(), expected)

    def test_private_base_multimodal_getter_prefers_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp).resolve()
            with patch.dict(os.environ, {"ATHENA_PRIVATE_BASE_MULTIMODAL_MODEL_DIR": str(expected)}, clear=False):
                self.assertEqual(athena_paths.get_private_base_multimodal_model_dir(), expected)

    def test_default_getter_switches_with_private_scope(self) -> None:
        with tempfile.TemporaryDirectory() as public_tmp, tempfile.TemporaryDirectory() as private_tmp:
            public_expected = Path(public_tmp).resolve()
            private_expected = Path(private_tmp).resolve()
            with patch.dict(
                os.environ,
                {
                    "ATHENA_PUBLIC_CHAT_MODEL_DIR": str(public_expected),
                    "ATHENA_PRIVATE_CHAT_MODEL_DIR": str(private_expected),
                    "ATHENA_PRIVATE_MODE": "1",
                    "ATHENA_RUNTIME_SCOPE": "private",
                },
                clear=False,
            ):
                self.assertEqual(athena_paths.get_default_chat_model_dir(), private_expected)
            with patch.dict(
                os.environ,
                {
                    "ATHENA_PUBLIC_CHAT_MODEL_DIR": str(public_expected),
                    "ATHENA_PRIVATE_CHAT_MODEL_DIR": str(private_expected),
                    "ATHENA_PRIVATE_MODE": "0",
                    "ATHENA_RUNTIME_SCOPE": "public",
                },
                clear=False,
            ):
                self.assertEqual(athena_paths.get_default_chat_model_dir(), public_expected)

    def test_cli_query_returns_canonical_public_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp).resolve()
            env = os.environ.copy()
            env["ATHENA_PUBLIC_CHAT_MODEL_DIR"] = str(expected)
            output = subprocess.check_output(
                [sys.executable, str(Path(athena_paths.__file__)), "--query", "public_chat_model_dir"],
                env=env,
                text=True,
            ).strip()
            self.assertEqual(Path(output), expected)


if __name__ == "__main__":
    unittest.main()
