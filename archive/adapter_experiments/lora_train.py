#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

ROLES = {"system", "user", "assistant"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _str2bool(v: str | bool) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid bool value: {v}")


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Args file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _cfg_get(cfg: dict, keys: list[str], default=None):
    cur = cfg
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _resolve_model_source(raw: str, project_root: Path) -> str:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return str(p.resolve())
    cwd_candidate = (Path.cwd() / p)
    if cwd_candidate.exists():
        return str(cwd_candidate.resolve())
    root_candidate = (project_root / p)
    if root_candidate.exists():
        return str(root_candidate.resolve())
    return raw


def _resolve_existing_file(raw: str, project_root: Path) -> Path:
    p = Path(raw).expanduser()
    candidates = [p] if p.is_absolute() else [Path.cwd() / p, project_root / p]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"File not found: {raw}. Tried: {tried}")


def _resolve_output_dir(raw: str, project_root: Path) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return project_root / p


def _resolve_existing_optional_path(raw: str, project_root: Path) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    p = Path(s).expanduser()
    candidates = [p] if p.is_absolute() else [Path.cwd() / p, project_root / p]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"Path not found for resume_from_checkpoint: {raw}. Tried: {tried}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LoRA trainer for AthenaV5 math SFT")
    p.add_argument("--args_file", default="", help="Optional JSON config (see Finetune/lora_args.json)")

    p.add_argument("--model_name_or_path", default="")
    p.add_argument("--train_file", default="")
    p.add_argument("--output_dir", default="")
    p.add_argument("--resume_from_checkpoint", default="")

    p.add_argument("--max_seq_length", type=int, default=0)
    p.add_argument("--per_device_train_batch_size", type=int, default=0)
    p.add_argument("--gradient_accumulation_steps", type=int, default=0)
    p.add_argument("--learning_rate", type=float, default=0.0)
    p.add_argument("--num_train_epochs", type=float, default=0.0)
    p.add_argument("--warmup_ratio", type=float, default=-1.0)
    p.add_argument("--lr_scheduler_type", default="")
    p.add_argument("--weight_decay", type=float, default=-1.0)
    p.add_argument("--max_grad_norm", type=float, default=-1.0)
    p.add_argument("--logging_steps", type=int, default=0)
    p.add_argument("--save_steps", type=int, default=0)
    p.add_argument("--save_total_limit", type=int, default=0)
    p.add_argument("--expected_samples", type=int, default=0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--chunk_overlap", type=int, default=-1)

    for flag in ("save_only_model", "strict_no_truncation", "bf16", "fp16", "gradient_checkpointing", "chunk_long_samples"):
        p.add_argument(f"--{flag}", type=_str2bool, nargs="?", const=True, default=None)

    p.add_argument("--lora_r", type=int, default=0)
    p.add_argument("--lora_alpha", type=int, default=0)
    p.add_argument("--lora_dropout", type=float, default=-1.0)
    p.add_argument("--target_modules", default="")
    p.add_argument("--modules_to_save", default="")

    args = p.parse_args()
    cfg = _load_json(args.args_file) if args.args_file else {}

    def choose(current, keys: list[str], fallback):
        if current not in (None, "", 0, 0.0, -1.0):
            return current
        c = _cfg_get(cfg, keys, None)
        return fallback if c is None else c

    def choose_bool(current, keys: list[str], fallback: bool):
        if current is not None:
            return bool(current)
        c = _cfg_get(cfg, keys, None)
        return fallback if c is None else bool(c)

    args.model_name_or_path = choose(args.model_name_or_path, ["paths", "model_path"], "")
    args.train_file = choose(args.train_file, ["paths", "train_file"], "")
    args.output_dir = choose(args.output_dir, ["paths", "output_dir"], "")
    args.resume_from_checkpoint = choose(args.resume_from_checkpoint, ["paths", "resume_from_checkpoint"], "")

    args.max_seq_length = int(choose(args.max_seq_length, ["train", "max_seq_length"], 2048))
    args.per_device_train_batch_size = int(
        choose(args.per_device_train_batch_size, ["train", "per_device_train_batch_size"], 1)
    )
    args.gradient_accumulation_steps = int(
        choose(args.gradient_accumulation_steps, ["train", "gradient_accumulation_steps"], 16)
    )
    args.learning_rate = float(choose(args.learning_rate, ["train", "learning_rate"], 2e-4))
    args.num_train_epochs = float(choose(args.num_train_epochs, ["train", "num_train_epochs"], 2.0))
    args.warmup_ratio = float(choose(args.warmup_ratio, ["train", "warmup_ratio"], 0.03))
    args.lr_scheduler_type = str(choose(args.lr_scheduler_type, ["train", "lr_scheduler_type"], "cosine"))
    args.weight_decay = float(choose(args.weight_decay, ["train", "weight_decay"], 0.0))
    args.max_grad_norm = float(choose(args.max_grad_norm, ["train", "max_grad_norm"], 1.0))
    args.logging_steps = int(choose(args.logging_steps, ["train", "logging_steps"], 10))
    args.save_steps = int(choose(args.save_steps, ["train", "save_steps"], 100))
    args.save_total_limit = int(choose(args.save_total_limit, ["train", "save_total_limit"], 3))
    args.expected_samples = int(choose(args.expected_samples, ["train", "expected_samples"], 0))
    args.seed = int(choose(args.seed, ["train", "seed"], 777))
    args.chunk_overlap = int(choose(args.chunk_overlap, ["train", "chunk_overlap"], 256))

    args.save_only_model = choose_bool(args.save_only_model, ["train", "save_only_model"], True)
    args.strict_no_truncation = choose_bool(args.strict_no_truncation, ["train", "strict_no_truncation"], False)
    args.bf16 = choose_bool(args.bf16, ["train", "bf16"], True)
    args.fp16 = choose_bool(args.fp16, ["train", "fp16"], False)
    args.gradient_checkpointing = choose_bool(args.gradient_checkpointing, ["train", "gradient_checkpointing"], True)
    args.chunk_long_samples = choose_bool(args.chunk_long_samples, ["train", "chunk_long_samples"], True)

    args.lora_r = int(choose(args.lora_r, ["lora", "lora_r"], 64))
    args.lora_alpha = int(choose(args.lora_alpha, ["lora", "lora_alpha"], 128))
    args.lora_dropout = float(choose(args.lora_dropout, ["lora", "lora_dropout"], 0.05))
    args.target_modules = str(
        choose(args.target_modules, ["lora", "target_modules"], "q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")
    )
    args.modules_to_save = str(choose(args.modules_to_save, ["lora", "modules_to_save"], ""))

    if not args.model_name_or_path:
        raise ValueError("model_name_or_path is required.")
    if not args.train_file:
        raise ValueError("train_file is required.")
    if not args.output_dir:
        raise ValueError("output_dir is required.")
    if args.bf16 and args.fp16:
        raise ValueError("Choose only one of bf16 or fp16.")
    if args.chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0.")
    if args.chunk_overlap >= args.max_seq_length:
        raise ValueError("chunk_overlap must be smaller than max_seq_length.")

    args.model_name_or_path = _resolve_model_source(args.model_name_or_path, PROJECT_ROOT)
    args.train_file = str(_resolve_existing_file(args.train_file, PROJECT_ROOT))
    args.output_dir = str(_resolve_output_dir(args.output_dir, PROJECT_ROOT).resolve())
    args.resume_from_checkpoint = _resolve_existing_optional_path(args.resume_from_checkpoint, PROJECT_ROOT)

    return args


def normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        role = str(m.get("role") or "").strip()
        content = str(m.get("content") or "").strip()
        if role in ROLES and content:
            out.append({"role": role, "content": content})
    return out


def render(tok, messages: list[dict[str, str]], gen: bool = False) -> str:
    return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=gen)


