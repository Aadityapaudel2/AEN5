from __future__ import annotations

import copy
import json
import os
import platform
import re
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]

for candidate in (PROJECT_ROOT, APP_DIR):
    value = str(candidate)
    if value not in sys.path:
        sys.path.insert(0, value)

try:
    from PySide6.QtCore import QTimer, Qt, QUrl
    from PySide6.QtGui import QDesktopServices, QTextCursor
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QProgressDialog,
        QPushButton,
        QPlainTextEdit,
        QScrollArea,
        QSpinBox,
        QStackedWidget,
        QTabWidget,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Finetune Studio requires PySide6. Install it in the active environment with "
        "`python -m pip install PySide6`."
    ) from exc

from Finetune.studio_backend import (
    BuildCanonicalDatasetRequest,
    CommandSpec,
    ComposeTrainReadyRequest,
    DatasetSourceType,
    DatasetValidationRequest,
    JobManager,
    JobStatus,
    PrepareDialogueRequest,
    StudioService,
    TrainingLaunchRequest,
    TrainingPreflightRequest,
)
from Finetune.studio_backend.service import DEFAULT_CONFIG
from athena_paths import get_project_tuned_models_dir

try:
    from .paths import get_logs_dir, load_session_state, save_session_state
except ImportError:
    from paths import get_logs_dir, load_session_state, save_session_state

BG = "#08101d"
PANEL = "#0d1830"
ENTRY = "#0a1324"
FG = "#eef3ff"
MUTED = "#90a6d1"
ACCENT_A = "#66c7ff"
ACCENT_B = "#f6ae63"
BAD = "#ff8b8b"
BORDER = "#213555"

STOP_CONDITION_RE = re.compile(
    r"Stop condition:\s*(?P<reason>.+?)\s*\|\s*planned_optimizer_steps=(?P<steps>\d+)"
)
PROGRESS_PLAN_RE = re.compile(r"Training progress plan:\s*steps=(?P<steps>\d+)")
PROGRESS_RE = re.compile(
    r"Training progress:\s*(?:completed\s*)?step=(?P<current>\d+)/(?P<total>\d+)\s*\|\s*elapsed=(?P<elapsed>[0-9:]+)"
    r"(?:\s*\|\s*eta=(?P<eta>[^|]+))?"
    r"(?:\s*\|\s*epoch=(?P<epoch>[^|]+))?"
    r"(?:\s*\|\s*loss=(?P<loss>[^|]+))?"
    r"(?:\s*\|\s*lr=(?P<lr>[^|]+))?"
)

WINDOW_STYLE = f"""
QWidget {{
    background: {BG};
    color: {FG};
    font-family: "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}
QMainWindow {{
    background: {BG};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 16px;
    background: {PANEL};
    top: -1px;
}}
QTabBar::tab {{
    background: {ENTRY};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 10px 18px;
    margin-right: 6px;
}}
QTabBar::tab:selected {{
    background: {PANEL};
    color: {FG};
    border-color: {ACCENT_A};
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 14px;
    margin-top: 16px;
    padding-top: 16px;
    background: {PANEL};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {FG};
}}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget {{
    background: {ENTRY};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 10px;
    selection-background-color: {ACCENT_A};
    selection-color: {BG};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QListWidget:focus {{
    border: 1px solid {ACCENT_A};
}}
QProgressBar {{
    background: {ENTRY};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    text-align: center;
    min-height: 22px;
}}
QProgressBar::chunk {{
    background: {ACCENT_A};
    border-radius: 8px;
}}
QPushButton {{
    background: {ENTRY};
    color: {FG};
    border: 1px solid {ACCENT_A};
    border-radius: 12px;
    padding: 9px 16px;
    min-height: 18px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {PANEL};
    color: {ACCENT_B};
    border-color: {ACCENT_B};
}}
QPushButton:pressed {{
    background: {ACCENT_A};
    color: {BG};
    border-color: {ACCENT_A};
}}
QPushButton:disabled {{
    background: {ENTRY};
    color: {MUTED};
    border: 1px solid {BORDER};
}}
QToolButton {{
    background: transparent;
    color: {ACCENT_A};
    border: 1px solid {ACCENT_A};
    border-radius: 8px;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    font-size: 11px;
    font-weight: 700;
}}
QToolButton:hover {{
    background: {PANEL};
    color: {ACCENT_B};
    border-color: {ACCENT_B};
}}
QListWidget::item {{
    padding: 8px 6px;
    border-bottom: 1px solid {BORDER};
}}
QListWidget::item:selected {{
    background: {PANEL};
    color: {FG};
    border: 1px solid {ACCENT_A};
    border-radius: 8px;
}}
QCheckBox {{
    background: transparent;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid {BORDER};
    background: {ENTRY};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_A};
    border-color: {ACCENT_A};
}}
QLabel#muted {{
    color: {MUTED};
}}
QLabel#title {{
    color: {FG};
    font-size: 30px;
    font-weight: 700;
}}
"""

PATH_FIELDS = [
    {"key": "model_path", "label": "Base Model", "browse": "dir"},
    {"key": "train_file", "label": "Train File", "browse": "file"},
    {"key": "output_dir", "label": "Output Directory", "browse": "dir"},
    {"key": "resume_from_checkpoint", "label": "Resume Checkpoint", "browse": "dir"},
]

METADATA_FIELDS = [
    {"key": "run_name", "label": "Run Name", "type": "text"},
    {"key": "training_mode", "label": "Training Mode", "type": "text"},
    {"key": "intent", "label": "Intent", "type": "text"},
    {"key": "reason_for_finetune", "label": "Reason For Finetune", "type": "multiline"},
    {"key": "expected_behavior", "label": "Expected Behavior", "type": "list"},
    {"key": "notes", "label": "Notes", "type": "list"},
    {"key": "source_snapshot_files", "label": "Extra Source Snapshots", "type": "list"},
]

ACCELERATE_FIELDS = [
    {"key": "num_processes", "label": "Processes", "type": "int", "min": 1, "max": 128},
    {"key": "num_machines", "label": "Machines", "type": "int", "min": 1, "max": 32},
    {
        "key": "mixed_precision",
        "label": "Mixed Precision",
        "type": "choice",
        "choices": ["no", "fp16", "bf16"],
    },
    {
        "key": "dynamo_backend",
        "label": "Dynamo Backend",
        "type": "choice",
        "choices": ["no", "eager", "inductor"],
    },
]

TRAIN_FIELDS = [
    {"key": "max_seq_length", "label": "Max Seq Length", "type": "int", "min": 128, "max": 32768},
    {"key": "expected_samples", "label": "Expected Samples", "type": "int", "min": 0, "max": 100000000},
    {"key": "strict_no_truncation", "label": "Strict No Truncation", "type": "bool"},
    {"key": "per_device_train_batch_size", "label": "Batch Size", "type": "int", "min": 1, "max": 128},
    {"key": "gradient_accumulation_steps", "label": "Grad Accumulation", "type": "int", "min": 1, "max": 4096},
    {"key": "learning_rate", "label": "Learning Rate", "type": "float", "min": 0.0, "max": 10.0, "step": 0.00001, "decimals": 8},
    {"key": "num_train_epochs", "label": "Epochs", "type": "float", "min": 0.0, "max": 1000.0, "step": 0.1, "decimals": 3},
    {"key": "max_steps", "label": "Max Steps", "type": "int", "min": 0, "max": 100000000},
    {"key": "warmup_ratio", "label": "Warmup Ratio", "type": "float", "min": 0.0, "max": 1.0, "step": 0.01, "decimals": 4},
    {
        "key": "lr_scheduler_type",
        "label": "LR Scheduler",
        "type": "choice",
        "choices": ["linear", "cosine", "constant", "cosine_with_restarts", "polynomial"],
    },
    {"key": "optim", "label": "Optimizer", "type": "text"},
    {"key": "optim_args", "label": "Optimizer Args", "type": "text"},
    {"key": "optim_target_modules", "label": "Optimizer Target Modules", "type": "text"},
    {"key": "torch_empty_cache_steps", "label": "Empty Cache Steps", "type": "int", "min": 0, "max": 1000000},
    {"key": "weight_decay", "label": "Weight Decay", "type": "float", "min": 0.0, "max": 10.0, "step": 0.001, "decimals": 4},
    {"key": "max_grad_norm", "label": "Max Grad Norm", "type": "float", "min": 0.0, "max": 100.0, "step": 0.1, "decimals": 4},
    {"key": "logging_steps", "label": "Logging Steps", "type": "int", "min": 1, "max": 1000000},
    {"key": "save_steps", "label": "Save Steps", "type": "int", "min": 1, "max": 100000000},
    {"key": "save_total_limit", "label": "Save Total Limit", "type": "int", "min": 1, "max": 1024},
    {"key": "save_only_model", "label": "Save Only Model", "type": "bool"},
    {"key": "gradient_checkpointing", "label": "Gradient Checkpointing", "type": "bool"},
    {"key": "seed", "label": "Seed", "type": "int", "min": 0, "max": 2147483647},
    {"key": "use_lora", "label": "Use LoRA", "type": "bool"},
    {"key": "load_in_4bit", "label": "Load In 4-bit", "type": "bool"},
    {"key": "lora_r", "label": "LoRA Rank", "type": "int", "min": 1, "max": 4096},
    {"key": "lora_alpha", "label": "LoRA Alpha", "type": "int", "min": 1, "max": 4096},
    {"key": "lora_dropout", "label": "LoRA Dropout", "type": "float", "min": 0.0, "max": 1.0, "step": 0.01, "decimals": 4},
    {"key": "lora_target_modules", "label": "LoRA Target Modules", "type": "text"},
]

BUILDERS = [
    ("verified_sft", "Verified Math+Logic Prep"),
    ("training_dataset_0", "Identity Data Prep"),
    ("chunked_sft", "Chunked SFT Prep"),
    ("orchestrator_v1", "Orchestrator Data Prep"),
]

PATH_HELP = {
    "model_path": "Path to the base model or tokenizer directory used for training and token checks. Relative paths are resolved from the repo root.",
    "train_file": "Train-ready JSONL in chat-SFT format. Each line must contain a non-empty `messages` list. Relative paths are resolved from the repo root.",
    "output_dir": "Directory where checkpoints, adapters, cards, and run artifacts will be written. Relative paths are resolved from the repo root, except `models/tuned/...` which maps to the tuned-models root.",
    "resume_from_checkpoint": "Optional checkpoint directory to resume an interrupted run. Relative paths are resolved from the repo root.",
}

METADATA_HELP = {
    "run_name": "Human-readable name for the run. Used in run history and log folders.",
    "training_mode": "Short label for the training strategy, such as Full SFT or QLoRA Adapter.",
    "intent": "One-line statement describing what this finetune is trying to achieve.",
    "reason_for_finetune": "Why the model is being finetuned right now. This text is written into the finetune card.",
    "expected_behavior": "One expected behavior per line. These become checklist items in the finetune card.",
    "notes": "Operator notes for this run. One line per note.",
    "source_snapshot_files": "Optional extra files to snapshot into the run output. One path per line.",
}

ACCELERATE_HELP = {
    "num_processes": "Number of parallel training processes to launch through Accelerate. For most single-GPU local runs this stays at 1.",
    "num_machines": "Number of machines participating in the run. Keep this at 1 unless you are intentionally doing distributed multi-machine training.",
    "mixed_precision": "Accelerate launcher precision. In most local runs you should keep this aligned with Train Precision below so the launcher and trainer agree.",
    "dynamo_backend": "PyTorch compile backend used by Accelerate. Start with `no` unless you are intentionally testing compiled training.",
}

