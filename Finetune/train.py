#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch
from torch.utils.data import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

ROLES = {"system", "user", "assistant"}
FLAG_ARGS = ("save_only_model", "strict_no_truncation", "bf16", "fp16", "gradient_checkpointing")


@dataclass(frozen=True)
class NumericArg:
    name: str
    arg_type: type
    default: int | float | str


NUMERIC_ARGS = (
    NumericArg("max_seq_length", int, 2048),
    NumericArg("per_device_train_batch_size", int, 1),
    NumericArg("gradient_accumulation_steps", int, 8),
    NumericArg("learning_rate", float, 2e-5),
    NumericArg("num_train_epochs", float, 3.0),
    NumericArg("warmup_ratio", float, 0.03),
    NumericArg("lr_scheduler_type", str, "linear"),
    NumericArg("weight_decay", float, 0.0),
    NumericArg("max_grad_norm", float, 1.0),
    NumericArg("logging_steps", int, 10),
    NumericArg("save_steps", int, 200),
    NumericArg("save_total_limit", int, 2),
    NumericArg("expected_samples", int, 0),
    NumericArg("seed", int, 777),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact Qwen chat SFT trainer")
    for name in ("model_name_or_path", "train_file", "output_dir"):
        parser.add_argument(f"--{name}", required=True)
    for arg in NUMERIC_ARGS:
        parser.add_argument(f"--{arg.name}", type=arg.arg_type, default=arg.default)
    for name in FLAG_ARGS:
        parser.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--resume_from_checkpoint", default="")
    return parser.parse_args()


def normalize_messages(messages: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        if role in ROLES and content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def render_messages(tokenizer: AutoTokenizer, messages: list[dict[str, str]], *, add_generation_prompt: bool = False) -> str:
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_generation_prompt)


def encode_ids(tokenizer: AutoTokenizer, text: str) -> list[int]:
    return tokenizer(text, add_special_tokens=False)["input_ids"]


class ChatDataset(Dataset):
    def __init__(self, path: str):
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Train file not found: {file_path}")
        self.samples: list[list[dict[str, str]]] = []
        with file_path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                payload = json.loads(raw)
                messages = payload.get("messages")
                if not isinstance(messages, list):
                    raise ValueError(f"Line {line_number}: missing 'messages' list")
                cleaned = normalize_messages(messages)
                if cleaned:
                    self.samples.append(cleaned)
        if not self.samples:
            raise ValueError("No usable training samples found")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, list[dict[str, str]]]:
        return {"messages": self.samples[index]}


def build_collator(tokenizer: AutoTokenizer, max_seq_length: int):
    def collate(batch: list[dict[str, list[dict[str, str]]]]) -> dict[str, torch.Tensor]:
        input_rows: list[list[int]] = []
        label_rows: list[list[int]] = []
        for row in batch:
            messages = row["messages"]
            input_ids = encode_ids(tokenizer, render_messages(tokenizer, messages))
            labels = [-100] * len(input_ids)
            for index, message in enumerate(messages):
                if message["role"] != "assistant":
                    continue
                start = min(len(encode_ids(tokenizer, render_messages(tokenizer, messages[:index], add_generation_prompt=True))), len(input_ids))
                end = min(len(encode_ids(tokenizer, render_messages(tokenizer, messages[: index + 1]))), len(input_ids))
                if end > start:
                    labels[start:end] = input_ids[start:end]
            input_rows.append(input_ids[:max_seq_length])
            label_rows.append(labels[:max_seq_length])

        pad_token_id = tokenizer.pad_token_id
        if pad_token_id is None:
            raise ValueError("Tokenizer pad_token_id is required")

        max_width = max(len(row) for row in input_rows)
        inputs = torch.full((len(batch), max_width), pad_token_id, dtype=torch.long)
        attention = torch.zeros((len(batch), max_width), dtype=torch.long)
        labels = torch.full((len(batch), max_width), -100, dtype=torch.long)
        for row_index, (input_row, label_row) in enumerate(zip(input_rows, label_rows)):
            width = len(input_row)
            inputs[row_index, :width] = torch.tensor(input_row)
            attention[row_index, :width] = 1
            labels[row_index, :width] = torch.tensor(label_row)
        return {"input_ids": inputs, "attention_mask": attention, "labels": labels}

    return collate


def token_lengths(tokenizer: AutoTokenizer, samples: list[list[dict[str, str]]]) -> list[int]:
    return sorted(len(encode_ids(tokenizer, render_messages(tokenizer, sample))) for sample in samples)


def print_length_stats(lengths: list[int], max_seq_length: int) -> int:
    over_limit = sum(1 for length in lengths if length > max_seq_length)
    p95_index = int(0.95 * (len(lengths) - 1))
    print(
        "Token length stats: "
        f"min={lengths[0]} p95={lengths[p95_index]} max={lengths[-1]} "
        f"over_limit({max_seq_length})={over_limit}"
    )
    return over_limit


def build_training_args(args: argparse.Namespace) -> TrainingArguments:
    return TrainingArguments(
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


def build_trainer(
    *,
    model: AutoModelForCausalLM,
    training_args: TrainingArguments,
    dataset: ChatDataset,
    collator,
    tokenizer: AutoTokenizer,
) -> Trainer:
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": dataset,
        "data_collator": collator,
    }
    trainer_signature = inspect.signature(Trainer.__init__).parameters
    if "processing_class" in trainer_signature:
        trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_signature:
        trainer_kwargs["tokenizer"] = tokenizer
    return Trainer(**trainer_kwargs)


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)

    dataset = ChatDataset(args.train_file)
    print(f"Loaded samples: {len(dataset)}")
    if args.expected_samples and len(dataset) != args.expected_samples:
        raise ValueError(f"Expected {args.expected_samples}, got {len(dataset)}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_name_or_path, use_fast=True)
    if not hasattr(tokenizer, "apply_chat_template"):
        raise ValueError("Tokenizer must support apply_chat_template()")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token if tokenizer.eos_token is not None else "<|pad|>"

    model = AutoModelForCausalLM.from_pretrained(args.model_name_or_path)
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    lengths = token_lengths(tokenizer, dataset.samples)
    over_limit = print_length_stats(lengths, args.max_seq_length)
    if args.strict_no_truncation and over_limit:
        raise ValueError(
            "strict_no_truncation enabled but "
            f"{over_limit} samples exceed max_seq_length={args.max_seq_length}"
        )

    trainer = build_trainer(
        model=model,
        training_args=build_training_args(args),
        dataset=dataset,
        collator=build_collator(tokenizer, args.max_seq_length),
        tokenizer=tokenizer,
    )
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint.strip() or None)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
