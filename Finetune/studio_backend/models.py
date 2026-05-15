from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class DatasetSourceType(str, Enum):
    TRAIN_READY_JSONL = "train_ready_jsonl"
    PREPARE_DIALOGUE_DATA = "prepare_dialogue_data"
    BUILD_CANONICAL_DATASET = "build_canonical_dataset"


class JobStatus(str, Enum):
    IDLE = "idle"
    PREFLIGHTING = "preflighting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StudioPreset:
    preset_id: str
    label: str
    description: str
    args_path: Path | None
    config: dict[str, Any]


@dataclass(frozen=True)
class DatasetPreview:
    row_count: int
    message_count_min: int
    message_count_max: int
    preview_rows: list[dict[str, Any]]
    role_counts: dict[str, int]


@dataclass(frozen=True)
class DatasetValidationRequest:
    train_file: str
    model_path: str = ""
    max_seq_length: int = 0
    strict_no_truncation: bool = True
    python_exe: str = ""


@dataclass(frozen=True)
class DatasetValidationResult:
    ok: bool
    train_file: str
    preview: DatasetPreview | None = None
    sample_count: int = 0
    min_tokens: int = 0
    p95_tokens: int = 0
    max_tokens: int = 0
    tokenizer_class: str = ""
    ready: bool = False
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PrepareDialogueRequest:
    input_path: str
    output_path: str
    assistant_role: str = "teacher"
    artifact_style: str = "assistant_turn"
    max_context_messages: int = 12
    min_messages: int = 2
    drop_empty: bool = True
    require_user_before_assistant: bool = True
    merge_consecutive_same_role: bool = True
    strip_role_prefixes: bool = True
    python_exe: str = ""


@dataclass(frozen=True)
class ComposeTrainReadyRequest:
    output_path: str
    user_prompt: str
    assistant_prompt: str
    system_instructions: str = ""
    append: bool = False


@dataclass(frozen=True)
class ComposeTrainReadyResult:
    output_path: str
    row_count: int
    appended: bool


@dataclass(frozen=True)
class BuildCanonicalDatasetRequest:
    builder_id: str
    options: dict[str, Any] = field(default_factory=dict)
    python_exe: str = ""


@dataclass(frozen=True)
class TrainingPreflightRequest:
    config: dict[str, Any]
    allow_cpu: bool = False
    dry_run: bool = True
    python_exe: str = ""


@dataclass(frozen=True)
class TrainingPreflightResult:
    ok: bool
    summary: dict[str, Any]
    resolved_config: dict[str, Any]
    command: list[str]
    python_exe: str
    cwd: str
    transcript_path: str
    meta_path: str
    finetune_card_path: str
    source_snapshot_dir: str
    allow_cpu: bool = False
    source_snapshot_inputs: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class TrainingLaunchRequest:
    preflight: TrainingPreflightResult
    dry_run: bool = False


@dataclass(frozen=True)
class RunRecord:
    meta_path: str
    started_at: str
    run_name: str
    args_file: str
    model: str
    train_file: str
    output_dir: str
    transcript: str
    finetune_card: str
    source_snapshot_dir: str
    status: str
    returncode: int | None = None
    training_mode: str = ""


@dataclass(frozen=True)
class CommandSpec:
    title: str
    kind: str
    command: list[str]
    cwd: Path
    env_overrides: dict[str, str] = field(default_factory=dict)
    transcript_path: Path | None = None
    meta_path: Path | None = None
    expected_outputs: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class JobSnapshot:
    job_id: str
    title: str
    kind: str
    status: JobStatus
    command: list[str]
    started_at: datetime | None
    ended_at: datetime | None
    returncode: int | None
    log_text: str
    meta_path: str
    transcript_path: str
    error: str = ""
