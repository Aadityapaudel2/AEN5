from __future__ import annotations

from dataclasses import replace
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ATHENA_WEB_LOAD_MODEL", "0")

from browser import portal_server


class PublicRuntimeContractTests(unittest.TestCase):
    def test_public_vllm_only_flag_respects_env(self) -> None:
        with patch.dict(os.environ, {"ATHENA_PUBLIC_VLLM_ONLY": "1"}, clear=False):
            self.assertTrue(portal_server._public_vllm_only())
        with patch.dict(os.environ, {"ATHENA_PUBLIC_VLLM_ONLY": "0"}, clear=False):
            self.assertFalse(portal_server._public_vllm_only())

    def test_runtime_ready_requires_vllm_backend_when_public_flag_enabled(self) -> None:
        snapshot = {"runtime_backend": "transformers", "model_loaded": True}
        with patch.dict(os.environ, {"ATHENA_PUBLIC_VLLM_ONLY": "1"}, clear=False):
            self.assertFalse(portal_server._runtime_ready(snapshot))

    def test_runtime_ready_accepts_vllm_backend_when_model_loaded(self) -> None:
        snapshot = {"runtime_backend": "vllm_openai", "model_loaded": True}
        with patch.dict(os.environ, {"ATHENA_PUBLIC_VLLM_ONLY": "1"}, clear=False):
            self.assertTrue(portal_server._runtime_ready(snapshot))

    def test_runtime_ready_allows_smoke_mode_without_loaded_model(self) -> None:
        snapshot = {"runtime_backend": "vllm_openai", "model_loaded": False}
        with patch.object(portal_server, "cfg", replace(portal_server.cfg, load_model=False)):
            with patch.dict(os.environ, {"ATHENA_PUBLIC_VLLM_ONLY": "1"}, clear=False):
                self.assertTrue(portal_server._runtime_ready(snapshot))

    def test_healthz_surfaces_runtime_backend_and_readiness(self) -> None:
        snapshot = {
            "runtime_backend": "vllm_openai",
            "runtime_backend_label": "vLLM OpenAI-compatible",
            "model_loaded": True,
            "model_label": "Qwen3.5-4B",
            "model_dir": "http://127.0.0.1:8001/v1",
        }
        with patch.object(portal_server.engine, "runtime_snapshot", return_value=snapshot):
            with patch.dict(os.environ, {"ATHENA_PUBLIC_VLLM_ONLY": "1"}, clear=False):
                payload = portal_server.healthz()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runtime_backend"], "vllm_openai")
        self.assertEqual(payload["active_model_label"], "Qwen3.5-4B")


if __name__ == "__main__":
    unittest.main()
