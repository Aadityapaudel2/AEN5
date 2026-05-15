from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.finetune_studio import paths


class FinetuneStudioPathsTests(unittest.TestCase):
    def test_load_session_state_initializes_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with patch.object(paths, "APP_DIR", root / "src"), patch.object(
                paths, "APP_DATA_DIR", root
            ), patch.object(paths, "CONFIG_DIR", root / "config"), patch.object(
                paths, "LOGS_DIR", root / "logs"
            ), patch.object(paths, "BUILD_DIR", root / "build"), patch.object(
                paths, "DIST_DIR", root / "dist"
            ), patch.object(paths, "SESSION_STATE_PATH", root / "config" / "session_state.json"), patch.object(
                paths, "LEGACY_CONFIG_DIR", root / "legacy_config"
            ), patch.object(paths, "LEGACY_SESSION_STATE_PATH", root / "legacy_config" / "session_state.json"):
                state = paths.load_session_state()
                self.assertEqual(state["selected_preset"], "most_stable")
                self.assertEqual(state["loaded_args_path"], "")
                self.assertEqual(state["selected_train_file_path"], "")
                self.assertEqual(state["compose"]["output_path"], "Finetune/trainingdata/manual_train_ready.jsonl")
                self.assertEqual(state["compose"]["system_instructions"], "")
                self.assertEqual(state["build"]["orchestrator_max_seq_length"], 2048)
                self.assertTrue((root / "config" / "session_state.json").exists())

    def test_save_session_state_deep_merges_nested_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with patch.object(paths, "APP_DIR", root / "src"), patch.object(
                paths, "APP_DATA_DIR", root
            ), patch.object(paths, "CONFIG_DIR", root / "config"), patch.object(
                paths, "LOGS_DIR", root / "logs"
            ), patch.object(paths, "BUILD_DIR", root / "build"), patch.object(
                paths, "DIST_DIR", root / "dist"
            ), patch.object(paths, "SESSION_STATE_PATH", root / "config" / "session_state.json"), patch.object(
                paths, "LEGACY_CONFIG_DIR", root / "legacy_config"
            ), patch.object(paths, "LEGACY_SESSION_STATE_PATH", root / "legacy_config" / "session_state.json"):
                paths.save_session_state(
                    {
                        "loaded_args_path": "Finetune/finetune_args.json",
                        "selected_train_file_path": "Finetune/trainingdata/identitytraining.jsonl",
                        "prepare": {"input_path": "raw.jsonl"},
                        "compose": {
                            "output_path": "manual.jsonl",
                            "system_instructions": "Be Athena.",
                            "user_prompt": "Q",
                            "assistant_prompt": "A",
                        },
                        "build": {
                            "builder_id": "chunked_sft",
                            "output": "chunked.jsonl",
                            "orchestrator_max_seq_length": 3072,
                        },
                    }
                )
                state = paths.load_session_state()
                self.assertEqual(state["loaded_args_path"], "Finetune/finetune_args.json")
                self.assertEqual(state["selected_train_file_path"], "Finetune/trainingdata/identitytraining.jsonl")
                self.assertEqual(state["prepare"]["input_path"], "raw.jsonl")
                self.assertEqual(state["compose"]["output_path"], "manual.jsonl")
                self.assertEqual(state["compose"]["system_instructions"], "Be Athena.")
                self.assertEqual(state["compose"]["user_prompt"], "Q")
                self.assertEqual(state["prepare"]["assistant_role"], "teacher")
                self.assertEqual(state["build"]["builder_id"], "chunked_sft")
                self.assertEqual(state["build"]["output"], "chunked.jsonl")
                self.assertEqual(state["build"]["orchestrator_max_seq_length"], 3072)

    def test_legacy_session_state_migrates_to_app_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            legacy_state = {
                "selected_preset": "super_fast",
                "compose": {"output_path": "legacy.jsonl"},
            }
            legacy_dir = root / "repo_app" / "config"
            legacy_dir.mkdir(parents=True, exist_ok=True)
            legacy_path = legacy_dir / "session_state.json"
            legacy_path.write_text(paths.json.dumps(legacy_state), encoding="utf-8")
            with patch.object(paths, "APP_DIR", root / "repo_app"), patch.object(
                paths, "APP_DATA_DIR", root / "user_data"
            ), patch.object(paths, "CONFIG_DIR", root / "user_data" / "config"), patch.object(
                paths, "LOGS_DIR", root / "user_data" / "logs"
            ), patch.object(paths, "BUILD_DIR", root / "user_data" / "build"), patch.object(
                paths, "DIST_DIR", root / "user_data" / "dist"
            ), patch.object(
                paths, "SESSION_STATE_PATH", root / "user_data" / "config" / "session_state.json"
            ), patch.object(paths, "LEGACY_CONFIG_DIR", legacy_dir), patch.object(
                paths, "LEGACY_SESSION_STATE_PATH", legacy_path
            ):
                state = paths.load_session_state()
                self.assertEqual(state["selected_preset"], "super_fast")
                self.assertEqual(state["compose"]["output_path"], "legacy.jsonl")
                self.assertTrue((root / "user_data" / "config" / "session_state.json").exists())


if __name__ == "__main__":
    unittest.main()
