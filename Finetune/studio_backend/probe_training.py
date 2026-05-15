from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def fail(stage: str, exc: Exception | str) -> None:
    message = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    print(json.dumps({"ok": False, "stage": stage, "error": message}))
    raise SystemExit(0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe a finetune dataset and runtime for Finetune Studio.")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--train-file", required=True)
    return parser.parse_args()


def load_samples(path: Path) -> list[list[dict[str, str]]]:
    samples: list[list[dict[str, str]]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            messages = payload.get("messages")
            if not isinstance(messages, list) or not messages:
                raise ValueError(f"Line {line_number}: missing non-empty 'messages' list")
            samples.append(messages)
    if not samples:
        raise ValueError("No usable training samples found")
    return samples


def main() -> None:
    args = parse_args()
    model_path = Path(args.model_path)
    train_file = Path(args.train_file)

    try:
        import accelerate
        import torch
        import transformers
        from transformers import AutoTokenizer
    except Exception as exc:  # pragma: no cover - depends on local env
        fail("imports", exc)

    if not model_path.exists():
        fail("model_path", f"Model path not found: {model_path}")
    if not train_file.exists():
        fail("train_file", f"Train file not found: {train_file}")

    try:
        samples = load_samples(train_file)
    except Exception as exc:
        fail("dataset_parse", exc)

    try:
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), use_fast=True)
        if not hasattr(tokenizer, "apply_chat_template"):
            raise ValueError("Tokenizer must support apply_chat_template()")
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token if tokenizer.eos_token is not None else "<|pad|>"
    except Exception as exc:
        fail("tokenizer", exc)

    lengths: list[int] = []
    try:
        for messages in samples:
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            lengths.append(len(tokenizer(rendered, add_special_tokens=False)["input_ids"]))
    except Exception as exc:
        fail("token_lengths", exc)

    lengths.sort()
    p95_index = int(0.95 * (len(lengths) - 1))
    payload = {
        "ok": True,
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "accelerate_version": accelerate.__version__,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_version": torch.version.cuda or "",
        "device_count": int(torch.cuda.device_count()),
        "total_vram_gib": round(
            torch.cuda.get_device_properties(0).total_memory / (1024 ** 3),
            2,
        )
        if torch.cuda.is_available() and torch.cuda.device_count() > 0
        else 0.0,
        "tokenizer_class": type(tokenizer).__name__,
        "sample_count": len(samples),
        "min_tokens": lengths[0],
        "p95_tokens": lengths[p95_index],
        "max_tokens": lengths[-1],
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