def ids(tok, text: str) -> list[int]:
    return tok(text, add_special_tokens=False)["input_ids"]


def build_supervised_tokens(tok, msgs: list[dict[str, str]]) -> tuple[list[int], list[int]]:
    x = ids(tok, render(tok, msgs))
    y = [-100] * len(x)
    for i, m in enumerate(msgs):
        if m["role"] != "assistant":
            continue
        s = min(len(ids(tok, render(tok, msgs[:i], True))), len(x))
        e = min(len(ids(tok, render(tok, msgs[: i + 1]))), len(x))
        if e > s:
            y[s:e] = x[s:e]
    return x, y


def smart_truncate(input_ids: list[int], labels: list[int], cap: int) -> tuple[list[int], list[int]]:
    if len(input_ids) <= cap:
        return input_ids, labels

    supervised_positions = [i for i, v in enumerate(labels) if v != -100]
    if not supervised_positions:
        return input_ids[:cap], labels[:cap]

    # Keep a window ending at the last supervised token so final answer targets survive truncation.
    end = min(len(input_ids), supervised_positions[-1] + 1)
    start = max(0, end - cap)
    return input_ids[start:end], labels[start:end]


def split_into_chunks(input_ids: list[int], labels: list[int], cap: int, overlap: int) -> list[tuple[list[int], list[int]]]:
    if len(input_ids) <= cap:
        return [(input_ids, labels)]

    step = max(1, cap - overlap)
    last_start = max(0, len(input_ids) - cap)
    starts = list(range(0, last_start + 1, step))
    if starts[-1] != last_start:
        starts.append(last_start)

    windows: list[tuple[list[int], list[int]]] = []
    for start in starts:
        end = start + cap
        wx = input_ids[start:end]
        wy = labels[start:end]
        if any(v != -100 for v in wy):
            windows.append((wx, wy))
    if windows:
        return windows
    tx, ty = smart_truncate(input_ids, labels, cap)
    return [(tx, ty)]


