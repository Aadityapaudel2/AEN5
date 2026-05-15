from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from athena_paths import get_project_tuned_models_dir

from .models import (
    BuildCanonicalDatasetRequest,
    CommandSpec,
    ComposeTrainReadyRequest,
    ComposeTrainReadyResult,
    DatasetPreview,
    DatasetValidationRequest,
    DatasetValidationResult,
    JobSnapshot,
    JobStatus,
    PrepareDialogueRequest,
    RunRecord,
    StudioPreset,
    TrainingLaunchRequest,
    TrainingPreflightRequest,
    TrainingPreflightResult,
)

DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "model_path": "",
        "train_file": "",
        "output_dir": "",
        "resume_from_checkpoint": "",
    },
    "metadata": {
        "run_name": "",
        "training_mode": "",
        "intent": "",
        "reason_for_finetune": "",
        "expected_behavior": [],
        "notes": [],
        "source_snapshot_files": [],
    },
    "accelerate": {
        "num_processes": 1,
        "num_machines": 1,
        "mixed_precision": "bf16",
        "dynamo_backend": "no",
    },
    "train": {
        "max_seq_length": 2048,
        "expected_samples": 0,
        "strict_no_truncation": True,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 8,
        "learning_rate": 2e-5,
        "num_train_epochs": 1,
        "max_steps": 0,
        "warmup_ratio": 0.03,
        "lr_scheduler_type": "linear",
        "optim": "adamw_torch",
        "optim_args": "",
        "optim_target_modules": "",
        "torch_empty_cache_steps": 0,
        "weight_decay": 0.0,
        "max_grad_norm": 1.0,
        "logging_steps": 10,
        "save_steps": 200,
        "save_total_limit": 2,
        "save_only_model": True,
        "bf16": True,
        "fp16": False,
        "gradient_checkpointing": True,
        "seed": 777,
        "use_lora": False,
        "load_in_4bit": False,
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "lora_target_modules": "q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
    },
}

MEMORY_EFFICIENT_DENSE_OPTIMIZERS = {
    "galore_adamw",
    "galore_adamw_8bit",
    "galore_adafactor",
    "galore_adamw_layerwise",
    "galore_adamw_8bit_layerwise",
    "galore_adafactor_layerwise",
    "apollo_adamw",
    "apollo_adamw_layerwise",
}