TRAIN_HELP = {
    "max_seq_length": "Maximum token length allowed per training row. Bigger values let you train on longer examples, but they raise VRAM use and slow training.",
    "expected_samples": "Expected row count. Use 0 to let preflight derive the dataset size automatically. The studio will usually update this from the real dataset.",
    "strict_no_truncation": "If enabled, preflight fails when any row exceeds max sequence length. This is safer when you do not want silent clipping.",
    "per_device_train_batch_size": "Batch size per process before gradient accumulation. Larger values can speed training, but they also increase VRAM use.",
    "gradient_accumulation_steps": "Number of micro-batches to accumulate before one optimizer step. This is how you simulate a larger effective batch without fitting it all in VRAM at once.",
    "learning_rate": "Optimizer learning rate. Too high can destabilize training. Too low can make training very slow or ineffective.",
    "num_train_epochs": "Number of passes over the dataset. Can be fractional.",
    "max_steps": "Hard cap on optimizer steps. Use 0 to disable and rely on epochs.",
    "warmup_ratio": "Fraction of total steps used for warmup.",
    "lr_scheduler_type": "Learning-rate schedule used during training.",
    "optim": "Optimizer name passed directly to the trainer.",
    "optim_args": "Raw optimizer argument string for advanced optimizer setups.",
    "optim_target_modules": "Optional module list for optimizers that support targeted optimization.",
    "torch_empty_cache_steps": "If non-zero, periodically asks PyTorch to clear cached CUDA memory.",
    "weight_decay": "Weight decay coefficient.",
    "max_grad_norm": "Gradient clipping threshold.",
    "logging_steps": "Emit training logs every N optimizer steps.",
    "save_steps": "Write checkpoints every N optimizer steps.",
    "save_total_limit": "Maximum number of retained checkpoints.",
    "save_only_model": "If enabled, save model-focused artifacts rather than full trainer state only.",
    "gradient_checkpointing": "Trades compute for memory by recomputing activations during backprop. It is commonly enabled when VRAM is limited.",
    "seed": "Random seed used for reproducibility.",
    "use_lora": "Enable LoRA adapters instead of dense full-model tuning. This is usually the easier and cheaper option when VRAM is limited.",
    "load_in_4bit": "Load the base model in 4-bit. This reduces VRAM use, but it only makes sense with LoRA-style adapter training.",
    "lora_r": "LoRA rank. Higher rank increases adapter capacity and usually memory use.",
    "lora_alpha": "LoRA scaling factor. Often paired with rank when tuning adapter strength.",
    "lora_dropout": "Dropout applied inside LoRA layers. Small values are common; large values can weaken learning.",
    "lora_target_modules": "Comma-separated module names to target with LoRA. Leave this at the known-good default unless you intentionally want a different adapter layout.",
}

SPECIAL_HELP = {
    "python_exe": "Python interpreter used for validation, prepare steps, builders, and training launch.",
    "precision_mode": "Mutually exclusive train precision. This controls `train.bf16` and `train.fp16` so they cannot both be enabled.",
    "preset": "Preset profiles fill the form with a known working starting point. Pick one, then click Load Selected Preset to apply it over the current form.",
    "args_file": "Load a finetune args JSON file directly. The studio merges it with safe defaults, then fills the form from that file.",
    "optimizer_choice": "Known optimizer presets. Choose Custom only when you need to type an optimizer name manually.",
    "custom_optimizer": "Only used when Optimizer Preset is set to Custom.",
    "train_ready_path": "The currently selected train-ready JSONL file used by validation and can be copied into the training path.",
    "compose_output_path": "Target JSONL that will receive manually composed user/assistant training rows. If you use a relative path, it is resolved from the repo root.",
    "compose_system_instructions": "Optional system message placed before the user and assistant messages in the row. Leave it blank if you do not want one.",
    "compose_user_prompt": "The user message for a single train-ready SFT row.",
    "compose_assistant_prompt": "The assistant message paired with the user prompt for a single train-ready SFT row.",
}

CHOICE_DETAILS = {
    "mixed_precision": {
        "no": "Uses full 32-bit math. Safest and easiest to debug, but usually the slowest and highest-memory option.",
        "fp16": "Uses half precision float16. Common on older NVIDIA setups, but can be less numerically stable than BF16.",
        "bf16": "Uses bfloat16. Usually the best first choice on modern NVIDIA hardware because it keeps memory lower without as many FP16 stability issues.",
    },
    "dynamo_backend": {
        "no": "Disables torch.compile. Best compatibility and usually the right first choice when you just want the run to work.",
        "eager": "Runs through Dynamo without aggressive compilation. Mostly useful for debugging or compatibility checks, not for major speed gains.",
        "inductor": "Compiles parts of the training graph for speed. It can improve steady-state performance, but adds startup compile time and sometimes breaks on certain models or drivers.",
    },
    "lr_scheduler_type": {
        "linear": "Warm up, then decay the learning rate in a straight line. Good general default.",
        "cosine": "Smooth cosine-shaped decay. Often used when you want a gentler late-stage decay.",
        "constant": "Keeps the learning rate flat after warmup. Simple, but usually less forgiving.",
        "cosine_with_restarts": "Cosine decay with periodic restarts. More advanced and rarely needed for a first run.",
        "polynomial": "Polynomial decay curve. Mostly for specialized training recipes.",
    },
    "precision_mode": {
        "bf16": "Best first choice on modern GPUs that support BF16. Lower memory use with better stability than FP16.",
        "fp16": "Useful on GPUs that do not support BF16 well. Faster/lower-memory than FP32, but more sensitive to instability.",
        "no": "Turns off mixed train precision and keeps full precision. Safest, but slower and heavier on VRAM.",
    },
    "optimizer_choice": {
        "adamw_torch": "Best local default. Stable, well understood, and the safest place to start.",
        "adamw_8bit": "Lower optimizer memory use. Useful when VRAM is tight.",
        "paged_adamw_8bit": "Another lower-memory 8-bit AdamW variant that can behave better on constrained systems.",
        "galore_adamw": "Advanced memory-efficient dense optimizer. Not a beginner default.",
        "apollo_adamw": "Advanced optimizer family for specific workflows. Use only if you know why you need it.",
        "__custom__": "Type the raw optimizer name manually. Only for advanced users or custom trainer support.",
    },
}

OPTIMIZER_OPTIONS = [
    ("Best Local Default (adamw_torch)", "adamw_torch"),
    ("8-bit AdamW", "adamw_8bit"),
    ("Paged AdamW 8-bit", "paged_adamw_8bit"),
    ("GaLore AdamW", "galore_adamw"),
    ("Apollo AdamW", "apollo_adamw"),
    ("Custom", "__custom__"),
]

DEFAULT_VALUE_BY_KEY: dict[str, Any] = {}
for _section in ("paths", "metadata", "accelerate", "train"):
    for _key, _value in DEFAULT_CONFIG.get(_section, {}).items():
        DEFAULT_VALUE_BY_KEY[_key] = _value


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
    return cleaned or "job"