class ChatDataset(Dataset):
    def __init__(self, path: str):
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Train file not found: {p}")
        self.samples: list[list[dict[str, str]]] = []
        with p.open("r", encoding="utf-8-sig") as fh:
            for i, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                msgs = obj.get("messages")
                if not isinstance(msgs, list):
                    raise ValueError(f"Line {i}: missing 'messages' list")
                cleaned = normalize_messages(msgs)
                if cleaned:
                    self.samples.append(cleaned)
        if not self.samples:
            raise ValueError("No usable training samples found")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, i: int) -> dict:
        return {"messages": self.samples[i]}


class TokenizedChunkDataset(Dataset):
    def __init__(
        self,
        samples: list[list[dict[str, str]]],
        tok,
        *,
        max_len: int,
        chunk_long_samples: bool,
        chunk_overlap: int,
    ) -> None:
        self.items: list[dict[str, list[int]]] = []
        self.raw_lengths: list[int] = []
        self.long_count = 0
        self.source_samples = len(samples)

        for msgs in samples:
            x, y = build_supervised_tokens(tok, msgs)
            n = len(x)
            self.raw_lengths.append(n)
            if n > max_len:
                self.long_count += 1
            if chunk_long_samples:
                windows = split_into_chunks(x, y, max_len, chunk_overlap)
            else:
                windows = [smart_truncate(x, y, max_len)]
            for wx, wy in windows:
                if any(v != -100 for v in wy):
                    self.items.append({"input_ids": wx, "labels": wy})

        if not self.items:
            raise ValueError("No tokenized training chunks produced.")
        self.raw_lengths.sort()

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> dict[str, list[int]]:
        return self.items[i]