DENSE_LOCAL_SEQ_CEILING = 2048


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _stringify_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _format_elapsed(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _studio_log_line(message: str, *, tag: str = "studio") -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = message.rstrip("\n")
    return f"[{stamp}] [{tag}] {body}\n"


class StudioService:
    def __init__(self, project_root: Path | str | None = None):
        self.project_root = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.finetune_root = self.project_root / "Finetune"
        self.training_runs_root = self.finetune_root / "runs"
        self.train_script = self.finetune_root / "train.py"
        self.prepare_script = self.finetune_root / "tooling" / "prepare" / "prepare_data.py"
        self.builder_dir = self.finetune_root / "tooling" / "builders"
        self.preset_files = {
            "canonical_full_sft": self.finetune_root / "finetune_args.json",
            "qlora_adapter": self.finetune_root / "finetune_args_qlora_adapter.json",
        }

    def blank_training_config(self) -> dict[str, Any]:
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["metadata"]["training_mode"] = "Custom"
        config["metadata"]["run_name"] = "finetune_run"
        config["metadata"]["notes"] = ["Created from Finetune Studio."]
        return config

    def list_presets(self) -> list[StudioPreset]:
        stable_config = self.load_preset_config("canonical_full_sft")
        fast_config = copy.deepcopy(stable_config)
        fast_config["metadata"]["training_mode"] = "Super Fast Finetuning"
        fast_config["metadata"]["intent"] = "Shortest dense finetune pass with one epoch and strict no truncation."
        fast_config["train"]["expected_samples"] = 0
        fast_config["train"]["num_train_epochs"] = 1
        fast_config["train"]["max_steps"] = 0
        fast_config["train"]["strict_no_truncation"] = True
        fast_config["train"]["use_lora"] = False
        fast_config["train"]["load_in_4bit"] = False
        fast_config["train"]["logging_steps"] = 10
        fast_config["train"]["save_steps"] = 1000
        fast_config["train"]["save_total_limit"] = 1
        fast_config["train"]["torch_empty_cache_steps"] = 0

        dense_config = copy.deepcopy(stable_config)
        dense_config["metadata"]["training_mode"] = "Super Dense Finetuning"
        dense_config["metadata"]["intent"] = "Full-model dense finetune profile for the strongest direct weight update path."

        most_stable_config = copy.deepcopy(stable_config)
        most_stable_config["metadata"]["training_mode"] = "Most Stable Finetuning"
        most_stable_config["metadata"]["intent"] = "Known-good Athena V1 style baseline for the safest local launch path."

        return [
            StudioPreset(
                preset_id="super_fast",
                label="Super Fast Finetuning",
                description="Shortest dense 1-epoch finetune path with strict no truncation kept on.",
                args_path=self.preset_files["canonical_full_sft"],
                config=fast_config,
            ),
            StudioPreset(
                preset_id="super_dense",
                label="Super Dense Finetuning",
                description="Full-model dense tuning profile when you want the heaviest direct finetune path.",
                args_path=self.preset_files["canonical_full_sft"],
                config=dense_config,
            ),
            StudioPreset(
                preset_id="most_stable",
                label="Most Stable Finetuning",
                description="Safest default. Uses the current Athena V1-style known-good baseline parameters.",
                args_path=self.preset_files["canonical_full_sft"],
                config=most_stable_config,
            ),
            StudioPreset(
                preset_id="blank_custom",
                label="Blank Custom",
                description="Start from defaults and edit everything manually.",
                args_path=None,
                config=self.blank_training_config(),
            ),
        ]

    def load_preset_config(self, preset_id: str) -> dict[str, Any]:
        if preset_id == "blank_custom":
            return self.blank_training_config()
        raw = json.loads(self.preset_files[preset_id].read_text(encoding="utf-8-sig"))
        config = _deep_merge(DEFAULT_CONFIG, raw)
        if not config["metadata"].get("run_name"):
            output_dir = str(config["paths"].get("output_dir") or "").strip()
            config["metadata"]["run_name"] = Path(output_dir).name if output_dir else "finetune_run"
        return config

    def load_training_config_file(self, args_path: str | Path) -> tuple[Path, dict[str, Any]]:
        path = self.resolve_existing_path(self.project_root, args_path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid finetune args JSON: {path}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"Finetune args must contain a JSON object: {path}")
        config = _deep_merge(DEFAULT_CONFIG, raw)
        if not config["metadata"].get("run_name"):
            output_dir = str(config["paths"].get("output_dir") or "").strip()
            config["metadata"]["run_name"] = Path(output_dir).name if output_dir else "finetune_run"
        return path, config

    def inspect_messages_jsonl(self, train_file: Path | str) -> DatasetPreview:
        path = Path(train_file).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Train file not found: {path}")

        row_count = 0
        message_min: int | None = None
        message_max = 0
        preview_rows: list[dict[str, Any]] = []
        role_counts: Counter[str] = Counter()

        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Line {line_number}: invalid JSON ({exc})") from exc
                messages = payload.get("messages")
                if not isinstance(messages, list) or not messages:
                    raise ValueError(f"Line {line_number}: missing non-empty 'messages' list")
                cleaned_messages: list[dict[str, str]] = []
                for message in messages:
                    if not isinstance(message, dict):
                        raise ValueError(f"Line {line_number}: message items must be objects")
                    role = str(message.get("role") or "").strip()
                    content = str(message.get("content") or "").strip()
                    if role not in {"system", "user", "assistant"}:
                        raise ValueError(f"Line {line_number}: invalid role {role!r}")
                    if not content:
                        raise ValueError(f"Line {line_number}: empty content for role {role!r}")
                    cleaned_messages.append({"role": role, "content": content})
                    role_counts[role] += 1
                row_count += 1
                width = len(cleaned_messages)
                message_min = width if message_min is None else min(message_min, width)
                message_max = max(message_max, width)
                if len(preview_rows) < 3:
                    preview_rows.append(
                        {
                            "line": line_number,
                            "messages": [
                                {"role": item["role"], "content": item["content"][:180]}
                                for item in cleaned_messages[:3]
                            ],
                        }
                    )
        if row_count == 0:
            raise ValueError("No usable training rows found")
        return DatasetPreview(
            row_count=row_count,
            message_count_min=message_min or 0,
            message_count_max=message_max,
            preview_rows=preview_rows,
            role_counts=dict(role_counts),
        )

    def compose_train_ready_jsonl(self, request: ComposeTrainReadyRequest) -> ComposeTrainReadyResult:
        output_path = self.resolve_output_path(self.project_root, request.output_path, create_if_missing=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        system_instructions = str(request.system_instructions).strip()
        user_prompt = str(request.user_prompt).strip()
        assistant_prompt = str(request.assistant_prompt).strip()
        if not user_prompt:
            raise ValueError("User prompt is required.")
        if not assistant_prompt:
            raise ValueError("Assistant prompt is required.")

        messages: list[dict[str, str]] = []
        if system_instructions:
            messages.append({"role": "system", "content": system_instructions})
        messages.append({"role": "user", "content": user_prompt})
        messages.append({"role": "assistant", "content": assistant_prompt})
        payload = {"messages": messages}
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        if request.append:
            with output_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        else:
            output_path.write_text(line, encoding="utf-8")

        row_count = 0
        with output_path.open("r", encoding="utf-8-sig") as handle:
            for raw_line in handle:
                if raw_line.strip():
                    row_count += 1
        return ComposeTrainReadyResult(
            output_path=str(output_path),
            row_count=row_count,
            appended=bool(request.append),
        )

    def validate_dataset(self, request: DatasetValidationRequest) -> DatasetValidationResult:
        try:
            resolved_train_file = self.resolve_existing_path(self.project_root, request.train_file)
            preview = self.inspect_messages_jsonl(resolved_train_file)
        except Exception as exc:
            return DatasetValidationResult(ok=False, train_file=request.train_file, error=str(exc))

        warnings: list[str] = []
        sample_count = preview.row_count
        min_tokens = 0
        p95_tokens = 0
        max_tokens = 0
        tokenizer_class = ""
        ready = True

        model_path = (request.model_path or "").strip()
        if model_path:
            try:
                runtime_probe = self._probe_training_runtime(
                    python_exe=request.python_exe,
                    model_path=self.resolve_existing_path(self.project_root, model_path),
                    train_file=resolved_train_file,
                )
            except Exception as exc:
                warnings.append(str(exc))
                ready = False
            else:
                sample_count = int(runtime_probe["sample_count"])
                min_tokens = int(runtime_probe["min_tokens"])
                p95_tokens = int(runtime_probe["p95_tokens"])
                max_tokens = int(runtime_probe["max_tokens"])
                tokenizer_class = str(runtime_probe["tokenizer_class"])
                if request.strict_no_truncation and request.max_seq_length > 0 and max_tokens > request.max_seq_length:
                    ready = False
                    warnings.append(
                        f"Dataset max token length {max_tokens} exceeds max_seq_length={request.max_seq_length}."
                    )

        return DatasetValidationResult(
            ok=True,
            train_file=str(resolved_train_file),
            preview=preview,
            sample_count=sample_count,
            min_tokens=min_tokens,
            p95_tokens=p95_tokens,
            max_tokens=max_tokens,
            tokenizer_class=tokenizer_class,
            ready=ready,
            warnings=warnings,
        )

    def resolve_existing_path(self, base_dir: Path, path_value: str | Path) -> Path:
        raw = str(path_value).strip()
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        resolved = candidate.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Path not found: {resolved}")
        return resolved

    def resolve_optional_existing_path(self, base_dir: Path, path_value: str | Path | None) -> Path | None:
        if not path_value:
            return None
        try:
            return self.resolve_existing_path(base_dir, path_value)
        except FileNotFoundError:
            return None

    def resolve_output_path(self, base_dir: Path, path_value: str | Path, *, create_if_missing: bool = False) -> Path:
        raw = str(path_value).replace("/", os.sep).strip()
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            normalized = raw.lower()
            tuned_prefix = f"models{os.sep}tuned"
            if normalized == tuned_prefix or normalized.startswith(f"{tuned_prefix}{os.sep}"):
                tuned_root = os.getenv("ATHENA_TUNED_MODELS_ROOT", "").strip()
                root = Path(tuned_root).expanduser() if tuned_root else get_project_tuned_models_dir()
                suffix = raw[len(tuned_prefix) :].lstrip("\\/")
                candidate = root / suffix if suffix else root
            else:
                candidate = base_dir / candidate
        resolved = candidate.resolve()
        if create_if_missing:
            resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def get_python_exe_candidates(self) -> list[Path]:
        candidates: list[Path] = []

        def add_candidate(path_value: str | Path | None) -> None:
            if not path_value:
                return
            candidate = Path(path_value).expanduser()
            if candidate.exists():
                resolved = candidate.resolve()
                if resolved not in candidates:
                    candidates.append(resolved)

        virtual_env = os.getenv("VIRTUAL_ENV", "").strip()
        if virtual_env:
            add_candidate(Path(virtual_env) / self._python_subpath())
        add_candidate(self.project_root / ".venv" / self._python_subpath())
        add_candidate(self.project_root.parent / ".venv" / self._python_subpath())
        add_candidate(sys.executable)
        python_cmd = shutil.which("python")
        if python_cmd:
            add_candidate(python_cmd)
        if not candidates:
            raise RuntimeError("Python executable not found. Activate a venv or create .venv in the project root.")
        return candidates

    def _python_subpath(self) -> Path:
        return Path("Scripts") / "python.exe" if os.name == "nt" else Path("bin") / "python"

    def _probe_training_runtime(self, *, python_exe: str | Path, model_path: Path, train_file: Path) -> dict[str, Any]:
        python_path = Path(python_exe).expanduser().resolve()
        command = [
            str(python_path),
            "-m",
            "Finetune.studio_backend.probe_training",
            "--model-path",
            str(model_path),
            "--train-file",
            str(train_file),
        ]
        completed = subprocess.run(
            command,
            cwd=self.project_root,
            check=False,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or "").strip() or (completed.stderr or "").strip()
        if completed.returncode != 0:
            raise RuntimeError(output or f"Probe failed with exit code {completed.returncode}.")
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Unable to parse probe output: {output}") from exc
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "Training probe failed."))
        return payload

    def resolve_training_runtime(
        self,
        *,
        model_path: Path,
        train_file: Path,
        allow_cpu: bool = False,
        explicit_python: str = "",
    ) -> tuple[Path, dict[str, Any]]:
        failures: list[str] = []
        cpu_fallback: tuple[Path, dict[str, Any]] | None = None
        candidates = []
        if explicit_python:
            candidates.append(Path(explicit_python).expanduser().resolve())
        candidates.extend(self.get_python_exe_candidates())

        unique_candidates: list[Path] = []
        for candidate in candidates:
            if candidate not in unique_candidates:
                unique_candidates.append(candidate)

        for candidate in unique_candidates:
            try:
                probe = self._probe_training_runtime(
                    python_exe=candidate,
                    model_path=model_path,
                    train_file=train_file,
                )
            except Exception as exc:
                failures.append(f"{candidate} [{exc}]")
                continue
            if bool(probe.get("cuda_available")):
                return candidate, probe
            if cpu_fallback is None:
                cpu_fallback = (candidate, probe)
            failures.append(f"{candidate} [cuda] CUDA unavailable")

        if allow_cpu and cpu_fallback is not None:
            return cpu_fallback
        message = "No compatible Python runtime found for training."
        if failures:
            message += "\nChecked:\n - " + "\n - ".join(failures)
        if not allow_cpu:
            message += "\nUse CPU fallback only if CPU training is intentional."
        raise RuntimeError(message)

    def preflight_training(self, request: TrainingPreflightRequest) -> TrainingPreflightResult:
        config = _deep_merge(DEFAULT_CONFIG, request.config)
        paths = config["paths"]
        train_cfg = config["train"]
        metadata = config["metadata"]

        model_path = self.resolve_existing_path(self.project_root, str(paths["model_path"]))
        train_file = self.resolve_existing_path(self.project_root, str(paths["train_file"]))
        output_dir = self.resolve_output_path(self.project_root, str(paths["output_dir"]), create_if_missing=not request.dry_run)
        resume_checkpoint = self.resolve_optional_existing_path(
            self.project_root,
            str(paths.get("resume_from_checkpoint") or "").strip(),
        )

        python_exe, runtime_probe = self.resolve_training_runtime(
            model_path=model_path,
            train_file=train_file,
            allow_cpu=bool(request.allow_cpu),
            explicit_python=request.python_exe,
        )
        resolved_expected_samples = int(runtime_probe["sample_count"])
        warnings: list[str] = []
        if int(train_cfg["expected_samples"]) > 0 and int(train_cfg["expected_samples"]) != resolved_expected_samples:
            warnings.append(
                f"expected_samples={train_cfg['expected_samples']} does not match train file count={resolved_expected_samples}; using dataset count."
            )

        max_seq_length = int(train_cfg["max_seq_length"])
        max_tokens = int(runtime_probe["max_tokens"])
        if bool(train_cfg["strict_no_truncation"]) and max_tokens > max_seq_length:
            raise RuntimeError(
                f"Dataset max token length ({max_tokens}) exceeds train.max_seq_length={max_seq_length} while strict_no_truncation is enabled."
            )
        if bool(train_cfg["bf16"]) and bool(train_cfg["fp16"]):
            raise RuntimeError("Invalid config: both train.bf16 and train.fp16 are true.")
        if bool(train_cfg["load_in_4bit"]) and not bool(train_cfg["use_lora"]):
            raise RuntimeError("Invalid config: train.load_in_4bit requires train.use_lora=true.")

        optim = str(train_cfg["optim"]).strip()
        is_conservative_dense_fastpass = (
            (not bool(train_cfg["use_lora"]))
            and (not bool(train_cfg["load_in_4bit"]))
            and optim not in MEMORY_EFFICIENT_DENSE_OPTIMIZERS
            and max_seq_length <= DENSE_LOCAL_SEQ_CEILING
            and int(train_cfg["per_device_train_batch_size"]) == 1
            and bool(train_cfg["gradient_checkpointing"])
            and (bool(train_cfg["bf16"]) or bool(train_cfg["fp16"]))
        )
        if (
            not bool(train_cfg["use_lora"])
            and not bool(train_cfg["load_in_4bit"])
            and optim not in MEMORY_EFFICIENT_DENSE_OPTIMIZERS
            and not is_conservative_dense_fastpass
            and bool(runtime_probe["cuda_available"])
            and float(runtime_probe["total_vram_gib"]) < 64.0
        ):
            blockers: list[str] = []
            if max_seq_length > DENSE_LOCAL_SEQ_CEILING:
                blockers.append(
                    f"max_seq_length={max_seq_length} is above the dense local ceiling of {DENSE_LOCAL_SEQ_CEILING}"
                )
            if int(train_cfg["per_device_train_batch_size"]) != 1:
                blockers.append(
                    f"per_device_train_batch_size={train_cfg['per_device_train_batch_size']} must be 1 for the dense fastpass"
                )
            if not bool(train_cfg["gradient_checkpointing"]):
                blockers.append("gradient_checkpointing must be enabled for the dense fastpass")
            if not (bool(train_cfg["bf16"]) or bool(train_cfg["fp16"])):
                blockers.append("BF16 or FP16 must be enabled for the dense fastpass")
            if bool(train_cfg["strict_no_truncation"]) and max_tokens > DENSE_LOCAL_SEQ_CEILING:
                blockers.append(
                    f"the dataset reaches {max_tokens} tokens, so strict no truncation prevents staying inside the {DENSE_LOCAL_SEQ_CEILING}-token dense local ceiling"
                )
            detail = ""
            if blockers:
                detail = "\nCurrent blockers:\n- " + "\n- ".join(blockers)
            raise RuntimeError(
                "Dense full-model finetuning is selected, but the detected GPU only has "
                f"{runtime_probe['total_vram_gib']} GiB VRAM."
                f"{detail}\nKnown-good reference: AthenaV1 succeeded locally on March 13, 2026 on the same 15.93 GiB class GPU, "
                "but that run stayed inside a 1024-token dense full-SFT window with max dataset row length 1013, batch size 1, gradient accumulation 1, BF16, and gradient checkpointing enabled."
                f"\nThe studio now allows dense local runs up to {DENSE_LOCAL_SEQ_CEILING} tokens when the rest of the launch stays conservative. "
                f"Use a larger GPU, choose a smaller base model, or shorten or chunk the dataset so it fits within {DENSE_LOCAL_SEQ_CEILING} tokens if you need to stay inside the local dense guidance window."
            )

        run_name = str(metadata.get("run_name") or "").strip() or output_dir.name
        source_snapshot_inputs = [train_file]
        source_snapshot_inputs.extend(
            filter(
                None,
                (
                    self.resolve_optional_existing_path(self.project_root, item)
                    for item in metadata.get("source_snapshot_files", [])
                ),
            )
        )

        run_root = self.training_runs_root / run_name
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_path = run_root / f"train_{stamp}.log"
        meta_path = run_root / f"train_{stamp}.meta.json"
        source_snapshot_dir = output_dir / "_finetune_source"
        finetune_card_path = output_dir / "FINETUNE_CARD.md"
        args_snapshot_path = output_dir / "FINETUNE_ARGS.json"

        resolved_config = _deep_merge(config, {})
        resolved_config["paths"]["model_path"] = str(model_path)
        resolved_config["paths"]["train_file"] = str(train_file)
        resolved_config["paths"]["output_dir"] = str(output_dir)
        resolved_config["paths"]["resume_from_checkpoint"] = str(resume_checkpoint or "")
        resolved_config["train"]["expected_samples"] = resolved_expected_samples

        summary = {
            "args_file": "",
            "model": str(model_path),
            "train_file": str(train_file),
            "output_dir": str(output_dir),
            "run_name": run_name,
            "args_file": str(args_snapshot_path),
            "finetune_card": str(finetune_card_path),
            "source_snapshot_dir": str(source_snapshot_dir),
            "transcript": str(transcript_path),
            "accelerate": copy.deepcopy(config["accelerate"]),
            "train": {**copy.deepcopy(config["train"]), "expected_samples": resolved_expected_samples},
            "runtime": runtime_probe,
            "dataset": {
                "sample_count": resolved_expected_samples,
                "min_tokens": int(runtime_probe["min_tokens"]),
                "p95_tokens": int(runtime_probe["p95_tokens"]),
                "max_tokens": int(runtime_probe["max_tokens"]),
            },
            "training_mode": str(metadata.get("training_mode") or ""),
            "intent": str(metadata.get("intent") or ""),
            "warnings": warnings,
        }
        if resume_checkpoint is not None:
            summary["resume_from_checkpoint"] = str(resume_checkpoint)

        command = self.build_training_command(
            python_exe=python_exe,
            train_script=self.train_script,
            config=resolved_config,
        )
        return TrainingPreflightResult(
            ok=True,
            summary=summary,
            resolved_config=resolved_config,
            command=command,
            python_exe=str(python_exe),
            cwd=str(self.finetune_root),
            transcript_path=str(transcript_path),
            meta_path=str(meta_path),
            finetune_card_path=str(finetune_card_path),
            source_snapshot_dir=str(source_snapshot_dir),
            allow_cpu=bool(request.allow_cpu),
            source_snapshot_inputs=[str(item) for item in source_snapshot_inputs],
        )

    def build_training_command(self, *, python_exe: Path, train_script: Path, config: dict[str, Any]) -> list[str]:
        accelerate_cfg = config["accelerate"]
        train_cfg = config["train"]
        paths = config["paths"]
        args = [
            str(python_exe),
            "-m",
            "accelerate.commands.launch",
            "--num_processes",
            str(accelerate_cfg["num_processes"]),
            "--num_machines",
            str(accelerate_cfg["num_machines"]),
            "--mixed_precision",
            str(accelerate_cfg["mixed_precision"]),
            "--dynamo_backend",
            str(accelerate_cfg["dynamo_backend"]),
            str(train_script),
            "--model_name_or_path",
            str(paths["model_path"]),
            "--train_file",
            str(paths["train_file"]),
            "--output_dir",
            str(paths["output_dir"]),
            "--max_seq_length",
            str(train_cfg["max_seq_length"]),
            "--expected_samples",
            str(train_cfg["expected_samples"]),
            "--per_device_train_batch_size",
            str(train_cfg["per_device_train_batch_size"]),
            "--gradient_accumulation_steps",
            str(train_cfg["gradient_accumulation_steps"]),
            "--learning_rate",
            str(train_cfg["learning_rate"]),
            "--num_train_epochs",
            str(train_cfg["num_train_epochs"]),
            "--warmup_ratio",
            str(train_cfg["warmup_ratio"]),
            "--lr_scheduler_type",
            str(train_cfg["lr_scheduler_type"]),
            "--weight_decay",
            str(train_cfg["weight_decay"]),
            "--max_grad_norm",
            str(train_cfg["max_grad_norm"]),
            "--logging_steps",
            str(train_cfg["logging_steps"]),
            "--save_steps",
            str(train_cfg["save_steps"]),
            "--save_total_limit",
            str(train_cfg["save_total_limit"]),
            "--seed",
            str(train_cfg["seed"]),
            "--max_steps",
            str(train_cfg["max_steps"]),
            "--optim",
            str(train_cfg["optim"]),
            "--torch_empty_cache_steps",
            str(train_cfg["torch_empty_cache_steps"]),
            "--lora_r",
            str(train_cfg["lora_r"]),
            "--lora_alpha",
            str(train_cfg["lora_alpha"]),
            "--lora_dropout",
            str(train_cfg["lora_dropout"]),
            "--lora_target_modules",
            str(train_cfg["lora_target_modules"]),
        ]
        if str(train_cfg.get("optim_args") or "").strip():
            args.extend(["--optim_args", str(train_cfg["optim_args"])])
        if str(train_cfg.get("optim_target_modules") or "").strip():
            args.extend(["--optim_target_modules", str(train_cfg["optim_target_modules"])])
        if str(paths.get("resume_from_checkpoint") or "").strip():
            args.extend(["--resume_from_checkpoint", str(paths["resume_from_checkpoint"])])
        for key in (
            "save_only_model",
            "strict_no_truncation",
            "bf16",
            "fp16",
            "gradient_checkpointing",
            "use_lora",
            "load_in_4bit",
        ):
            if bool(train_cfg[key]):
                args.append(f"--{key}")
        return args

    def build_prepare_command(self, request: PrepareDialogueRequest) -> CommandSpec:
        python_exe = (
            Path(request.python_exe).expanduser().resolve()
            if request.python_exe
            else self.get_python_exe_candidates()[0]
        )
        input_path = self.resolve_existing_path(self.project_root, request.input_path)
        output_path = self.resolve_output_path(self.project_root, request.output_path, create_if_missing=False)
        command = [
            str(python_exe),
            str(self.prepare_script),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--assistant_role",
            request.assistant_role,
            "--artifact_style",
            request.artifact_style,
            "--max_context_messages",
            str(request.max_context_messages),
            "--min_messages",
            str(request.min_messages),
        ]
        if request.drop_empty:
            command.append("--drop_empty")
        if request.require_user_before_assistant:
            command.append("--require_user_before_assistant")
        if request.merge_consecutive_same_role:
            command.append("--merge_consecutive_same_role")
        if request.strip_role_prefixes:
            command.append("--strip_role_prefixes")
        return CommandSpec(
            title="Prepare Dialogue Data",
            kind="prepare",
            command=command,
            cwd=self.project_root,
            expected_outputs=[output_path],
        )

    def build_canonical_dataset_command(self, request: BuildCanonicalDatasetRequest) -> CommandSpec:
        python_exe = (
            Path(request.python_exe).expanduser().resolve()
            if request.python_exe
            else self.get_python_exe_candidates()[0]
        )
        options = request.options
        builder_id = request.builder_id
        if builder_id == "training_dataset_0":
            command = [str(python_exe), str(self.builder_dir / "build_training_dataset_0.py")]
            outputs = [self.finetune_root / "trainingdata" / "training_dataset_0_identity.jsonl"]
            title = "Build Dataset 0 Identity"
        elif builder_id == "verified_sft":
            command = [str(python_exe), str(self.builder_dir / "build_verified_sft_dataset.py")]
            outputs = [self.finetune_root / "trainingdata" / "math_plus_logic_verified_sft.jsonl"]
            title = "Build Verified Math+Logic Dataset"
        elif builder_id == "chunked_sft":
            source = self.resolve_existing_path(self.project_root, str(options["source"]))
            output = self.resolve_output_path(self.project_root, str(options["output"]), create_if_missing=False)
            manifest_output = self.resolve_output_path(self.project_root, str(options["manifest_output"]), create_if_missing=False)
            model = self.resolve_existing_path(self.project_root, str(options["model"]))
            command = [
                str(python_exe),
                str(self.builder_dir / "build_chunked_sft_dataset.py"),
                "--model",
                str(model),
                "--source",
                str(source),
                "--output",
                str(output),
                "--manifest-output",
                str(manifest_output),
                "--max-seq-length",
                str(int(options.get("max_seq_length", 4096))),
            ]
            if bool(options.get("drop_overlong_base")):
                command.append("--drop-overlong-base")
            if bool(options.get("drop_unchunkable")):
                command.append("--drop-unchunkable")
            outputs = [output, manifest_output]
            title = "Build Chunked SFT Dataset"
        elif builder_id == "orchestrator_v1":
            model_name_or_path = str(options.get("model_name_or_path") or "")
            command = [str(python_exe), str(self.builder_dir / "build_orchestrator_dataset.py")]
            for flag in ("bootstrap", "overwrite_bootstrap", "write", "validate", "token_stats"):
                if bool(options.get(flag)):
                    command.append(f"--{flag.replace('_', '-')}")
            command.extend(["--max-seq-length", str(int(options.get("max_seq_length", 2048)))])
            if model_name_or_path:
                resolved_model = self.resolve_existing_path(self.project_root, model_name_or_path)
                command.extend(["--model-name-or-path", str(resolved_model)])
            outputs = [self.finetune_root / "trainingdata" / "orchestrator_v1" / "manifest.json"]
            title = "Build Orchestrator V1 Dataset"
        else:
            raise ValueError(f"Unknown builder_id: {builder_id}")
        return CommandSpec(
            title=title,
            kind="build",
            command=command,
            cwd=self.project_root,
            expected_outputs=outputs,
        )

    def create_training_command_spec(self, request: TrainingLaunchRequest) -> CommandSpec:
        preflight = request.preflight
        if not preflight.ok:
            raise RuntimeError(preflight.error or "Training preflight failed.")
        if request.dry_run:
            return CommandSpec(
                title=f"Dry Run: {preflight.summary.get('run_name', 'finetune')}",
                kind="training_dry_run",
                command=preflight.command,
                cwd=Path(preflight.cwd),
            )

        output_dir = Path(preflight.resolved_config["paths"]["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        source_snapshot_dir = Path(preflight.source_snapshot_dir)
        source_snapshot_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = Path(preflight.transcript_path)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)

        snapshot_targets: list[str] = []
        for source in preflight.source_snapshot_inputs:
            source_path = Path(source)
            destination = source_snapshot_dir / source_path.name
            shutil.copy2(source_path, destination)
            snapshot_targets.append(str(destination))

        card_text = self._build_finetune_card(preflight)
        Path(preflight.summary["args_file"]).write_text(_stringify_json(preflight.resolved_config), encoding="utf-8")
        Path(preflight.finetune_card_path).write_text(card_text, encoding="utf-8")

        run_meta = {
            "started_at": _iso_now(),
            "run_name": preflight.summary["run_name"],
            "args_file": preflight.summary["args_file"],
            "model": preflight.summary["model"],
            "train_file": preflight.summary["train_file"],
            "output_dir": preflight.summary["output_dir"],
            "transcript": preflight.transcript_path,
            "finetune_card": preflight.finetune_card_path,
            "source_snapshot_dir": preflight.source_snapshot_dir,
            "source_snapshots": snapshot_targets,
            "training_mode": preflight.summary.get("training_mode", ""),
            "allow_cpu": bool(preflight.allow_cpu),
            "use_lora": bool(preflight.resolved_config["train"]["use_lora"]),
            "load_in_4bit": bool(preflight.resolved_config["train"]["load_in_4bit"]),
            "runtime": preflight.summary["runtime"],
            "resolved_expected_samples": preflight.resolved_config["train"]["expected_samples"],
            "status": "running",
            "returncode": None,
        }
        Path(preflight.meta_path).write_text(_stringify_json(run_meta), encoding="utf-8")

        env_overrides: dict[str, str] = {}
        env_overrides["PYTHONUNBUFFERED"] = "1"
        if not os.getenv("PYTORCH_CUDA_ALLOC_CONF"):
            env_overrides["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

        return CommandSpec(
            title=f"Train {preflight.summary['run_name']}",
            kind="training",
            command=preflight.command,
            cwd=Path(preflight.cwd),
            env_overrides=env_overrides,
            transcript_path=Path(preflight.transcript_path),
            meta_path=Path(preflight.meta_path),
            expected_outputs=[
                Path(preflight.summary["args_file"]),
                Path(preflight.finetune_card_path),
                Path(preflight.source_snapshot_dir),
                Path(preflight.resolved_config["paths"]["output_dir"]),
            ],
        )

    def _build_finetune_card(self, preflight: TrainingPreflightResult) -> str:
        metadata = preflight.resolved_config.get("metadata", {})
        train_cfg = preflight.resolved_config["train"]
        training_mode = str(metadata.get("training_mode") or "SFT")
        intent = str(metadata.get("intent") or "Supervised finetune run launched from Finetune Studio.")
        reason = str(metadata.get("reason_for_finetune") or "Improve the selected base model using the configured supervised dataset.")
        expected = metadata.get("expected_behavior") or ["Produce a stronger finetuned checkpoint from the selected supervised dataset."]
        notes = metadata.get("notes") or ["This run was launched through Finetune Studio."]
        return (
            "# Finetune Card\n\n"
            "## Expected Checkpoint\n\n"
            f"- Output directory: `{preflight.summary['output_dir']}`\n"
            f"- Base model: `{preflight.summary['model']}`\n"
            f"- Training mode: `{training_mode}`\n"
            f"- Adapter: `{'Yes (LoRA)' if train_cfg['use_lora'] else 'No'}`\n\n"
            "## Data\n\n"
            f"- Train file: `{preflight.summary['train_file']}`\n"
            f"- Source snapshot directory: `{preflight.source_snapshot_dir}`\n\n"
            "## Intent\n\n"
            f"{intent}\n\n"
            "## Reason For Finetune\n\n"
            f"{reason}\n\n"
            "## Expected Behavior\n\n"
            + "\n".join(f"- {item}" for item in expected)
            + "\n\n## Notes\n\n"
            + "\n".join(f"- {item}" for item in notes)
            + "\n"
        )

    def list_runs(self, *, limit: int = 50) -> list[RunRecord]:
        records: list[RunRecord] = []
        if not self.training_runs_root.exists():
            return records
        for meta_path in sorted(self.training_runs_root.glob("**/*.meta.json"), reverse=True):
            try:
                payload = json.loads(meta_path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            records.append(
                RunRecord(
                    meta_path=str(meta_path),
                    started_at=str(payload.get("started_at") or ""),
                    run_name=str(payload.get("run_name") or meta_path.parent.name),
                    args_file=str(payload.get("args_file") or ""),
                    model=str(payload.get("model") or ""),
                    train_file=str(payload.get("train_file") or ""),
                    output_dir=str(payload.get("output_dir") or ""),
                    transcript=str(payload.get("transcript") or ""),
                    finetune_card=str(payload.get("finetune_card") or ""),
                    source_snapshot_dir=str(payload.get("source_snapshot_dir") or ""),
                    status=str(payload.get("status") or "completed"),
                    returncode=payload.get("returncode"),
                    training_mode=str(payload.get("training_mode") or ""),
                )
            )
            if len(records) >= limit:
                break
        records.sort(key=lambda item: item.started_at, reverse=True)
        return records

    def inspect_run(self, meta_path: str | Path) -> RunRecord:
        payload = json.loads(Path(meta_path).read_text(encoding="utf-8-sig"))
        return RunRecord(
            meta_path=str(meta_path),
            started_at=str(payload.get("started_at") or ""),
            run_name=str(payload.get("run_name") or Path(meta_path).parent.name),
            args_file=str(payload.get("args_file") or ""),
            model=str(payload.get("model") or ""),
            train_file=str(payload.get("train_file") or ""),
            output_dir=str(payload.get("output_dir") or ""),
            transcript=str(payload.get("transcript") or ""),
            finetune_card=str(payload.get("finetune_card") or ""),
            source_snapshot_dir=str(payload.get("source_snapshot_dir") or ""),
            status=str(payload.get("status") or "completed"),
            returncode=payload.get("returncode"),
            training_mode=str(payload.get("training_mode") or ""),
        )


class _RunningJob:
    def __init__(self, spec: CommandSpec):
        self.spec = spec
        self.job_id = uuid.uuid4().hex
        self.status = JobStatus.RUNNING
        self.started_at = _utc_now()
        self.ended_at: datetime | None = None
        self.returncode: int | None = None
        self.error = ""
        self._log_lines: list[str] = []
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def append_line(self, line: str) -> None:
        with self._lock:
            self._log_lines.append(line)
            if len(self._log_lines) > 2000:
                self._log_lines = self._log_lines[-2000:]

    def log_text(self) -> str:
        with self._lock:
            return "".join(self._log_lines)

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            job_id=self.job_id,
            title=self.spec.title,
            kind=self.spec.kind,
            status=self.status,
            command=list(self.spec.command),
            started_at=self.started_at,
            ended_at=self.ended_at,
            returncode=self.returncode,
            log_text=self.log_text(),
            meta_path=str(self.spec.meta_path or ""),
            transcript_path=str(self.spec.transcript_path or ""),
            error=self.error,
        )

    def cancel(self) -> None:
        with self._lock:
            proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
        except Exception:
            pass


class JobManager:
    def __init__(self):
        self._jobs: dict[str, _RunningJob] = {}
        self._lock = threading.Lock()

    def _collect_process_metrics(self, pid: int) -> dict[str, Any]:
        metrics: dict[str, Any] = {"pid": pid}
        try:
            import psutil  # type: ignore
        except Exception:
            metrics["psutil_available"] = False
            return metrics

        metrics["psutil_available"] = True
        try:
            process = psutil.Process(pid)
            metrics["status"] = process.status()
            metrics["cpu_percent"] = process.cpu_percent(interval=None)
            metrics["rss_bytes"] = process.memory_info().rss
            metrics["threads"] = process.num_threads()
            child_processes = process.children(recursive=True)
            metrics["child_count"] = len(child_processes)
            child_rss = 0
            for child in child_processes:
                try:
                    child_rss += child.memory_info().rss
                except Exception:
                    continue
            metrics["children_rss_bytes"] = child_rss
        except Exception as exc:
            metrics["psutil_error"] = str(exc)
        return metrics

    def _collect_gpu_metrics(self) -> list[dict[str, Any]]:
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return []
        try:
            completed = subprocess.run(
                [
                    nvidia_smi,
                    "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            return []
        if completed.returncode != 0:
            return []

        rows: list[dict[str, Any]] = []
        for raw_line in (completed.stdout or "").splitlines():
            parts = [part.strip() for part in raw_line.split(",")]
            if len(parts) < 6:
                continue
            rows.append(
                {
                    "index": parts[0],
                    "name": parts[1],
                    "util_gpu": parts[2],
                    "memory_used_mib": parts[3],
                    "memory_total_mib": parts[4],
                    "temperature_c": parts[5],
                }
            )
        return rows

    def _format_telemetry_line(self, *, pid: int, started_at: datetime) -> str:
        elapsed = _format_elapsed((_utc_now() - started_at).total_seconds())
        proc_metrics = self._collect_process_metrics(pid)
        parts = [f"elapsed={elapsed}", f"pid={pid}"]

        if proc_metrics.get("psutil_available"):
            if "cpu_percent" in proc_metrics:
                parts.append(f"cpu={float(proc_metrics['cpu_percent']):.1f}%")
            rss_total = int(proc_metrics.get("rss_bytes", 0)) + int(proc_metrics.get("children_rss_bytes", 0))
            if rss_total > 0:
                parts.append(f"rss={rss_total / (1024 ** 3):.2f} GiB")
            if proc_metrics.get("threads") is not None:
                parts.append(f"threads={proc_metrics['threads']}")
            if proc_metrics.get("child_count") is not None:
                parts.append(f"children={proc_metrics['child_count']}")
            if proc_metrics.get("status"):
                parts.append(f"status={proc_metrics['status']}")
        elif proc_metrics.get("psutil_error"):
            parts.append(f"psutil_error={proc_metrics['psutil_error']}")
        else:
            parts.append("psutil=unavailable")

        gpu_rows = self._collect_gpu_metrics()
        if gpu_rows:
            gpu_parts = []
            for row in gpu_rows:
                gpu_parts.append(
                    f"gpu{row['index']}={row['memory_used_mib']}/{row['memory_total_mib']} MiB util={row['util_gpu']}% temp={row['temperature_c']}C"
                )
            parts.append(" | ".join(gpu_parts))
        else:
            parts.append("gpu_telemetry=unavailable")

        return _studio_log_line("heartbeat " + " | ".join(parts), tag="telemetry")

    def _monitor_job(
        self,
        *,
        job: _RunningJob,
        proc: subprocess.Popen[str],
        emit: Callable[[str], None],
        stop_event: threading.Event,
    ) -> None:
        emit(
            _studio_log_line(
                "Heartbeat enabled every 2s. CPU/RAM uses psutil when available; GPU uses nvidia-smi when available.",
                tag="telemetry",
            )
        )
        try:
            import psutil  # type: ignore

            try:
                psutil.Process(proc.pid).cpu_percent(interval=None)
            except Exception:
                pass
        except Exception:
            pass

        while not stop_event.wait(2.0):
            if proc.poll() is not None:
                break
            emit(self._format_telemetry_line(pid=proc.pid, started_at=job.started_at))

    def launch(self, spec: CommandSpec) -> str:
        job = _RunningJob(spec)
        with self._lock:
            self._jobs[job.job_id] = job
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job.job_id

    def _run_job(self, job: _RunningJob) -> None:
        env = os.environ.copy()
        env.update(job.spec.env_overrides)
        transcript_handle = None
        telemetry_stop = threading.Event()
        telemetry_thread: threading.Thread | None = None

        def emit(line: str) -> None:
            job.append_line(line)
            if transcript_handle is not None:
                transcript_handle.write(line)
                transcript_handle.flush()

        if job.spec.transcript_path is not None:
            job.spec.transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_handle = job.spec.transcript_path.open("a", encoding="utf-8")
        try:
            emit(_studio_log_line(f"Launching job: {job.spec.title}"))
            emit(_studio_log_line(f"Working directory: {job.spec.cwd}"))
            emit(_studio_log_line(f"Command: {' '.join(job.spec.command)}"))
            proc = subprocess.Popen(
                job.spec.command,
                cwd=job.spec.cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            with job._lock:
                job._proc = proc
            emit(_studio_log_line(f"Process started. pid={proc.pid}. Waiting for output..."))
            telemetry_thread = threading.Thread(
                target=self._monitor_job,
                kwargs={
                    "job": job,
                    "proc": proc,
                    "emit": emit,
                    "stop_event": telemetry_stop,
                },
                daemon=True,
            )
            telemetry_thread.start()
            if proc.stdout is not None:
                for line in proc.stdout:
                    emit(line)
            returncode = proc.wait()
            job.returncode = returncode
            if job.status == JobStatus.CANCELLED:
                emit(_studio_log_line("Process cancelled by user."))
            elif returncode == 0:
                job.status = JobStatus.COMPLETED
                emit(_studio_log_line("Process completed successfully."))
            else:
                job.status = JobStatus.FAILED
                job.error = f"Process exited with code {returncode}."
                emit(_studio_log_line(f"Process exited with code {returncode}."))
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            emit(_studio_log_line(str(exc), tag="error"))
        finally:
            telemetry_stop.set()
            if telemetry_thread is not None:
                telemetry_thread.join(timeout=1.0)
            if transcript_handle is not None:
                transcript_handle.close()
            job.ended_at = _utc_now()
            self._finalize_meta(job)

    def _finalize_meta(self, job: _RunningJob) -> None:
        meta_path = job.spec.meta_path
        if meta_path is None or not meta_path.exists():
            return
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        except Exception:
            payload = {}
        payload["status"] = job.status.value
        payload["finished_at"] = _iso_now()
        payload["returncode"] = job.returncode
        meta_path.write_text(_stringify_json(payload), encoding="utf-8")

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = JobStatus.CANCELLED
        job.cancel()

    def get_snapshot(self, job_id: str) -> JobSnapshot | None:
        with self._lock:
            job = self._jobs.get(job_id)
        return None if job is None else job.snapshot()

    def list_snapshots(self) -> list[JobSnapshot]:
        with self._lock:
            jobs = list(self._jobs.values())
        snapshots = [job.snapshot() for job in jobs]
        snapshots.sort(key=lambda item: item.started_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return snapshots