def _format_default_value(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    if isinstance(value, list):
        return "Empty" if not value else ", ".join(str(item) for item in value)
    if value == "":
        return "Empty"
    return str(value)


def _field_help(help_map: dict[str, str], spec: dict[str, Any], key_override: str | None = None) -> str:
    key = key_override or spec["key"]
    parts: list[str] = []
    base = help_map.get(key, "").strip()
    if base:
        parts.append(f"What it does:\n{base}")
    if key in DEFAULT_VALUE_BY_KEY:
        parts.append(f"Default:\n{_format_default_value(DEFAULT_VALUE_BY_KEY[key])}")
    if "choices" in spec:
        parts.append("Choices:\n" + ", ".join(str(choice) for choice in spec["choices"]))
        details = CHOICE_DETAILS.get(key)
        if details:
            parts.append(
                "Choice Notes:\n"
                + "\n".join(f"- {choice}: {details[choice]}" for choice in spec["choices"] if choice in details)
            )
    if "min" in spec or "max" in spec:
        parts.append(f"Range:\n{spec.get('min', '-inf')} to {spec.get('max', 'inf')}")
    return "\n\n".join(parts).strip()


def _special_help_text(key: str) -> str:
    base = SPECIAL_HELP.get(key, "").strip()
    parts = [f"What it does:\n{base}"] if base else []
    if key == "precision_mode":
        parts.append("Default:\nBF16")
        parts.append("Choices:\nBF16, FP16, FP32 / None")
        details = CHOICE_DETAILS.get("precision_mode", {})
        parts.append(
            "Choice Notes:\n"
            + "\n".join(
                f"- {label}: {details[value]}"
                for label, value in (("BF16", "bf16"), ("FP16", "fp16"), ("FP32 / None", "no"))
                if value in details
            )
        )
    if key == "optimizer_choice":
        parts.append("Default:\nBest Local Default (adamw_torch)")
        parts.append("Choices:\n" + ", ".join(label for label, _ in OPTIMIZER_OPTIONS))
        details = CHOICE_DETAILS.get("optimizer_choice", {})
        parts.append(
            "Choice Notes:\n"
            + "\n".join(f"- {label}: {details[value]}" for label, value in OPTIMIZER_OPTIONS if value in details)
        )
    if key == "python_exe":
        parts.append("Default:\nAuto-detected from the active venv or project .venv")
        parts.append("Why it matters:\nThe studio uses this Python for dataset inspection, builder scripts, preflight checks, and the actual training launch. If this points to the wrong environment, packages and CUDA detection can fail.")
    if key == "args_file":
        parts.append("What gets loaded:\nThe studio reads the JSON file, fills in any missing keys with studio defaults, and then applies the result into the form.")
    return "\n\n".join(parts).strip()


def _recommended_max_seq_length(max_tokens: int) -> int:
    if max_tokens <= 0:
        return 2048
    canonical_sizes = [512, 768, 1024, 1536, 2048, 3072, 4096, 6144, 8192, 12288, 16384, 24576, 32768]
    for candidate in canonical_sizes:
        if max_tokens <= candidate:
            return candidate
    rounded = ((max_tokens + 255) // 256) * 256
    return min(max(rounded, max_tokens), 32768)


def _safe_relative_path(base: Path, target: Path) -> str | None:
    try:
        return target.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return None


def _display_path(path_value: str | Path) -> str:
    raw = str(path_value).strip()
    if not raw:
        return ""
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return Path(raw.replace("\\", "/")).as_posix()
    resolved = candidate.resolve()
    relative_to_project = _safe_relative_path(PROJECT_ROOT, resolved)
    if relative_to_project is not None:
        return relative_to_project
    tuned_root_env = os.getenv("ATHENA_TUNED_MODELS_ROOT", "").strip()
    tuned_root = Path(tuned_root_env).expanduser() if tuned_root_env else get_project_tuned_models_dir()
    relative_to_tuned = _safe_relative_path(tuned_root, resolved)
    if relative_to_tuned is not None:
        suffix = relative_to_tuned.strip("/")
        return f"models/tuned/{suffix}" if suffix else "models/tuned"
    return str(resolved)


def _blank(value: str | Path | None) -> str:
    return str(value).strip() if value is not None else ""


class FinetuneStudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.service = StudioService(PROJECT_ROOT)
        self.jobs = JobManager()
        self.presets = {preset.preset_id: preset for preset in self.service.list_presets()}
        self.state = load_session_state()
        self.current_job_id = ""
        self.last_preflight = None
        self._completed_jobs: set[str] = set()
        self._loading_state = True
        self._last_displayed_job_log = ""
        self.loaded_args_path = ""
        self.preferred_run_meta_path = ""
        self.run_records: dict[str, Any] = {}
        self.path_widgets: dict[str, QWidget] = {}
        self.meta_widgets: dict[str, QWidget] = {}
        self.accelerate_widgets: dict[str, QWidget] = {}
        self.train_widgets: dict[str, QWidget] = {}
        self.special_widgets: dict[str, QWidget] = {}
        self.compose_widgets: dict[str, QWidget] = {}
        self.prepare_widgets: dict[str, QWidget] = {}
        self.build_widgets: dict[str, QWidget] = {}
        self.selected_train_file_path = ""

        self.setWindowTitle("AEN Finetune Studio")
        self.resize(1440, 920)
        self._build_ui()
        self._apply_style()
        self._restore_session()
        self.refresh_environment()
        self.refresh_runs()
        self._loading_state = False

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self._poll_jobs)
        self.poll_timer.start()

    def _apply_style(self) -> None:
        self.setStyleSheet(WINDOW_STYLE)

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("AEN Finetune Studio")
        title.setObjectName("title")
        subtitle = QLabel(
            "Developed by NeoHMLabs. Local finetuning software for composing data, configuring arguments, and running train jobs."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.compose_tab = self._build_compose_tab()
        self.data_tab = self._build_data_tab()
        self.arguments_tab = self._build_arguments_tab()
        self.jobs_tab = self._build_jobs_tab()
        self.home_tab = self._build_home_tab()
        self.tabs.addTab(self.home_tab, "Overview")
        self.tabs.addTab(self.compose_tab, "Compose")
        self.tabs.addTab(self.data_tab, "Data")
        self.tabs.addTab(self.arguments_tab, "Arguments")
        self.tabs.addTab(self.jobs_tab, "Jobs")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def _build_home_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        welcome_box = QGroupBox("Workflow")
        welcome_layout = QVBoxLayout(welcome_box)
        welcome_text = QLabel(
            "Use one path through the studio: compose or import data, load a preset, review arguments, then run preflight and launch training."
        )
        welcome_text.setObjectName("muted")
        welcome_text.setWordWrap(True)
        welcome_layout.addWidget(welcome_text)
        shortcuts = QWidget()
        shortcuts_layout = QHBoxLayout(shortcuts)
        shortcuts_layout.setContentsMargins(0, 0, 0, 0)
        shortcuts_layout.setSpacing(10)
        compose_button = QPushButton("Compose Data")
        compose_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.compose_tab))
        shortcuts_layout.addWidget(compose_button)
        import_button = QPushButton("Import Data")
        import_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.data_tab))
        shortcuts_layout.addWidget(import_button)
        args_button = QPushButton("Open Arguments")
        args_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.arguments_tab))
        shortcuts_layout.addWidget(args_button)
        jobs_button = QPushButton("Open Jobs")
        jobs_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.jobs_tab))
        shortcuts_layout.addWidget(jobs_button)
        shortcuts_layout.addStretch(1)
        welcome_layout.addWidget(shortcuts)
        layout.addWidget(welcome_box)

        content_row = QHBoxLayout()
        content_row.setSpacing(16)

        env_box = QGroupBox("Environment")
        env_layout = QVBoxLayout(env_box)
        self.environment_text = QPlainTextEdit()
        self.environment_text.setReadOnly(True)
        self.environment_text.setMinimumHeight(220)
        env_layout.addWidget(self.environment_text)
        refresh_button = QPushButton("Refresh Environment")
        refresh_button.clicked.connect(self.refresh_environment)
        env_layout.addWidget(self._action_row(refresh_button))
        content_row.addWidget(env_box, 4)

        recent_box = QGroupBox("Recent Runs")
        recent_layout = QVBoxLayout(recent_box)
        self.home_runs_list = QListWidget()
        self.home_runs_list.setMinimumHeight(220)
        self.home_runs_list.itemSelectionChanged.connect(self._show_selected_run_details)
        self.home_runs_list.itemDoubleClicked.connect(lambda *_args: self._show_selected_run_details())
        recent_layout.addWidget(self.home_runs_list)
        open_recent = QPushButton("Inspect Selected Run")
        open_recent.clicked.connect(lambda *_args: self._show_selected_run_details())
        clear_recent = QPushButton("Clear Selection")
        clear_recent.clicked.connect(self._clear_run_selection)
        recent_layout.addWidget(self._action_row(open_recent, clear_recent))
        content_row.addWidget(recent_box, 5)

        layout.addLayout(content_row, 1)

        details_box = QGroupBox("Run Details")
        details_layout = QVBoxLayout(details_box)
        self.run_details = QPlainTextEdit()
        self.run_details.setReadOnly(True)
        self.run_details.setMinimumHeight(260)
        details_layout.addWidget(self.run_details, 1)

        buttons = QHBoxLayout()
        open_output = QPushButton("Open Output")
        open_output.clicked.connect(self._open_selected_run_output)
        buttons.addWidget(open_output)
        open_transcript = QPushButton("Open Transcript")
        open_transcript.clicked.connect(self._open_selected_run_transcript)
        buttons.addWidget(open_transcript)
        open_card = QPushButton("Open Card")
        open_card.clicked.connect(self._open_selected_run_card)
        buttons.addWidget(open_card)
        open_args = QPushButton("Open Args File")
        open_args.clicked.connect(self._open_selected_run_args_file)
        buttons.addWidget(open_args)
        open_snapshot = QPushButton("Open Source Snapshot")
        open_snapshot.clicked.connect(self._open_selected_run_snapshot)
        buttons.addWidget(open_snapshot)
        details_layout.addLayout(buttons)
        layout.addWidget(details_box, 1)
        return tab

    def _build_compose_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        compose_box = QGroupBox("Compose Train-Ready JSONL")
        compose_form = QFormLayout(compose_box)
        self.compose_widgets["output_path"], row = self._make_path_row("save_file")
        compose_output_help = _special_help_text("compose_output_path")
        self.compose_widgets["output_path"].setToolTip(compose_output_help)
        self.compose_widgets["output_path"].textChanged.connect(lambda *_args: self._refresh_compose_preview())
        compose_form.addRow(
            self._make_label_widget("Target Data File", compose_output_help),
            row,
        )

        self.compose_widgets["system_instructions"] = QPlainTextEdit()
        self.compose_widgets["system_instructions"].setMaximumHeight(110)
        compose_system_help = _special_help_text("compose_system_instructions")
        self.compose_widgets["system_instructions"].setToolTip(compose_system_help)
        compose_form.addRow(
            self._make_label_widget("System Instructions", compose_system_help),
            self.compose_widgets["system_instructions"],
        )

        self.compose_widgets["user_prompt"] = QPlainTextEdit()
        self.compose_widgets["user_prompt"].setMaximumHeight(170)
        compose_user_help = _special_help_text("compose_user_prompt")
        self.compose_widgets["user_prompt"].setToolTip(compose_user_help)
        compose_form.addRow(
            self._make_label_widget("User Prompt", compose_user_help),
            self.compose_widgets["user_prompt"],
        )

        self.compose_widgets["assistant_prompt"] = QPlainTextEdit()
        self.compose_widgets["assistant_prompt"].setMaximumHeight(220)
        compose_assistant_help = _special_help_text("compose_assistant_prompt")
        self.compose_widgets["assistant_prompt"].setToolTip(compose_assistant_help)
        compose_form.addRow(
            self._make_label_widget("Assistant Prompt", compose_assistant_help),
            self.compose_widgets["assistant_prompt"],
        )

        compose_buttons = QWidget()
        compose_buttons_layout = QHBoxLayout(compose_buttons)
        compose_buttons_layout.setContentsMargins(0, 0, 0, 0)
        build_button = QPushButton("Build Train-Ready JSONL")
        build_button.clicked.connect(lambda: self._write_composed_train_ready(append=False))
        compose_buttons_layout.addWidget(build_button)
        append_button = QPushButton("Append To Data")
        append_button.clicked.connect(lambda: self._write_composed_train_ready(append=True))
        compose_buttons_layout.addWidget(append_button)
        send_button = QPushButton("Use Compose File For Training")
        send_button.clicked.connect(self._send_compose_file_to_training)
        compose_buttons_layout.addWidget(send_button)
        clear_button = QPushButton("Clear Prompt Boxes")
        clear_button.clicked.connect(self._clear_compose_prompts)
        compose_buttons_layout.addWidget(clear_button)
        compose_form.addRow(compose_buttons)

        self.compose_status = QLabel("Compose an optional system message plus a user/assistant pair, then write it into the selected JSONL file.")
        self.compose_status.setObjectName("muted")
        self.compose_status.setWordWrap(True)
        compose_form.addRow(self.compose_status)
        layout.addWidget(compose_box)

        format_box = QGroupBox("Dataset Preview")
        format_layout = QVBoxLayout(format_box)
        self.compose_preview = QPlainTextEdit()
        self.compose_preview.setReadOnly(True)
        self.compose_preview.setMinimumHeight(320)
        format_layout.addWidget(self.compose_preview)
        layout.addWidget(format_box, 1)
        return tab

    def _build_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        self.data_mode_combo = QComboBox()
        self.data_mode_combo.addItem("Import Existing JSONL", DatasetSourceType.TRAIN_READY_JSONL.value)
        self.data_mode_combo.addItem("Prepare Dialogue Data", DatasetSourceType.PREPARE_DIALOGUE_DATA.value)
        self.data_mode_combo.addItem("Build Dataset", DatasetSourceType.BUILD_CANONICAL_DATASET.value)
        self.data_mode_combo.currentIndexChanged.connect(self._refresh_data_mode)

        self.data_stack = QStackedWidget()
        self.data_stack.addWidget(QWidget())
        self.data_stack.addWidget(self._build_prepare_panel())
        self.data_stack.addWidget(self._build_build_panel())
        self.data_stack.hide()

        import_box = self._build_train_ready_panel()
        layout.addWidget(import_box)

        format_box = QGroupBox("Required JSONL Format")
        format_layout = QVBoxLayout(format_box)
        format_hint = QLabel(
            "Use this tab when you already have a finished dataset file. If you want to write rows manually one pair at a time, use Compose."
        )
        format_hint.setObjectName("muted")
        format_hint.setWordWrap(True)
        format_layout.addWidget(format_hint)
        format_example = QPlainTextEdit()
        format_example.setReadOnly(True)
        format_example.setMinimumHeight(170)
        format_example.setPlainText(
            '{\n'
            '  "messages": [\n'
            '    {"role": "system", "content": "Optional system message"},\n'
            '    {"role": "user", "content": "User prompt"},\n'
            '    {"role": "assistant", "content": "Assistant reply"}\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- One JSON object per line\n"
            "- Each row must contain a non-empty messages list\n"
            "- A system message is optional, not required\n"
            "- Allowed roles: system, user, assistant\n"
            "- Every message must have non-empty content"
        )
        format_layout.addWidget(format_example)
        layout.addWidget(format_box)

        preview_box = QGroupBox("Dataset Preview")
        preview_layout = QVBoxLayout(preview_box)
        self.dataset_preview = QPlainTextEdit()
        self.dataset_preview.setReadOnly(True)
        self.dataset_preview.setMinimumHeight(260)
        preview_layout.addWidget(self.dataset_preview)
        layout.addWidget(preview_box, 1)
        return tab

    def _build_train_ready_panel(self) -> QWidget:
        box = QGroupBox("Import Existing Train-Ready JSONL")
        form = QFormLayout(box)
        import_hint = QLabel(
            "Bring a finished chat-SFT JSONL file into the studio, inspect it, and point training at it. If you want to create rows manually, use Compose instead."
        )
        import_hint.setObjectName("muted")
        import_hint.setWordWrap(True)
        form.addRow(import_hint)

        self.train_ready_path_edit, row = self._make_path_row("file")
        train_ready_help = _special_help_text("train_ready_path")
        self.train_ready_path_edit.setToolTip(train_ready_help)
        self.train_ready_path_edit.textChanged.connect(self._on_train_ready_path_changed)
        form.addRow(self._make_label_widget("Dataset File", train_ready_help), row)

        self.dataset_hint = QLabel()
        self.dataset_hint.setObjectName("muted")
        self.dataset_hint.setWordWrap(True)
        form.addRow(self.dataset_hint)

        validation_note = QLabel(
            "Validate Current Dataset only reads the selected JSONL file, checks its structure, and reports whether it looks usable for training. It does not append, rewrite, or repair the file."
        )
        validation_note.setObjectName("muted")
        validation_note.setWordWrap(True)
        form.addRow(validation_note)

        validate_button = QPushButton("Validate Current Dataset")
        validate_button.clicked.connect(self._validate_selected_data)
        import_button = QPushButton("Use Selected File For Training")
        import_button.clicked.connect(lambda: self._sync_train_file_from_data(self.train_ready_path_edit.text().strip()))
        form.addRow(self._action_row(import_button, validate_button))
        return box

    def _build_prepare_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.prepare_widgets["input_path"], row = self._make_path_row("file")
        form.addRow("Input Dialogue JSONL", row)
        self.prepare_widgets["output_path"], row = self._make_path_row("save_file")
        form.addRow("Output SFT JSONL", row)
        self.prepare_widgets["assistant_role"] = QLineEdit()
        form.addRow("Assistant Role", self.prepare_widgets["assistant_role"])
        self.prepare_widgets["artifact_style"] = QComboBox()
        self.prepare_widgets["artifact_style"].addItems(["assistant_turn", "full_dialogue"])
        form.addRow("Artifact Style", self.prepare_widgets["artifact_style"])
        self.prepare_widgets["max_context_messages"] = self._spin_box(1, 128)
        form.addRow("Max Context Messages", self.prepare_widgets["max_context_messages"])
        self.prepare_widgets["min_messages"] = self._spin_box(1, 128)
        form.addRow("Min Messages", self.prepare_widgets["min_messages"])
        for key, label in (
            ("drop_empty", "Drop Empty"),
            ("require_user_before_assistant", "Require User Before Assistant"),
            ("merge_consecutive_same_role", "Merge Same Role"),
            ("strip_role_prefixes", "Strip Role Prefixes"),
        ):
            checkbox = QCheckBox()
            self.prepare_widgets[key] = checkbox
            form.addRow(label, checkbox)
        run_button = QPushButton("Run Prepare")
        run_button.clicked.connect(self._launch_prepare_job)
        form.addRow(self._action_row(run_button))
        return panel

    def _build_build_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        selector_row = QHBoxLayout()
        self.builder_combo = QComboBox()
        for builder_id, label in BUILDERS:
            self.builder_combo.addItem(label, builder_id)
        self.builder_combo.currentIndexChanged.connect(self._refresh_builder_stack)
        selector_row.addWidget(QLabel("Builder"))
        selector_row.addWidget(self.builder_combo, 1)
        layout.addLayout(selector_row)

        self.builder_stack = QStackedWidget()
        self.builder_stack.addWidget(self._build_verified_builder_panel())
        self.builder_stack.addWidget(self._build_dataset0_builder_panel())
        self.builder_stack.addWidget(self._build_chunked_builder_panel())
        self.builder_stack.addWidget(self._build_orchestrator_builder_panel())
        layout.addWidget(self.builder_stack)

        run_button = QPushButton("Run Dataset Builder")
        run_button.clicked.connect(self._launch_build_job)
        layout.addWidget(self._action_row(run_button))
        return panel

    def _build_verified_builder_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        hint = QLabel("Prepare the verified math and logic train-ready JSONL using the existing AEN data tool.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)
        return panel

    def _build_dataset0_builder_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        hint = QLabel("Prepare the identity-style dataset 0 corpus using the existing AEN data tool.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)
        return panel

    def _build_chunked_builder_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.build_widgets["source"], row = self._make_path_row("file")
        form.addRow("Source Dataset", row)
        self.build_widgets["output"], row = self._make_path_row("save_file")
        form.addRow("Chunked Output", row)
        self.build_widgets["manifest_output"], row = self._make_path_row("save_file")
        form.addRow("Manifest Output", row)
        self.build_widgets["model"], row = self._make_path_row("dir")
        form.addRow("Tokenizer Model", row)
        self.build_widgets["max_seq_length"] = self._spin_box(128, 32768)
        form.addRow("Max Seq Length", self.build_widgets["max_seq_length"])
        for key, label in (
            ("drop_overlong_base", "Drop Overlong Base Rows"),
            ("drop_unchunkable", "Drop Unchunkable"),
        ):
            checkbox = QCheckBox()
            self.build_widgets[key] = checkbox
            form.addRow(label, checkbox)
        return panel

    def _build_orchestrator_builder_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.build_widgets["model_name_or_path"], row = self._make_path_row("dir")
        form.addRow("Tokenizer Model", row)
        self.build_widgets["orchestrator_max_seq_length"] = self._spin_box(128, 32768)
        form.addRow("Max Seq Length", self.build_widgets["orchestrator_max_seq_length"])
        for key, label in (
            ("bootstrap", "Bootstrap"),
            ("overwrite_bootstrap", "Overwrite Bootstrap"),
            ("write", "Write Dataset Files"),
            ("validate", "Validate Dataset Files"),
            ("token_stats", "Token Stats"),
        ):
            checkbox = QCheckBox()
            self.build_widgets[key] = checkbox
            form.addRow(label, checkbox)
        return panel

    def _build_arguments_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        header_box = QGroupBox("Profiles")
        header_layout = QFormLayout(header_box)
        self.preset_combo = QComboBox()
        for preset in self.presets.values():
            self.preset_combo.addItem(preset.label, preset.preset_id)
        self.preset_combo.currentIndexChanged.connect(self._update_preset_summary)
        preset_help = _special_help_text("preset")
        header_layout.addRow(self._make_label_widget("Preset", preset_help), self.preset_combo)

        self.preset_summary = QLabel()
        self.preset_summary.setObjectName("muted")
        self.preset_summary.setWordWrap(True)
        header_layout.addRow(self.preset_summary)

        self.args_file_edit, args_row = self._make_path_row("file")
        args_help = _special_help_text("args_file")
        self.args_file_edit.setToolTip(args_help)
        header_layout.addRow(self._make_label_widget("Finetune Args File", args_help), args_row)

        runtime_row = QWidget()
        runtime_layout = QHBoxLayout(runtime_row)
        runtime_layout.setContentsMargins(0, 0, 0, 0)
        self.python_path_edit = QLineEdit()
        python_help = _special_help_text("python_exe")
        self.python_path_edit.setToolTip(python_help)
        runtime_layout.addWidget(self.python_path_edit, 1)
        browse_runtime = QPushButton("Browse")
        browse_runtime.clicked.connect(lambda: self._browse_for_path(self.python_path_edit, "file"))
        runtime_layout.addWidget(browse_runtime)
        auto_runtime = QPushButton("Use Detected")
        auto_runtime.clicked.connect(self._use_detected_python)
        runtime_layout.addWidget(auto_runtime)
        header_layout.addRow(self._make_label_widget("Python Runtime", python_help), runtime_row)

        preset_button = QPushButton("Load Selected Preset")
        preset_button.clicked.connect(self._apply_selected_preset)
        args_button = QPushButton("Load Finetune Args")
        args_button.clicked.connect(self._load_selected_args_file)
        header_layout.addRow(self._action_row(preset_button, args_button))
        layout.addWidget(header_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)

        metadata_box = QGroupBox("Metadata")
        metadata_form = QFormLayout(metadata_box)
        for spec in METADATA_FIELDS:
            widget = self._make_value_widget(spec)
            self.meta_widgets[spec["key"]] = widget
            help_text = _field_help(METADATA_HELP, spec)
            widget.setToolTip(help_text)
            metadata_form.addRow(self._make_label_widget(spec["label"], help_text), widget)
        body_layout.addWidget(metadata_box)

        paths_box = QGroupBox("Paths")
        paths_form = QFormLayout(paths_box)
        for spec in PATH_FIELDS:
            widget, row = self._make_path_row(spec["browse"])
            self.path_widgets[spec["key"]] = widget
            help_text = _field_help(PATH_HELP, spec)
            widget.setToolTip(help_text)
            paths_form.addRow(self._make_label_widget(spec["label"], help_text), row)
        self.path_widgets["train_file"].textChanged.connect(self._on_arguments_train_file_changed)
        body_layout.addWidget(paths_box)

        accelerate_box = QGroupBox("Accelerate")
        accelerate_form = QFormLayout(accelerate_box)
        for spec in ACCELERATE_FIELDS:
            widget = self._make_value_widget(spec)
            self.accelerate_widgets[spec["key"]] = widget
            help_text = _field_help(ACCELERATE_HELP, spec)
            widget.setToolTip(help_text)
            accelerate_form.addRow(self._make_label_widget(spec["label"], help_text), widget)
        body_layout.addWidget(accelerate_box)

        train_specs = {spec["key"]: spec for spec in TRAIN_FIELDS}

        train_box = QGroupBox("Training Basics")
        train_form = QFormLayout(train_box)
        self.special_widgets["precision_mode"] = QComboBox()
        self.special_widgets["precision_mode"].addItem("BF16", "bf16")
        self.special_widgets["precision_mode"].addItem("FP16", "fp16")
        self.special_widgets["precision_mode"].addItem("FP32 / None", "no")
        precision_help = _special_help_text("precision_mode")
        self.special_widgets["precision_mode"].setToolTip(precision_help)
        train_form.addRow(self._make_label_widget("Train Precision", precision_help), self.special_widgets["precision_mode"])

        for key in (
            "max_seq_length",
            "expected_samples",
            "strict_no_truncation",
            "per_device_train_batch_size",
            "gradient_accumulation_steps",
            "learning_rate",
            "num_train_epochs",
            "max_steps",
            "warmup_ratio",
            "lr_scheduler_type",
        ):
            spec = train_specs[key]
            widget = self._make_value_widget(spec)
            self.train_widgets[spec["key"]] = widget
            help_text = _field_help(TRAIN_HELP, spec)
            widget.setToolTip(help_text)
            train_form.addRow(self._make_label_widget(spec["label"], help_text), widget)
        body_layout.addWidget(train_box)

        optimizer_box = QGroupBox("Optimizer, Logging, and Checkpoints")
        optimizer_form = QFormLayout(optimizer_box)
        self.special_widgets["optimizer_choice"] = QComboBox()
        for label, value in OPTIMIZER_OPTIONS:
            self.special_widgets["optimizer_choice"].addItem(label, value)
        self.special_widgets["optimizer_choice"].currentIndexChanged.connect(self._refresh_optimizer_visibility)
        optimizer_help = _special_help_text("optimizer_choice")
        self.special_widgets["optimizer_choice"].setToolTip(optimizer_help)
        optimizer_form.addRow(
            self._make_label_widget("Optimizer Preset", optimizer_help),
            self.special_widgets["optimizer_choice"],
        )
        self.special_widgets["custom_optimizer"] = QLineEdit()
        self.special_widgets["custom_optimizer"].setPlaceholderText("Type a raw optimizer name only when Custom is selected")
        custom_optimizer_help = _special_help_text("custom_optimizer")
        self.special_widgets["custom_optimizer"].setToolTip(custom_optimizer_help)
        optimizer_form.addRow(
            self._make_label_widget("Custom Optimizer", custom_optimizer_help),
            self.special_widgets["custom_optimizer"],
        )
        for key in (
            "optim_args",
            "optim_target_modules",
            "weight_decay",
            "max_grad_norm",
            "torch_empty_cache_steps",
            "logging_steps",
            "save_steps",
            "save_total_limit",
            "save_only_model",
            "gradient_checkpointing",
            "seed",
        ):
            spec = train_specs[key]
            widget = self._make_value_widget(spec)
            self.train_widgets[spec["key"]] = widget
            help_text = _field_help(TRAIN_HELP, spec)
            widget.setToolTip(help_text)
            optimizer_form.addRow(self._make_label_widget(spec["label"], help_text), widget)
        use_lora_spec = train_specs["use_lora"]
        self.train_widgets["use_lora"] = self._make_value_widget(use_lora_spec)
        use_lora_help = _field_help(TRAIN_HELP, use_lora_spec)
        self.train_widgets["use_lora"].setToolTip(use_lora_help)
        optimizer_form.addRow(self._make_label_widget(use_lora_spec["label"], use_lora_help), self.train_widgets["use_lora"])
        body_layout.addWidget(optimizer_box)

        self.lora_box = QGroupBox("LoRA Options")
        lora_form = QFormLayout(self.lora_box)
        for key in (
            "load_in_4bit",
            "lora_r",
            "lora_alpha",
            "lora_dropout",
            "lora_target_modules",
        ):
            spec = train_specs[key]
            widget = self._make_value_widget(spec)
            self.train_widgets[spec["key"]] = widget
            help_text = _field_help(TRAIN_HELP, spec)
            widget.setToolTip(help_text)
            lora_form.addRow(self._make_label_widget(spec["label"], help_text), widget)
        self.train_widgets["use_lora"].toggled.connect(self._refresh_lora_visibility)
        body_layout.addWidget(self.lora_box)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        return tab

    def _build_jobs_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        controls = QGroupBox("Training Controls")
        controls_layout = QVBoxLayout(controls)
        self.allow_cpu_checkbox = QCheckBox("Allow CPU fallback when CUDA is unavailable")
        controls_layout.addWidget(self.allow_cpu_checkbox)

        buttons = QHBoxLayout()
        preflight_button = QPushButton("Run Preflight")
        preflight_button.clicked.connect(self._run_training_preflight)
        buttons.addWidget(preflight_button)
        launch_button = QPushButton("Launch Training")
        launch_button.clicked.connect(self._launch_training_job)
        buttons.addWidget(launch_button)
        cancel_button = QPushButton("Cancel Current Job")
        cancel_button.clicked.connect(self._cancel_current_job)
        buttons.addWidget(cancel_button)
        controls_layout.addLayout(buttons)

        self.current_job_label = QLabel("No active job.")
        self.current_job_label.setWordWrap(True)
        controls_layout.addWidget(self.current_job_label)

        self.job_progress_bar = QProgressBar()
        self.job_progress_bar.setRange(0, 1)
        self.job_progress_bar.setValue(0)
        self.job_progress_bar.setFormat("Waiting")
        controls_layout.addWidget(self.job_progress_bar)

        self.job_progress_detail = QLabel("Progress will appear here once training reports planned steps and live updates.")
        self.job_progress_detail.setObjectName("muted")
        self.job_progress_detail.setWordWrap(True)
        controls_layout.addWidget(self.job_progress_detail)

        self.training_target_summary = QLabel("Training target summary will appear here.")
        self.training_target_summary.setObjectName("muted")
        self.training_target_summary.setWordWrap(True)
        controls_layout.addWidget(self.training_target_summary)

        self.launch_artifacts_summary = QLabel("Launch artifacts will appear here.")
        self.launch_artifacts_summary.setObjectName("muted")
        self.launch_artifacts_summary.setWordWrap(True)
        controls_layout.addWidget(self.launch_artifacts_summary)
        layout.addWidget(controls)

        preflight_box = QGroupBox("Preflight Summary")
        preflight_layout = QVBoxLayout(preflight_box)
        self.preflight_summary = QPlainTextEdit()
        self.preflight_summary.setReadOnly(True)
        self.preflight_summary.setMinimumHeight(220)
        preflight_layout.addWidget(self.preflight_summary)
        layout.addWidget(preflight_box)

        logs_box = QGroupBox("Live Logs")
        logs_layout = QVBoxLayout(logs_box)
        self.job_logs = QPlainTextEdit()
        self.job_logs.setReadOnly(True)
        self.job_logs.setMinimumHeight(260)
        logs_layout.addWidget(self.job_logs)
        layout.addWidget(logs_box, 1)
        return tab

    def _make_path_row(self, browse_mode: str) -> tuple[QLineEdit, QWidget]:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        line_edit = QLineEdit()
        line_edit.setPlaceholderText("Relative or absolute path")
        layout.addWidget(line_edit, 1)
        browse = QPushButton("Browse")
        browse.clicked.connect(lambda: self._browse_for_path(line_edit, browse_mode))
        layout.addWidget(browse)
        return line_edit, widget

    def _action_row(self, *widgets: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return row

    def _make_label_widget(self, text: str, help_text: str) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(text)
        label.setToolTip(help_text)
        layout.addWidget(label)
        info_button = QToolButton()
        info_button.setText("i")
        info_button.setToolTip(help_text)
        info_button.clicked.connect(lambda: self._show_help_dialog(text, help_text))
        layout.addWidget(info_button)
        layout.addStretch(1)
        return wrapper

    def _show_help_dialog(self, title: str, help_text: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(f"{title} Help")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(title)
        box.setInformativeText(help_text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _show_busy_dialog(self, title: str, label: str) -> QProgressDialog:
        dialog = QProgressDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setCancelButton(None)
        dialog.setRange(0, 0)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.show()
        QApplication.processEvents()
        return dialog

    def _reset_job_progress_ui(self, message: str, *, busy: bool = False) -> None:
        if not hasattr(self, "job_progress_bar"):
            return
        if busy:
            self.job_progress_bar.setRange(0, 0)
            self.job_progress_bar.setFormat("Working...")
        else:
            self.job_progress_bar.setRange(0, 1)
            self.job_progress_bar.setValue(0)
            self.job_progress_bar.setFormat("Waiting")
        self.job_progress_detail.setText(message)

    def _update_job_progress_ui(self, log_text: str, status: JobStatus) -> None:
        if not hasattr(self, "job_progress_bar"):
            return

        stop_reason = ""
        planned_steps: int | None = None
        current_step: int | None = None
        elapsed = ""
        eta = ""
        epoch = ""
        loss = ""
        latest_line = ""

        for raw_line in reversed(log_text.splitlines()):
            line = raw_line.strip()
            if not line:
                continue
            if not latest_line and "[telemetry]" not in line:
                latest_line = line
            if not stop_reason:
                stop_match = STOP_CONDITION_RE.search(line)
                if stop_match:
                    stop_reason = stop_match.group("reason").strip()
                    planned_steps = int(stop_match.group("steps"))
            if planned_steps is None:
                plan_match = PROGRESS_PLAN_RE.search(line)
                if plan_match:
                    planned_steps = int(plan_match.group("steps"))
            if current_step is None:
                progress_match = PROGRESS_RE.search(line)
                if progress_match:
                    current_step = int(progress_match.group("current"))
                    planned_steps = int(progress_match.group("total"))
                    elapsed = str(progress_match.group("elapsed") or "").strip()
                    eta = str(progress_match.group("eta") or "").strip()
                    epoch = str(progress_match.group("epoch") or "").strip()
                    loss = str(progress_match.group("loss") or "").strip()
            if stop_reason and planned_steps is not None and current_step is not None and latest_line:
                break

        detail_lines: list[str] = []
        if stop_reason:
            detail_lines.append(f"Run ends when it reaches {stop_reason}.")
        if planned_steps is not None:
            if current_step is None:
                current_step = planned_steps if status == JobStatus.COMPLETED else 0
            bounded_step = max(0, min(current_step, planned_steps))
            self.job_progress_bar.setRange(0, max(planned_steps, 1))
            self.job_progress_bar.setValue(bounded_step)
            self.job_progress_bar.setFormat(f"{bounded_step} / {planned_steps} steps")
            progress_text = f"Optimizer steps: {bounded_step}/{planned_steps}"
            if elapsed:
                progress_text += f" | Elapsed: {elapsed}"
            if eta:
                progress_text += f" | ETA: {eta}"
            elif status == JobStatus.RUNNING and bounded_step < planned_steps:
                progress_text += " | ETA pending first logged step"
            if epoch:
                progress_text += f" | Epoch: {epoch}"
            if loss:
                progress_text += f" | Loss: {loss}"
            detail_lines.append(progress_text)
        elif status == JobStatus.RUNNING:
            self.job_progress_bar.setRange(0, 0)
            self.job_progress_bar.setFormat("Working...")
            detail_lines.append("Trainer is still loading the model, dataset, or optimizer state before step tracking begins.")
        else:
            self.job_progress_bar.setRange(0, 1)
            self.job_progress_bar.setValue(0)
            self.job_progress_bar.setFormat("Waiting")

        if status == JobStatus.COMPLETED:
            detail_lines.append("Run completed.")
        elif status == JobStatus.FAILED:
            detail_lines.append("Run failed.")
        elif status == JobStatus.CANCELLED:
            detail_lines.append("Run cancelled.")

        if latest_line:
            detail_lines.append(f"Latest: {latest_line}")
        elif not detail_lines:
            detail_lines.append("Progress will appear here once training reports planned steps and live updates.")

        self.job_progress_detail.setText("\n".join(detail_lines))

    def _make_value_widget(self, spec: dict[str, Any]) -> QWidget:
        kind = spec["type"]
        if kind == "bool":
            return QCheckBox()
        if kind == "choice":
            combo = QComboBox()
            for choice in spec["choices"]:
                combo.addItem(str(choice), choice)
            return combo
        if kind == "int":
            return self._spin_box(spec.get("min", 0), spec.get("max", 1000000))
        if kind == "float":
            spin = QDoubleSpinBox()
            spin.setRange(float(spec.get("min", 0.0)), float(spec.get("max", 1000000.0)))
            spin.setDecimals(int(spec.get("decimals", 6)))
            spin.setSingleStep(float(spec.get("step", 0.1)))
            return spin
        if kind in {"multiline", "list"}:
            text = QPlainTextEdit()
            text.setMaximumHeight(92)
            return text
        return QLineEdit()

    def _spin_box(self, minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        return spin

    def _browse_for_path(self, target: QLineEdit, browse_mode: str) -> None:
        start_value = target.text().strip()
        if start_value:
            try:
                start = str(self.service.resolve_output_path(PROJECT_ROOT, start_value, create_if_missing=False))
            except Exception:
                start = str(PROJECT_ROOT)
        else:
            start = str(PROJECT_ROOT)
        if browse_mode == "dir":
            chosen = QFileDialog.getExistingDirectory(self, "Choose Directory", start)
        elif browse_mode == "save_file":
            chosen, _ = QFileDialog.getSaveFileName(self, "Choose Output File", start)
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, "Choose File", start)
        if chosen:
            target.setText(_display_path(chosen))
            self._update_dataset_hint()
            self._refresh_training_target_summary()
            self._save_state()

    def _set_combo_by_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _normalized_preset_id(self, preset_id: str) -> str:
        legacy_map = {
            "canonical_full_sft": "most_stable",
            "qlora_adapter": "blank_custom",
        }
        normalized = legacy_map.get(preset_id, preset_id)
        return normalized if normalized in self.presets else "most_stable"

    def _refresh_optimizer_visibility(self, *_args: Any) -> None:
        if "custom_optimizer" not in self.special_widgets:
            return
        use_custom = str(self.special_widgets["optimizer_choice"].currentData() or "") == "__custom__"
        self.special_widgets["custom_optimizer"].setEnabled(use_custom)
        self._refresh_training_target_summary()

    def _is_athena_v1_dense_profile(self) -> bool:
        preset_id = self._normalized_preset_id(str(self.preset_combo.currentData() or "most_stable"))
        if preset_id not in {"super_fast", "most_stable"}:
            return False
        use_lora_widget = self.train_widgets.get("use_lora")
        load_4bit_widget = self.train_widgets.get("load_in_4bit")
        use_lora = bool(use_lora_widget.isChecked()) if use_lora_widget is not None else False
        load_in_4bit = bool(load_4bit_widget.isChecked()) if load_4bit_widget is not None else False
        return not use_lora and not load_in_4bit

    def _refresh_lora_visibility(self, *_args: Any) -> None:
        if not hasattr(self, "lora_box"):
            return
        enabled = bool(self.train_widgets.get("use_lora") and self.train_widgets["use_lora"].isChecked())
        self.lora_box.setVisible(enabled)
        self._refresh_training_target_summary()

    def _refresh_training_target_summary(self) -> None:
        if not hasattr(self, "training_target_summary"):
            return
        try:
            config = self._current_training_config_from_widgets()
        except Exception:
            return
        train_file = self._selected_training_dataset(config)
        base_model = str(config["paths"].get("model_path") or "").strip() or "(not set)"
        output_dir = str(config["paths"].get("output_dir") or "").strip() or "(not set)"
        run_name = str(config["metadata"].get("run_name") or "").strip() or "finetune_run"
        precision = str(self.special_widgets["precision_mode"].currentData() or "bf16").upper()
        optimizer = str(config["train"].get("optim") or "adamw_torch")
        mode = "LoRA" if bool(config["train"].get("use_lora")) else "Dense"
        self.training_target_summary.setText(
            f"Training on: {train_file or '(no dataset selected)'}\n"
            f"Base model: {base_model}\n"
            f"Output: {output_dir}\n"
            f"Preset: {str(self.preset_combo.currentText() or 'Custom')} | Mode: {mode} | Precision: {precision} | Optimizer: {optimizer}"
        )
        if hasattr(self, "launch_artifacts_summary"):
            self.launch_artifacts_summary.setText(
                "Created when launch starts:\n"
                f"- Run history entry under Finetune/runs/{run_name}/\n"
                f"- Transcript log in that run folder\n"
                f"- FINETUNE_ARGS.json in {output_dir}\n"
                f"- FINETUNE_CARD.md in {output_dir}\n"
                f"- _finetune_source/ snapshot in {output_dir}"
            )

    def _update_preset_summary(self, *_args: Any) -> None:
        preset_id = self._normalized_preset_id(str(self.preset_combo.currentData() or "most_stable"))
        preset = self.presets.get(preset_id)
        if preset is None:
            self.preset_summary.setText("No preset selected.")
            return
        source = _display_path(preset.args_path) if preset.args_path is not None else "Studio defaults"
        text = f"{preset.description} Source: {source}. Click 'Load Selected Preset' to apply it to the form."
        if self.loaded_args_path:
            text += f"\nCurrent form source: {_display_path(self.loaded_args_path)}"
        self.preset_summary.setText(text)

    def _on_train_ready_path_changed(self, text: str) -> None:
        if not text.strip():
            self.dataset_preview.setPlainText("Load a train-ready JSONL file to inspect it here.")
            return
        self._update_dataset_hint()
        self._refresh_import_preview()
        if not self.compose_widgets["output_path"].text().strip():
            self.compose_widgets["output_path"].setText(text.strip())

    def _on_arguments_train_file_changed(self, text: str) -> None:
        cleaned = _display_path(text)
        if cleaned != self.selected_train_file_path:
            self.selected_train_file_path = cleaned
        self._refresh_training_target_summary()
        self.refresh_environment()
        self._save_state()

    def _sync_train_file_from_data(self, path_value: str) -> None:
        cleaned = str(path_value).strip()
        if not cleaned:
            return
        display = _display_path(cleaned)
        self.selected_train_file_path = display
        self.train_ready_path_edit.setText(display)
        if "train_file" in self.path_widgets:
            if self.path_widgets["train_file"].text().strip() != display:
                self.path_widgets["train_file"].setText(display)
        self._update_dataset_hint()
        self._refresh_import_preview()
        self._refresh_training_target_summary()
        self.refresh_environment()
        self._save_state()

    def _send_compose_file_to_training(self) -> None:
        output_path = self.compose_widgets["output_path"].text().strip()
        if not output_path:
            QMessageBox.warning(self, "Compose Train-Ready JSONL", "Choose a target JSONL file first.")
            return
        self._sync_train_file_from_data(output_path)
        self.compose_status.setText(f"Compose target sent to training: {_display_path(output_path)}")
        self.tabs.setCurrentWidget(self.compose_tab)

    def _selected_training_dataset(self, config: dict[str, Any] | None = None) -> str:
        active = _display_path(self.selected_train_file_path)
        if active:
            return active
        if config is None:
            try:
                config = self._current_training_config_from_widgets()
            except Exception:
                config = None
        if config is not None:
            configured = _display_path(str(config["paths"].get("train_file") or "").strip())
            if configured:
                return configured
        return _display_path(self.train_ready_path_edit.text().strip())

    def _resolve_ui_path(self, path_value: str) -> Path:
        return self.service.resolve_output_path(PROJECT_ROOT, path_value, create_if_missing=False)

    def _render_dataset_preview(self, path_value: str, *, empty_message: str) -> str:
        cleaned = str(path_value).strip()
        if not cleaned:
            return empty_message
        resolved = self._resolve_ui_path(cleaned)
        if not resolved.exists():
            return f"File not found yet:\n{resolved}"

        rows: list[tuple[int, Any]] = []
        with resolved.open("r", encoding="utf-8-sig") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except Exception as exc:
                    return f"Unable to parse line {line_number} in {resolved}:\n{exc}"
                rows.append((line_number, payload))

        if not rows:
            return f"No rows found in:\n{resolved}"

        lines = [
            f"File: {resolved}",
            f"Rows: {len(rows)}",
        ]
        lines.append("")
        for line_number, payload in rows:
            lines.append(f"Line {line_number}")
            lines.append(_json_text(payload))
            lines.append("")
        return "\n".join(lines).strip()

    def _refresh_compose_preview(self) -> None:
        self.compose_preview.setPlainText(
            self._render_dataset_preview(
                self.compose_widgets["output_path"].text().strip(),
                empty_message="Compose or append a row to see the dataset structure here.",
            )
        )

    def _refresh_import_preview(self) -> None:
        self.dataset_preview.setPlainText(
            self._render_dataset_preview(
                self.train_ready_path_edit.text().strip(),
                empty_message="Import a train-ready JSONL file to inspect it here.",
            )
        )

    def _apply_dataset_recommendations(self, validation_result: Any) -> list[str]:
        changes: list[str] = []

        if "expected_samples" in self.train_widgets and validation_result.sample_count > 0:
            current_samples = self.train_widgets["expected_samples"].value()
            if current_samples != validation_result.sample_count:
                self.train_widgets["expected_samples"].setValue(int(validation_result.sample_count))
                changes.append(
                    f"Expected Samples updated from {current_samples} to {validation_result.sample_count} to match the dataset."
                )

        if "max_seq_length" in self.train_widgets and validation_result.max_tokens > 0:
            current_length = self.train_widgets["max_seq_length"].value()
            recommended = _recommended_max_seq_length(int(validation_result.max_tokens))
            if self._is_athena_v1_dense_profile() and recommended > 2048 and current_length <= 2048:
                changes.append(
                    "Dataset rows exceed the studio dense local guidance window. "
                    f"The dataset reaches {validation_result.max_tokens} tokens, so the studio did not auto-raise Max Seq Length above 2048 for this profile. "
                    "If you want to stay inside the local dense fast path, shorten or chunk the dataset so rows fit within 2048 tokens."
                )
            elif recommended > current_length:
                self.train_widgets["max_seq_length"].setValue(recommended)
                changes.append(
                    f"Max Seq Length raised from {current_length} to {recommended} because the dataset contains rows up to {validation_result.max_tokens} tokens."
                )

        if changes:
            self._refresh_training_target_summary()
        return changes

    def _clear_compose_prompts(self) -> None:
        self.compose_widgets["system_instructions"].clear()
        self.compose_widgets["user_prompt"].clear()
        self.compose_widgets["assistant_prompt"].clear()
        self.compose_status.setText("Prompt boxes cleared.")
        self._save_state()

    def _write_composed_train_ready(self, *, append: bool) -> None:
        output_path = self.compose_widgets["output_path"].text().strip()
        if not output_path:
            QMessageBox.warning(self, "Compose Train-Ready JSONL", "Choose a target JSONL file first.")
            return
        target = Path(output_path)
        if not target.is_absolute():
            target = (PROJECT_ROOT / target).resolve()
        if target.exists() and not append:
            decision = QMessageBox.question(
                self,
                "Overwrite Train-Ready JSONL",
                f"Overwrite the existing file?\n{target}",
            )
            if decision != QMessageBox.StandardButton.Yes:
                return
        try:
            result = self.service.compose_train_ready_jsonl(
                ComposeTrainReadyRequest(
                    output_path=output_path,
                    system_instructions=self.compose_widgets["system_instructions"].toPlainText(),
                    user_prompt=self.compose_widgets["user_prompt"].toPlainText(),
                    assistant_prompt=self.compose_widgets["assistant_prompt"].toPlainText(),
                    append=append,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "Compose Train-Ready JSONL", str(exc))
            return
        self.compose_status.setText(
            f"{'Appended' if append else 'Wrote'} row successfully. Current row count: {result.row_count}. File: {result.output_path}"
        )
        self._sync_train_file_from_data(result.output_path)
        self._refresh_compose_preview()
        self.tabs.setCurrentWidget(self.compose_tab)

    def _restore_session(self) -> None:
        selected_preset = self._normalized_preset_id(str(self.state.get("selected_preset") or "most_stable"))
        self._set_combo_by_data(self.preset_combo, selected_preset)
        self.selected_train_file_path = _display_path(self.state.get("selected_train_file_path") or "")
        self.loaded_args_path = str(self.state.get("loaded_args_path") or "")
        self.args_file_edit.setText(_display_path(self.loaded_args_path))
        self.python_path_edit.setText(str(self.state.get("python_exe") or ""))
        self.allow_cpu_checkbox.setChecked(bool(self.state.get("allow_cpu")))
        self.train_ready_path_edit.setText(_display_path(self.state.get("train_ready_path") or ""))
        self._load_compose_state(self.state.get("compose") or {})

        self._set_combo_by_data(self.data_mode_combo, str(self.state.get("input_mode") or DatasetSourceType.TRAIN_READY_JSONL.value))
        self._load_prepare_state(self.state.get("prepare") or {})
        self._load_build_state(self.state.get("build") or {})

        base_config = copy.deepcopy(self.presets[selected_preset].config if selected_preset in self.presets else self.service.blank_training_config())
        merged_config = _deep_merge(base_config, self.state.get("training_config") or {})
        self._load_training_config_into_widgets(merged_config)
        if self.selected_train_file_path:
            self.path_widgets["train_file"].setText(self.selected_train_file_path)
        else:
            self.selected_train_file_path = _display_path(str(merged_config["paths"].get("train_file") or "").strip())

        self._update_dataset_hint()
        self._update_preset_summary()
        self._refresh_compose_preview()
        self._refresh_import_preview()
        self._refresh_training_target_summary()

    def _load_compose_state(self, state: dict[str, Any]) -> None:
        self.compose_widgets["output_path"].setText(
            _display_path(state.get("output_path") or self.state.get("train_ready_path") or "Finetune/trainingdata/manual_train_ready.jsonl")
        )
        self.compose_widgets["system_instructions"].setPlainText(str(state.get("system_instructions") or ""))
        self.compose_widgets["user_prompt"].setPlainText(str(state.get("user_prompt") or ""))
        self.compose_widgets["assistant_prompt"].setPlainText(str(state.get("assistant_prompt") or ""))

    def _load_prepare_state(self, state: dict[str, Any]) -> None:
        self.prepare_widgets["input_path"].setText(_display_path(state.get("input_path") or ""))
        self.prepare_widgets["output_path"].setText(_display_path(state.get("output_path") or ""))
        self.prepare_widgets["assistant_role"].setText(str(state.get("assistant_role") or "teacher"))
        self._set_combo_by_data(self.prepare_widgets["artifact_style"], str(state.get("artifact_style") or "assistant_turn"))
        self.prepare_widgets["max_context_messages"].setValue(int(state.get("max_context_messages") or 12))
        self.prepare_widgets["min_messages"].setValue(int(state.get("min_messages") or 2))
        for key, fallback in (
            ("drop_empty", True),
            ("require_user_before_assistant", True),
            ("merge_consecutive_same_role", True),
            ("strip_role_prefixes", True),
        ):
            self.prepare_widgets[key].setChecked(bool(state.get(key, fallback)))

    def _load_build_state(self, state: dict[str, Any]) -> None:
        self._set_combo_by_data(self.builder_combo, str(state.get("builder_id") or "verified_sft"))
        for key in ("source", "output", "manifest_output", "model", "model_name_or_path"):
            if key in self.build_widgets:
                self.build_widgets[key].setText(_display_path(state.get(key) or ""))
        self.build_widgets["max_seq_length"].setValue(int(state.get("max_seq_length") or 4096))
        self.build_widgets["orchestrator_max_seq_length"].setValue(int(state.get("orchestrator_max_seq_length") or 2048))
        for key, fallback in (
            ("drop_overlong_base", False),
            ("drop_unchunkable", False),
            ("bootstrap", False),
            ("overwrite_bootstrap", False),
            ("write", True),
            ("validate", True),
            ("token_stats", False),
        ):
            if key in self.build_widgets:
                self.build_widgets[key].setChecked(bool(state.get(key, fallback)))

    def _load_training_config_into_widgets(self, config: dict[str, Any]) -> None:
        for spec in PATH_FIELDS:
            self._set_widget_value(self.path_widgets[spec["key"]], _display_path(config["paths"].get(spec["key"]) or ""))
        for spec in METADATA_FIELDS:
            self._set_widget_value(self.meta_widgets[spec["key"]], config["metadata"].get(spec["key"]))
        for spec in ACCELERATE_FIELDS:
            self._set_widget_value(self.accelerate_widgets[spec["key"]], config["accelerate"].get(spec["key"]))
        precision_mode = "bf16" if bool(config["train"].get("bf16")) else "fp16" if bool(config["train"].get("fp16")) else "no"
        self._set_combo_by_data(self.special_widgets["precision_mode"], precision_mode)
        optim_value = str(config["train"].get("optim") or "adamw_torch")
        known_optimizer_values = {value for _, value in OPTIMIZER_OPTIONS if value != "__custom__"}
        if optim_value in known_optimizer_values:
            self._set_combo_by_data(self.special_widgets["optimizer_choice"], optim_value)
            self.special_widgets["custom_optimizer"].setText("")
        else:
            self._set_combo_by_data(self.special_widgets["optimizer_choice"], "__custom__")
            self.special_widgets["custom_optimizer"].setText(optim_value)
        for spec in TRAIN_FIELDS:
            if spec["key"] in self.train_widgets:
                self._set_widget_value(self.train_widgets[spec["key"]], config["train"].get(spec["key"]))
        self._refresh_optimizer_visibility()
        self._refresh_lora_visibility()
        self._refresh_training_target_summary()

    def _set_widget_value(self, widget: QWidget, value: Any) -> None:
        if isinstance(widget, QLineEdit):
            widget.setText("" if value is None else str(value))
            return
        if isinstance(widget, QPlainTextEdit):
            if isinstance(value, list):
                widget.setPlainText("\n".join(str(item) for item in value))
            else:
                widget.setPlainText("" if value is None else str(value))
            return
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
            return
        if isinstance(widget, QComboBox):
            index = widget.findData(value)
            if index < 0:
                index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
            return
        if isinstance(widget, QSpinBox):
            widget.setValue(int(value or 0))
            return
        if isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value or 0.0))

    def _widget_value(self, widget: QWidget) -> Any:
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QPlainTextEdit):
            text = widget.toPlainText().strip()
            if widget in {self.meta_widgets["expected_behavior"], self.meta_widgets["notes"], self.meta_widgets["source_snapshot_files"]}:
                return [line.strip() for line in text.splitlines() if line.strip()]
            return text
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentData() or widget.currentText()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        return ""

    def _current_input_mode(self) -> str:
        return str(self.data_mode_combo.currentData() or DatasetSourceType.TRAIN_READY_JSONL.value)

    def _refresh_data_mode(self, *_args: Any) -> None:
        mode = self._current_input_mode()
        index_by_mode = {
            DatasetSourceType.TRAIN_READY_JSONL.value: 0,
            DatasetSourceType.PREPARE_DIALOGUE_DATA.value: 1,
            DatasetSourceType.BUILD_CANONICAL_DATASET.value: 2,
        }
        self.data_stack.setCurrentIndex(index_by_mode[mode])
        self._update_dataset_hint()
        self._save_state()

    def _refresh_builder_stack(self, *_args: Any) -> None:
        builder_id = str(self.builder_combo.currentData() or "verified_sft")
        index = {builder: idx for idx, (builder, _) in enumerate(BUILDERS)}[builder_id]
        self.builder_stack.setCurrentIndex(index)
        self._update_dataset_hint()
        self._save_state()

    def _update_dataset_hint(self) -> None:
        suggested = self._suggest_train_file()
        active = self._selected_training_dataset()
        if active and suggested and active != suggested:
            self.dataset_hint.setText(f"Selected for training: {active}\nImported file in this tab: {suggested}")
        elif active:
            self.dataset_hint.setText(f"Selected for training: {active}")
        elif suggested:
            self.dataset_hint.setText(f"Current train file candidate: {suggested}")
        else:
            self.dataset_hint.setText("No dataset is implied yet. You can still set a train file manually in Arguments.")

    def _suggest_train_file(self) -> str:
        mode = self._current_input_mode()
        if mode == DatasetSourceType.TRAIN_READY_JSONL.value:
            return self.train_ready_path_edit.text().strip()
        if mode == DatasetSourceType.PREPARE_DIALOGUE_DATA.value:
            return self.prepare_widgets["output_path"].text().strip()
        builder_id = str(self.builder_combo.currentData() or "verified_sft")
        if builder_id == "verified_sft":
            return "Finetune/trainingdata/math_plus_logic_verified_sft.jsonl"
        if builder_id == "training_dataset_0":
            return "Finetune/trainingdata/training_dataset_0_identity.jsonl"
        if builder_id == "chunked_sft":
            return self.build_widgets["output"].text().strip()
        return ""

    def _apply_selected_preset(self) -> None:
        preset_id = self._normalized_preset_id(str(self.preset_combo.currentData() or "most_stable"))
        config = copy.deepcopy(self.presets[preset_id].config if preset_id in self.presets else self.service.blank_training_config())
        self.loaded_args_path = ""
        self.args_file_edit.clear()
        self._load_training_config_into_widgets(config)
        if not self.meta_widgets["run_name"].text().strip():
            self.meta_widgets["run_name"].setText("finetune_run")
        self._update_preset_summary()
        self._refresh_training_target_summary()
        self.preflight_summary.clear()
        self.last_preflight = None
        self._save_state()

    def _load_selected_args_file(self) -> None:
        args_path = self.args_file_edit.text().strip()
        if not args_path:
            chosen, _ = QFileDialog.getOpenFileName(self, "Choose Finetune Args JSON", str(PROJECT_ROOT), "JSON Files (*.json);;All Files (*)")
            if not chosen:
                return
            args_path = chosen
            self.args_file_edit.setText(_display_path(chosen))
        try:
            resolved_path, config = self.service.load_training_config_file(args_path)
        except Exception as exc:
            QMessageBox.critical(self, "Load Finetune Args", str(exc))
            return
        self._set_combo_by_data(self.preset_combo, "blank_custom")
        self.loaded_args_path = str(resolved_path)
        self.args_file_edit.setText(_display_path(resolved_path))
        self._load_training_config_into_widgets(config)
        if not self.meta_widgets["run_name"].text().strip():
            self.meta_widgets["run_name"].setText("finetune_run")
        self._update_preset_summary()
        self._refresh_training_target_summary()
        self.preflight_summary.clear()
        self.last_preflight = None
        self._save_state()

    def _use_detected_python(self) -> None:
        try:
            candidate = self.service.get_python_exe_candidates()[0]
        except Exception as exc:
            QMessageBox.critical(self, "Python Runtime", str(exc))
            return
        self.python_path_edit.setText(str(candidate))
        self.refresh_environment()
        self._refresh_training_target_summary()
        self._save_state()

    def refresh_environment(self) -> None:
        try:
            candidates = [str(path) for path in self.service.get_python_exe_candidates()]
        except Exception as exc:
            candidates = [f"Runtime discovery failed: {exc}"]
        selected_dataset = self._selected_training_dataset()
        imported_dataset = self.train_ready_path_edit.text().strip()
        lines = [
            f"Project Root\n{PROJECT_ROOT}",
            f"Finetune Root\n{self.service.finetune_root}",
            f"Platform\n{platform.platform()}",
            f"Python Runtime\n{_blank(self.python_path_edit.text())}",
            f"Selected Preset\n{_blank(self.preset_combo.currentText())}",
            f"Loaded Args File\n{_blank(_display_path(self.loaded_args_path))}",
            f"Selected Dataset\n{_blank(selected_dataset)}",
            f"Imported Dataset In Data Tab\n{_blank(imported_dataset)}",
            "Detected Runtimes\n" + ("\n".join(f"- {candidate}" for candidate in candidates) if candidates else ""),
        ]
        self.environment_text.setPlainText("\n\n".join(lines))

    def refresh_runs(self) -> None:
        selected_meta_path = self.preferred_run_meta_path
        selected_item = self.home_runs_list.currentItem()
        if not selected_meta_path and selected_item is not None:
            selected_meta_path = str(selected_item.data(Qt.UserRole))
        records = self.service.list_runs(limit=100)
        self.run_records = {record.meta_path: record for record in records}
        self.home_runs_list.clear()
        for record in records:
            label = f"{record.started_at[:19].replace('T', ' ')}  {record.run_name}  [{record.status}]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, record.meta_path)
            self.home_runs_list.addItem(item)
        if selected_meta_path:
            for index in range(self.home_runs_list.count()):
                item = self.home_runs_list.item(index)
                if str(item.data(Qt.UserRole)) == selected_meta_path:
                    self.home_runs_list.setCurrentItem(item)
                    break
        self.preferred_run_meta_path = ""
        self._show_selected_run_details()
        self._save_state()

    def _clear_run_selection(self) -> None:
        self.preferred_run_meta_path = ""
        self.home_runs_list.clearSelection()
        self._show_selected_run_details()

    def _current_training_config_from_widgets(self) -> dict[str, Any]:
        config = self.service.blank_training_config()
        for spec in PATH_FIELDS:
            config["paths"][spec["key"]] = self._widget_value(self.path_widgets[spec["key"]])
        for spec in METADATA_FIELDS:
            config["metadata"][spec["key"]] = self._widget_value(self.meta_widgets[spec["key"]])
        for spec in ACCELERATE_FIELDS:
            config["accelerate"][spec["key"]] = self._widget_value(self.accelerate_widgets[spec["key"]])
        precision_mode = str(self.special_widgets["precision_mode"].currentData() or "bf16")
        config["train"]["bf16"] = precision_mode == "bf16"
        config["train"]["fp16"] = precision_mode == "fp16"
        optimizer_choice = str(self.special_widgets["optimizer_choice"].currentData() or "adamw_torch")
        if optimizer_choice == "__custom__":
            config["train"]["optim"] = self.special_widgets["custom_optimizer"].text().strip() or "adamw_torch"
        else:
            config["train"]["optim"] = optimizer_choice
        for spec in TRAIN_FIELDS:
            if spec["key"] in self.train_widgets:
                config["train"][spec["key"]] = self._widget_value(self.train_widgets[spec["key"]])
        selected_train_file = self._selected_training_dataset(config)
        if selected_train_file:
            config["paths"]["train_file"] = selected_train_file
        return config

    def _validate_selected_data(self) -> None:
        config = self._current_training_config_from_widgets()
        train_file = self.train_ready_path_edit.text().strip() or self._selected_training_dataset(config)
        if not train_file:
            QMessageBox.warning(self, "Dataset Validation", "Choose or build a dataset first.")
            return
        busy = self._show_busy_dialog("Dataset Validation", "Validation is running. Please wait...")
        try:
            result = self.service.validate_dataset(
                DatasetValidationRequest(
                    train_file=train_file,
                    model_path=str(config["paths"].get("model_path") or ""),
                    max_seq_length=int(config["train"]["max_seq_length"]),
                    strict_no_truncation=bool(config["train"]["strict_no_truncation"]),
                    python_exe=self.python_path_edit.text().strip(),
                )
            )
        finally:
            busy.close()
            QApplication.processEvents()
        if not result.ok:
            self.dataset_preview.setPlainText(result.error)
            QMessageBox.warning(self, "Dataset Validation", result.error)
            return
        changes = self._apply_dataset_recommendations(result)
        payload: dict[str, Any] = {
            "train_file": result.train_file,
            "ready": result.ready,
            "sample_count": result.sample_count,
            "min_tokens": result.min_tokens,
            "p95_tokens": result.p95_tokens,
            "max_tokens": result.max_tokens,
            "tokenizer_class": result.tokenizer_class,
            "warnings": result.warnings,
        }
        if result.preview is not None:
            payload["preview"] = asdict(result.preview)
        if changes:
            payload["auto_adjustments"] = changes
        payload["what_validation_does"] = "Read-only check. Validation does not modify the dataset file."
        structure_preview = self._render_dataset_preview(train_file, empty_message="")
        self.dataset_preview.setPlainText(_json_text(payload) + "\n\n" + structure_preview)
        if changes:
            QMessageBox.information(self, "Dataset Validation", "\n\n".join(changes))
        self._save_state()

    def _build_prepare_request(self) -> PrepareDialogueRequest:
        return PrepareDialogueRequest(
            input_path=self.prepare_widgets["input_path"].text().strip(),
            output_path=self.prepare_widgets["output_path"].text().strip(),
            assistant_role=self.prepare_widgets["assistant_role"].text().strip() or "teacher",
            artifact_style=str(self.prepare_widgets["artifact_style"].currentData() or self.prepare_widgets["artifact_style"].currentText()),
            max_context_messages=self.prepare_widgets["max_context_messages"].value(),
            min_messages=self.prepare_widgets["min_messages"].value(),
            drop_empty=self.prepare_widgets["drop_empty"].isChecked(),
            require_user_before_assistant=self.prepare_widgets["require_user_before_assistant"].isChecked(),
            merge_consecutive_same_role=self.prepare_widgets["merge_consecutive_same_role"].isChecked(),
            strip_role_prefixes=self.prepare_widgets["strip_role_prefixes"].isChecked(),
            python_exe=self.python_path_edit.text().strip(),
        )

    def _launch_prepare_job(self) -> None:
        try:
            spec = self.service.build_prepare_command(self._build_prepare_request())
        except Exception as exc:
            QMessageBox.critical(self, "Prepare Data", str(exc))
            return
        self._sync_train_file_from_data(self.prepare_widgets["output_path"].text().strip())
        self._launch_generic_job(spec)

    def _build_canonical_request(self) -> BuildCanonicalDatasetRequest:
        builder_id = str(self.builder_combo.currentData() or "verified_sft")
        options: dict[str, Any] = {}
        if builder_id == "chunked_sft":
            options = {
                "source": self.build_widgets["source"].text().strip(),
                "output": self.build_widgets["output"].text().strip(),
                "manifest_output": self.build_widgets["manifest_output"].text().strip(),
                "model": self.build_widgets["model"].text().strip(),
                "max_seq_length": self.build_widgets["max_seq_length"].value(),
                "drop_overlong_base": self.build_widgets["drop_overlong_base"].isChecked(),
                "drop_unchunkable": self.build_widgets["drop_unchunkable"].isChecked(),
            }
        elif builder_id == "orchestrator_v1":
            options = {
                "model_name_or_path": self.build_widgets["model_name_or_path"].text().strip(),
                "max_seq_length": self.build_widgets["orchestrator_max_seq_length"].value(),
                "bootstrap": self.build_widgets["bootstrap"].isChecked(),
                "overwrite_bootstrap": self.build_widgets["overwrite_bootstrap"].isChecked(),
                "write": self.build_widgets["write"].isChecked(),
                "validate": self.build_widgets["validate"].isChecked(),
                "token_stats": self.build_widgets["token_stats"].isChecked(),
            }
        return BuildCanonicalDatasetRequest(
            builder_id=builder_id,
            options=options,
            python_exe=self.python_path_edit.text().strip(),
        )

    def _launch_build_job(self) -> None:
        try:
            spec = self.service.build_canonical_dataset_command(self._build_canonical_request())
        except Exception as exc:
            QMessageBox.critical(self, "Dataset Builder", str(exc))
            return
        suggested = self._suggest_train_file()
        if suggested:
            self._sync_train_file_from_data(suggested)
        self._launch_generic_job(spec)

    def _launch_generic_job(self, spec: CommandSpec) -> None:
        snapshot = self.jobs.get_snapshot(self.current_job_id) if self.current_job_id else None
        if snapshot is not None and snapshot.status == JobStatus.RUNNING:
            QMessageBox.warning(self, "Active Job", "Wait for the current job to finish or cancel it first.")
            return
        if spec.transcript_path is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            transcript = get_logs_dir() / f"{stamp}_{_slugify(spec.title)}.log"
            spec = CommandSpec(
                title=spec.title,
                kind=spec.kind,
                command=spec.command,
                cwd=spec.cwd,
                env_overrides=spec.env_overrides,
                transcript_path=transcript,
                meta_path=spec.meta_path,
                expected_outputs=spec.expected_outputs,
            )
        self.current_job_id = self.jobs.launch(spec)
        self.preferred_run_meta_path = str(spec.meta_path or "")
        self.tabs.setCurrentWidget(self.jobs_tab)
        self.current_job_label.setText(f"{spec.title} launched.")
        self.job_logs.clear()
        self._last_displayed_job_log = ""
        self._reset_job_progress_ui("Job launched. Waiting for the trainer to report stop condition and planned steps...", busy=True)
        self._save_state()

    def _run_training_preflight(self) -> Any:
        config = self._current_training_config_from_widgets()
        train_file = self._selected_training_dataset(config)
        if not train_file:
            QMessageBox.warning(self, "Training Preflight", "Choose a dataset before running preflight.")
            return None
        config["paths"]["train_file"] = train_file
        busy = self._show_busy_dialog("Training Preflight", "Preflight is running. Please wait...")
        try:
            try:
                preflight = self.service.preflight_training(
                    TrainingPreflightRequest(
                        config=config,
                        allow_cpu=self.allow_cpu_checkbox.isChecked(),
                        dry_run=True,
                        python_exe=self.python_path_edit.text().strip(),
                    )
                )
            except Exception as exc:
                self.preflight_summary.setPlainText(str(exc))
                QMessageBox.critical(self, "Training Preflight", str(exc))
                return None
        finally:
            busy.close()
            QApplication.processEvents()
        self.last_preflight = preflight
        resolved_expected_samples = int(preflight.resolved_config["train"]["expected_samples"])
        if "expected_samples" in self.train_widgets and self.train_widgets["expected_samples"].value() != resolved_expected_samples:
            self.train_widgets["expected_samples"].setValue(resolved_expected_samples)
        self.preflight_summary.setPlainText(_json_text(preflight.summary))
        self.tabs.setCurrentWidget(self.jobs_tab)
        self._save_state()
        return preflight

    def _launch_training_job(self) -> None:
        preflight = self._run_training_preflight()
        if preflight is None:
            return
        busy = self._show_busy_dialog("Launch Training", "Starting training job. Please wait...")
        try:
            try:
                spec = self.service.create_training_command_spec(TrainingLaunchRequest(preflight=preflight, dry_run=False))
            except Exception as exc:
                QMessageBox.critical(self, "Launch Training", str(exc))
                return
            self._launch_generic_job(spec)
        finally:
            busy.close()
            QApplication.processEvents()
        self.refresh_runs()

    def _cancel_current_job(self) -> None:
        if not self.current_job_id:
            return
        self.jobs.cancel(self.current_job_id)
        self.current_job_label.setText("Cancellation requested.")
        self._reset_job_progress_ui("Cancellation requested. Waiting for the process to stop...", busy=True)

    def _poll_jobs(self) -> None:
        if not self.current_job_id:
            return
        snapshot = self.jobs.get_snapshot(self.current_job_id)
        if snapshot is None:
            return
        self.current_job_label.setText(
            f"{snapshot.title} | {snapshot.status.value} | returncode={snapshot.returncode}"
        )
        if snapshot.log_text != self._last_displayed_job_log:
            if snapshot.log_text.startswith(self._last_displayed_job_log):
                delta = snapshot.log_text[len(self._last_displayed_job_log) :]
                if delta:
                    self.job_logs.moveCursor(QTextCursor.MoveOperation.End)
                    self.job_logs.insertPlainText(delta)
            else:
                self.job_logs.setPlainText(snapshot.log_text)
            self._last_displayed_job_log = snapshot.log_text
        self._update_job_progress_ui(snapshot.log_text, snapshot.status)
        selected_run = self._selected_run()
        if selected_run is not None and snapshot.meta_path and selected_run.meta_path == snapshot.meta_path:
            self._show_selected_run_details()
        if snapshot.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            if snapshot.job_id not in self._completed_jobs:
                self._completed_jobs.add(snapshot.job_id)
                self.preferred_run_meta_path = snapshot.meta_path
                self.refresh_runs()

    def _selected_run(self) -> Any:
        item = self.home_runs_list.currentItem()
        if item is None:
            return None
        return self.run_records.get(str(item.data(Qt.UserRole)))

    def _show_selected_run_details(self) -> None:
        run = self._selected_run()
        if run is None:
            self.run_details.clear()
            return
        try:
            payload = json.loads(Path(run.meta_path).read_text(encoding="utf-8-sig"))
        except Exception:
            payload = asdict(run)
        payload["paths_exist"] = {
            "args_file": Path(str(payload.get("args_file") or "")).exists() if str(payload.get("args_file") or "").strip() else False,
            "output_dir": Path(str(payload.get("output_dir") or "")).exists() if str(payload.get("output_dir") or "").strip() else False,
            "transcript": Path(str(payload.get("transcript") or "")).exists() if str(payload.get("transcript") or "").strip() else False,
            "finetune_card": Path(str(payload.get("finetune_card") or "")).exists() if str(payload.get("finetune_card") or "").strip() else False,
            "source_snapshot_dir": Path(str(payload.get("source_snapshot_dir") or "")).exists() if str(payload.get("source_snapshot_dir") or "").strip() else False,
        }
        self.run_details.setPlainText(_json_text(payload))

    def _open_path(self, path_value: str) -> None:
        path = self.service.resolve_output_path(PROJECT_ROOT, path_value, create_if_missing=False)
        if not path.exists():
            QMessageBox.warning(self, "Open Path", f"Path does not exist:\n{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_selected_run_output(self) -> None:
        run = self._selected_run()
        if run is not None:
            self._open_path(run.output_dir)

    def _open_selected_run_transcript(self) -> None:
        run = self._selected_run()
        if run is not None:
            self._open_path(run.transcript)

    def _open_selected_run_card(self) -> None:
        run = self._selected_run()
        if run is not None:
            self._open_path(run.finetune_card)

    def _open_selected_run_args_file(self) -> None:
        run = self._selected_run()
        if run is not None:
            self._open_path(run.args_file)

    def _open_selected_run_snapshot(self) -> None:
        run = self._selected_run()
        if run is not None:
            self._open_path(run.source_snapshot_dir)

    def _save_state(self) -> None:
        if self._loading_state:
            return
        training_config = self._current_training_config_from_widgets()
        for key in training_config.get("paths", {}):
            training_config["paths"][key] = _display_path(training_config["paths"].get(key) or "")
        build_state = {
            "builder_id": str(self.builder_combo.currentData() or "verified_sft"),
            "source": _display_path(self.build_widgets["source"].text().strip()),
            "output": _display_path(self.build_widgets["output"].text().strip()),
            "manifest_output": _display_path(self.build_widgets["manifest_output"].text().strip()),
            "model": _display_path(self.build_widgets["model"].text().strip()),
            "model_name_or_path": _display_path(self.build_widgets["model_name_or_path"].text().strip()),
            "max_seq_length": self.build_widgets["max_seq_length"].value(),
            "orchestrator_max_seq_length": self.build_widgets["orchestrator_max_seq_length"].value(),
            "drop_overlong_base": self.build_widgets["drop_overlong_base"].isChecked(),
            "drop_unchunkable": self.build_widgets["drop_unchunkable"].isChecked(),
            "bootstrap": self.build_widgets["bootstrap"].isChecked(),
            "overwrite_bootstrap": self.build_widgets["overwrite_bootstrap"].isChecked(),
            "write": self.build_widgets["write"].isChecked(),
            "validate": self.build_widgets["validate"].isChecked(),
            "token_stats": self.build_widgets["token_stats"].isChecked(),
        }
        prepare_state = {
            "input_path": _display_path(self.prepare_widgets["input_path"].text().strip()),
            "output_path": _display_path(self.prepare_widgets["output_path"].text().strip()),
            "assistant_role": self.prepare_widgets["assistant_role"].text().strip(),
            "artifact_style": str(self.prepare_widgets["artifact_style"].currentData() or self.prepare_widgets["artifact_style"].currentText()),
            "max_context_messages": self.prepare_widgets["max_context_messages"].value(),
            "min_messages": self.prepare_widgets["min_messages"].value(),
            "drop_empty": self.prepare_widgets["drop_empty"].isChecked(),
            "require_user_before_assistant": self.prepare_widgets["require_user_before_assistant"].isChecked(),
            "merge_consecutive_same_role": self.prepare_widgets["merge_consecutive_same_role"].isChecked(),
            "strip_role_prefixes": self.prepare_widgets["strip_role_prefixes"].isChecked(),
        }
        compose_state = {
            "output_path": _display_path(self.compose_widgets["output_path"].text().strip()),
            "system_instructions": self.compose_widgets["system_instructions"].toPlainText(),
            "user_prompt": self.compose_widgets["user_prompt"].toPlainText(),
            "assistant_prompt": self.compose_widgets["assistant_prompt"].toPlainText(),
        }
        updates = {
            "selected_preset": str(self.preset_combo.currentData() or "most_stable"),
            "loaded_args_path": _display_path(self.loaded_args_path),
            "input_mode": self._current_input_mode(),
            "selected_train_file_path": _display_path(self.selected_train_file_path),
            "train_ready_path": _display_path(self.train_ready_path_edit.text().strip()),
            "compose": compose_state,
            "prepare": prepare_state,
            "build": build_state,
            "allow_cpu": self.allow_cpu_checkbox.isChecked(),
            "python_exe": self.python_path_edit.text().strip(),
            "recent_run_meta_paths": list(self.run_records.keys())[:10],
            "training_config": training_config,
        }
        self.state = save_session_state(updates)

    def closeEvent(self, event: Any) -> None:
        self._save_state()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = FinetuneStudioWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