def make_collator(tok):
    def collate(batch: list[dict]) -> dict[str, torch.Tensor]:
        packed_ids = [row["input_ids"] for row in batch]
        packed_lbl = [row["labels"] for row in batch]

        pad = tok.pad_token_id
        if pad is None:
            raise ValueError("Tokenizer pad_token_id is required")
        if not packed_ids:
            raise ValueError("No training chunks produced in collator.")
        mlen = max(len(v) for v in packed_ids)
        x = torch.full((len(batch), mlen), pad, dtype=torch.long)
        a = torch.zeros((len(batch), mlen), dtype=torch.long)
        y = torch.full((len(batch), mlen), -100, dtype=torch.long)
        for i, (v, l) in enumerate(zip(packed_ids, packed_lbl)):
            n = len(v)
            x[i, :n] = torch.tensor(v)
            a[i, :n] = 1
            y[i, :n] = torch.tensor(l)
        return {"input_ids": x, "attention_mask": a, "labels": y}

    return collate


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)

    ds = ChatDataset(args.train_file)
    print(f"Loaded samples: {len(ds)}")
    if args.expected_samples and len(ds) != args.expected_samples:
        raise ValueError(f"Expected {args.expected_samples}, got {len(ds)}")

    tok = AutoTokenizer.from_pretrained(args.model_name_or_path, use_fast=True)
    if not hasattr(tok, "apply_chat_template"):
        raise ValueError("Tokenizer must support apply_chat_template().")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token if tok.eos_token is not None else "<|pad|>"

    chunk_ds = TokenizedChunkDataset(
        ds.samples,
        tok,
        max_len=args.max_seq_length,
        chunk_long_samples=args.chunk_long_samples,
        chunk_overlap=args.chunk_overlap,
    )

    model_kwargs: dict = {}
    if args.bf16:
        model_kwargs["torch_dtype"] = torch.bfloat16
    elif args.fp16:
        model_kwargs["torch_dtype"] = torch.float16

    model = AutoModelForCausalLM.from_pretrained(args.model_name_or_path, **model_kwargs)
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    if hasattr(model.config, "use_cache"):
        model.config.use_cache = False

    try:
        from peft import LoraConfig, get_peft_model
    except Exception as exc:
        raise RuntimeError("Missing PEFT dependency. Install with: pip install peft") from exc

    target_modules = [x.strip() for x in args.target_modules.split(",") if x.strip()]
    if not target_modules:
        raise ValueError("target_modules is empty.")
    modules_to_save = [x.strip() for x in args.modules_to_save.split(",") if x.strip()]
    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
        modules_to_save=(modules_to_save or None),
    )
    model = get_peft_model(model, lora_cfg)
    if hasattr(model, "print_trainable_parameters"):
        model.print_trainable_parameters()

    lens = chunk_ds.raw_lengths
    over = sum(1 for n in lens if n > args.max_seq_length)
    p95 = lens[int(0.95 * (len(lens) - 1))]
    print(f"Token length stats: min={lens[0]} p95={p95} max={lens[-1]} over_limit({args.max_seq_length})={over}")
    if args.chunk_long_samples:
        print(
            "Chunking enabled: "
            f"max_seq_length={args.max_seq_length} chunk_overlap={args.chunk_overlap} "
            f"total_chunks={len(chunk_ds)}"
        )
    if args.strict_no_truncation and over and (not args.chunk_long_samples):
        raise ValueError(
            f"strict_no_truncation enabled but {over} samples exceed max_seq_length={args.max_seq_length}"
        )

    targs = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type=args.lr_scheduler_type,
        weight_decay=args.weight_decay,
        max_grad_norm=args.max_grad_norm,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        save_only_model=args.save_only_model,
        bf16=args.bf16,
        fp16=args.fp16,
        report_to=[],
        remove_unused_columns=False,
        seed=args.seed,
    )
    trainer_kwargs = {
        "model": model,
        "args": targs,
        "train_dataset": chunk_ds,
        "data_collator": make_collator(tok),
    }
    trainer_sig = inspect.signature(Trainer.__init__)
    if "processing_class" in trainer_sig.parameters:
        trainer_kwargs["processing_class"] = tok
    elif "tokenizer" in trainer_sig.parameters:
        trainer_kwargs["tokenizer"] = tok
    trainer = Trainer(**trainer_kwargs)
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint.strip() or None)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(out))
    tok.save_pretrained(str(out))
    meta = {
        "base_model": args.model_name_or_path,
        "train_file": args.train_file,
        "lora": {
            "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout,
            "target_modules": target_modules,
            "modules_to_save": modules_to_save,
        },
        "train": {
            "max_seq_length": args.max_seq_length,
            "chunk_long_samples": args.chunk_long_samples,
            "chunk_overlap": args.chunk_overlap,
        },
    }
    (out / "adapter_train_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved adapter to: {out}")


if __name__ == "__main__":
    main()
