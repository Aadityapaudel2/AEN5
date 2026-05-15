from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Finetune.studio_backend import (
    ComposeTrainReadyRequest,
    DatasetValidationRequest,
    PrepareDialogueRequest,
    StudioService,
    TrainingLaunchRequest,
    TrainingPreflightRequest,
)
from Finetune.studio_backend.service import _format_elapsed, _studio_log_line


class StudioBackendValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.service = StudioService(self.root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_jsonl(self, name: str, rows: list[dict]) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def test_validate_dataset_accepts_train_ready_messages_jsonl(self) -> None:
        train_file = self._write_jsonl(
            "train.jsonl",
            [
                {"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]},
                {"messages": [{"role": "system", "content": "policy"}, {"role": "assistant", "content": "answer"}]},
            ],
        )
        result = self.service.validate_dataset(DatasetValidationRequest(train_file=str(train_file)))
        self.assertTrue(result.ok)
        self.assertTrue(result.ready)
        self.assertEqual(result.sample_count, 2)
        self.assertEqual(result.preview.row_count, 2)

    def test_validate_dataset_resolves_relative_path_from_service_root(self) -> None:
        self._write_jsonl(
            "Finetune/trainingdata/identitytraining.jsonl",
            [
                {"messages": [{"role": "user", "content": "who are you"}, {"role": "assistant", "content": "I am Athena"}]},
            ],
        )
        result = self.service.validate_dataset(
            DatasetValidationRequest(train_file="Finetune/trainingdata/identitytraining.jsonl")
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.ready)
        self.assertTrue(result.train_file.endswith("Finetune\\trainingdata\\identitytraining.jsonl") or result.train_file.endswith("Finetune/trainingdata/identitytraining.jsonl"))

    def test_validate_dataset_rejects_malformed_jsonl(self) -> None:
        train_file = self.root / "broken.jsonl"
        train_file.write_text('{"messages": [}\n', encoding="utf-8")
        result = self.service.validate_dataset(DatasetValidationRequest(train_file=str(train_file)))
        self.assertFalse(result.ok)
        self.assertIn("invalid JSON", result.error)

    def test_validate_dataset_rejects_missing_messages(self) -> None:
        train_file = self._write_jsonl("missing.jsonl", [{"prompt": "hello"}])
        result = self.service.validate_dataset(DatasetValidationRequest(train_file=str(train_file)))
        self.assertFalse(result.ok)
        self.assertIn("missing non-empty 'messages' list", result.error)

    def test_validate_dataset_flags_overlong_rows_under_strict_mode(self) -> None:
        train_file = self._write_jsonl(
            "strict.jsonl",
            [{"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]}],
        )
        model_dir = self.root / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(
            StudioService,
            "_probe_training_runtime",
            return_value={
                "ok": True,
                "sample_count": 1,
                "min_tokens": 10,
                "p95_tokens": 5000,
                "max_tokens": 5000,
                "tokenizer_class": "DummyTokenizer",
                "cuda_available": True,
                "total_vram_gib": 80.0,
            },
        ):
            result = self.service.validate_dataset(
                DatasetValidationRequest(
                    train_file=str(train_file),
                    model_path=str(model_dir),
                    max_seq_length=4096,
                    strict_no_truncation=True,
                    python_exe=sys.executable,
                )
            )
        self.assertTrue(result.ok)
        self.assertFalse(result.ready)
        self.assertTrue(any("max_seq_length=4096" in item for item in result.warnings))

    def test_compose_train_ready_jsonl_writes_and_appends_rows(self) -> None:
        result = self.service.compose_train_ready_jsonl(
            ComposeTrainReadyRequest(
                output_path="manual/train_ready.jsonl",
                system_instructions="You are Athena.",
                user_prompt="Question one",
                assistant_prompt="Answer one",
                append=False,
            )
        )
        self.assertEqual(result.row_count, 1)
        self.assertFalse(result.appended)

        result = self.service.compose_train_ready_jsonl(
            ComposeTrainReadyRequest(
                output_path="manual/train_ready.jsonl",
                user_prompt="Question two",
                assistant_prompt="Answer two",
                append=True,
            )
        )
        self.assertEqual(result.row_count, 2)
        path = Path(result.output_path)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(rows[0]["messages"][0]["role"], "system")
        self.assertEqual(rows[0]["messages"][0]["content"], "You are Athena.")
        self.assertEqual(rows[0]["messages"][1]["content"], "Question one")
        self.assertEqual(rows[1]["messages"][1]["content"], "Answer two")

    def test_load_training_config_file_merges_defaults(self) -> None:
        args_path = self.root / "finetune_args.json"
        args_path.write_text(
            json.dumps(
                {
                    "paths": {"model_path": "models/base", "train_file": "data/train.jsonl"},
                    "train": {"use_lora": True, "load_in_4bit": True},
                }
            ),
            encoding="utf-8",
        )
        resolved_path, config = self.service.load_training_config_file(args_path)
        self.assertEqual(resolved_path, args_path.resolve())
        self.assertEqual(config["paths"]["model_path"], "models/base")
        self.assertTrue(config["train"]["use_lora"])
        self.assertTrue(config["train"]["load_in_4bit"])
        self.assertEqual(config["train"]["logging_steps"], 10)


class StudioBackendCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = StudioService(PROJECT_ROOT)

    def test_log_helpers_format_elapsed_and_timestamped_lines(self) -> None:
        self.assertEqual(_format_elapsed(5), "00:00:05")
        self.assertEqual(_format_elapsed(3661), "01:01:01")
        line = _studio_log_line("heartbeat alive", tag="telemetry")
        self.assertIn("[telemetry]", line)
        self.assertIn("heartbeat alive", line)
        self.assertTrue(line.endswith("\n"))

    def test_resolve_output_path_routes_models_tuned_to_portable_root(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            tuned_root = Path(tempdir) / "portable_tuned"
            tuned_root.mkdir(parents=True, exist_ok=True)
            with patch("Finetune.studio_backend.service.get_project_tuned_models_dir", return_value=tuned_root):
                resolved = self.service.resolve_output_path(PROJECT_ROOT, "models/tuned/run_alpha")
        self.assertEqual(resolved, (tuned_root / "run_alpha").resolve())

    def test_full_sft_preset_command_shape_matches_dense_profile(self) -> None:
        config = self.service.load_preset_config("canonical_full_sft")
        command = self.service.build_training_command(
            python_exe=Path(sys.executable),
            train_script=self.service.train_script,
            config=config,
        )
        self.assertEqual(command[:3], [sys.executable, "-m", "accelerate.commands.launch"])
        self.assertIn("--model_name_or_path", command)
        self.assertNotIn("--use_lora", command)
        self.assertNotIn("--load_in_4bit", command)

    def test_qlora_preset_command_includes_adapter_flags(self) -> None:
        config = self.service.load_preset_config("qlora_adapter")
        command = self.service.build_training_command(
            python_exe=Path(sys.executable),
            train_script=self.service.train_script,
            config=config,
        )
        self.assertIn("--use_lora", command)
        self.assertIn("--load_in_4bit", command)
        self.assertIn("--lora_target_modules", command)

    def test_super_fast_studio_preset_is_dense_one_epoch(self) -> None:
        preset = {item.preset_id: item for item in self.service.list_presets()}["super_fast"]
        self.assertFalse(preset.config["train"]["use_lora"])
        self.assertFalse(preset.config["train"]["load_in_4bit"])
        self.assertTrue(preset.config["train"]["strict_no_truncation"])
        self.assertEqual(preset.config["train"]["num_train_epochs"], 1)
        self.assertEqual(preset.config["train"]["max_steps"], 0)

    def test_prepare_command_points_to_prepare_script(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = StudioService(root)
            input_path = root / "raw.jsonl"
            input_path.write_text("[]\n", encoding="utf-8")
            spec = service.build_prepare_command(
                PrepareDialogueRequest(
                    input_path=str(input_path),
                    output_path="prepared.jsonl",
                    python_exe=sys.executable,
                )
            )
        self.assertEqual(spec.command[0], sys.executable)
        self.assertEqual(spec.command[1], str(service.prepare_script))

    def test_launch_spec_writes_args_card_and_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = StudioService(root)
            model_dir = root / "models" / "base"
            model_dir.mkdir(parents=True, exist_ok=True)
            train_file = root / "data" / "train.jsonl"
            train_file.parent.mkdir(parents=True, exist_ok=True)
            train_file.write_text(
                json.dumps(
                    {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}
                )
                + "\n",
                encoding="utf-8",
            )
            config = service.blank_training_config()
            config["paths"]["model_path"] = "models/base"
            config["paths"]["train_file"] = "data/train.jsonl"
            config["paths"]["output_dir"] = "outputs/run_alpha"
            config["metadata"]["run_name"] = "run_alpha"
            with patch.object(
                StudioService,
                "resolve_training_runtime",
                return_value=(
                    Path(sys.executable),
                    {
                        "sample_count": 1,
                        "min_tokens": 10,
                        "p95_tokens": 10,
                        "max_tokens": 10,
                        "tokenizer_class": "DummyTokenizer",
                        "cuda_available": True,
                        "total_vram_gib": 80.0,
                    },
                ),
            ):
                preflight = service.preflight_training(TrainingPreflightRequest(config=config, dry_run=True, python_exe=sys.executable))
                spec = service.create_training_command_spec(TrainingLaunchRequest(preflight=preflight, dry_run=False))
                self.assertTrue(Path(preflight.summary["args_file"]).exists())
                self.assertTrue(Path(preflight.finetune_card_path).exists())
                self.assertTrue(Path(preflight.meta_path).exists())
                self.assertIn(Path(preflight.summary["args_file"]), spec.expected_outputs)
                self.assertEqual(spec.env_overrides.get("PYTHONUNBUFFERED"), "1")

    def test_dense_preflight_allows_local_1536_seq_run_under_conservative_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = StudioService(root)
            model_dir = root / "models" / "base"
            model_dir.mkdir(parents=True, exist_ok=True)
            train_file = root / "data" / "train.jsonl"
            train_file.parent.mkdir(parents=True, exist_ok=True)
            train_file.write_text(
                json.dumps(
                    {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}
                )
                + "\n",
                encoding="utf-8",
            )
            config = service.blank_training_config()
            config["paths"]["model_path"] = "models/base"
            config["paths"]["train_file"] = "data/train.jsonl"
            config["paths"]["output_dir"] = "outputs/run_beta"
            config["metadata"]["run_name"] = "run_beta"
            config["train"]["max_seq_length"] = 1536
            config["train"]["expected_samples"] = 1
            config["train"]["per_device_train_batch_size"] = 1
            config["train"]["gradient_accumulation_steps"] = 1
            config["train"]["gradient_checkpointing"] = True
            config["train"]["bf16"] = True
            config["train"]["fp16"] = False
            config["train"]["use_lora"] = False
            config["train"]["load_in_4bit"] = False
            with patch.object(
                StudioService,
                "resolve_training_runtime",
                return_value=(
                    Path(sys.executable),
                    {
                        "sample_count": 1,
                        "min_tokens": 64,
                        "p95_tokens": 1200,
                        "max_tokens": 1279,
                        "tokenizer_class": "DummyTokenizer",
                        "cuda_available": True,
                        "total_vram_gib": 15.93,
                    },
                ),
            ):
                preflight = service.preflight_training(
                    TrainingPreflightRequest(config=config, dry_run=True, python_exe=sys.executable)
                )
        self.assertTrue(preflight.ok)
        self.assertEqual(preflight.resolved_config["train"]["max_seq_length"], 1536)


if __name__ == "__main__":
    unittest.main()
