from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from exclusive.desktop_engine import session as exclusive_session


class PrivateRuntimeContractTests(unittest.TestCase):
    def test_runtime_backend_aliases_normalize_to_vllm(self) -> None:
        for raw in ("vllm", "vllm_openai", "openai_compat"):
            with patch.dict(os.environ, {"ATHENA_RUNTIME_BACKEND": raw}, clear=False):
                self.assertEqual(exclusive_session._runtime_backend_name(), "vllm_openai")

    def test_unloaded_private_snapshot_reflects_vllm_runtime(self) -> None:
        model_dir = Path(__file__).resolve().parents[2] / "exclusive" / "AthenaV1"
        with patch.dict(
            os.environ,
            {
                "ATHENA_RUNTIME_BACKEND": "vllm_openai",
                "ATHENA_PRIVATE_MODE": "1",
                "ATHENA_RUNTIME_SCOPE": "private",
                "ATHENA_VLLM_BASE_URL": "http://127.0.0.1:8002/v1",
                "ATHENA_VLLM_MODEL": "AthenaV1",
            },
            clear=False,
        ):
            worker = exclusive_session.ChatWorker(model_dir=model_dir, tools_enabled=False, load_model=False)
            snapshot = worker.runtime_snapshot()

        self.assertEqual(snapshot["runtime_backend"], "vllm_openai")
        self.assertEqual(snapshot["runtime_scope"], "private")
        self.assertEqual(snapshot["runtime_backend_label"], "vLLM OpenAI-compatible")
        self.assertEqual(snapshot["model_dir"], "http://127.0.0.1:8002/v1")
        self.assertEqual(snapshot["model_label"], "AthenaV1")
        self.assertFalse(snapshot["model_loaded"])


if __name__ == "__main__":
    unittest.main()

