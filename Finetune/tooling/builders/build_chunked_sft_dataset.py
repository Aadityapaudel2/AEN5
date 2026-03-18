from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from transformers import AutoTokenizer


CONTINUE_PROMPT = (
    "Continue the solution carefully from the previous point. Preserve correctness and "
    "complete the remaining reasoning."
)
SAFETY_MARGIN = 16
MAX_ASSISTANT_CHUNK_TOKENS = 1600
ROW_SHAPE = {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}


def load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        raw = line.strip()
        if raw:
            rows.append(json.loads(raw))
    return rows


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def render_messages(tokenizer: AutoTokenizer, messages: list[dict[str, str]]) -> str:
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)


def token_length(tokenizer: AutoTokenizer, messages: list[dict[str, str]]) -> int:
    rendered = render_messages(tokenizer, messages)
    return len(tokenizer(rendered, add_special_tokens=False)["input_ids"])


def fits(tokenizer: AutoTokenizer, messages: list[dict[str, str]], max_seq_length: int) -> bool:
    return token_length(tokenizer, messages) <= max_seq_length - SAFETY_MARGIN


def content_token_length(tokenizer: AutoTokenizer, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def split_sentences(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\\])", normalized)
    cleaned = [part.strip() for part in parts if part.strip()]
    return cleaned if len(cleaned) > 1 else [normalized]


def split_lines(text: str) -> list[str]:
    parts = [line.strip() for line in text.splitlines() if line.strip()]
    return parts if len(parts) > 1 else [text.strip()]


def split_unit_by_tokens(tokenizer: AutoTokenizer, text: str, context: list[dict[str, str]], max_seq_length: int) -> list[str]:
    token_ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    if not token_ids:
        return [text.strip()]
    low = 1
    high = len(token_ids)
    best = 1
    while low <= high:
        mid = (low + high) // 2
        candidate = tokenizer.decode(token_ids[:mid], skip_special_tokens=True).strip()
        if candidate and fits(tokenizer, context + [{"role": "assistant", "content": candidate}], max_seq_length):
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    head = tokenizer.decode(token_ids[:best], skip_special_tokens=True).strip()
    tail = tokenizer.decode(token_ids[best:], skip_special_tokens=True).strip()
    if not head:
        head = tokenizer.decode(token_ids[:1], skip_special_tokens=True).strip() or text[:64].strip()
        tail = text[len(head):].strip()
    return [part for part in (head, tail) if part]


def split_unit_to_fit(tokenizer: AutoTokenizer, unit: str, context: list[dict[str, str]], max_seq_length: int) -> list[str]:
    for splitter in (split_sentences, split_lines):
        parts = splitter(unit)
        if len(parts) > 1:
            return parts
    return split_unit_by_tokens(tokenizer, unit, context, max_seq_length)


def chunk_messages(
    tokenizer: AutoTokenizer,
    messages: list[dict[str, str]],
    max_seq_length: int,
) -> list[list[dict[str, str]]]:
    if not messages or messages[-1]["role"] != "assistant":
        return [messages]

    base_messages = [dict(message) for message in messages[:-1]]
    assistant_text = str(messages[-1]["content"]).strip()
    units = [part.strip() for part in assistant_text.split("\n\n") if part.strip()]
    if not units:
        return [messages]

    outputs: list[list[dict[str, str]]] = []
    previous_chunk: str | None = None
    remaining = list(units)
    base_length = token_length(tokenizer, base_messages)
    chunk_token_target = min(
        MAX_ASSISTANT_CHUNK_TOKENS,
        max(512, (max_seq_length - base_length - 256) // 2),
    )

    while remaining:
        context = [dict(message) for message in base_messages]
        if previous_chunk:
            context.append({"role": "assistant", "content": previous_chunk})
            context.append({"role": "user", "content": CONTINUE_PROMPT})

        current_parts: list[str] = []
        while remaining:
            candidate_unit = remaining[0]
            trial_text = "\n\n".join(current_parts + [candidate_unit]).strip()
            if (
                trial_text
                and content_token_length(tokenizer, trial_text) <= chunk_token_target
                and fits(tokenizer, context + [{"role": "assistant", "content": trial_text}], max_seq_length)
            ):
                current_parts.append(candidate_unit)
                remaining.pop(0)
                continue
            if current_parts:
                break
            smaller_parts = split_unit_to_fit(tokenizer, candidate_unit, context, max_seq_length)
            if len(smaller_parts) == 1 and smaller_parts[0].strip() == candidate_unit.strip():
                raise ValueError("Unable to fit assistant chunk within max_seq_length")
            remaining = smaller_parts + remaining[1:]

        if not current_parts:
            raise ValueError("Failed to produce a non-empty assistant continuation chunk")

        chunk_text = "\n\n".join(current_parts).strip()
        outputs.append(context + [{"role": "assistant", "content": chunk_text}])
        previous_chunk = chunk_text

    return outputs


def validate_rows(tokenizer: AutoTokenizer, rows: list[dict[str, object]], max_seq_length: int) -> list[int]:
    over_limit: list[int] = []
    for index, row in enumerate(rows, start=1):
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"Row {index}: missing messages list")
        length = token_length(tokenizer, messages)  # type: ignore[arg-type]
        if length > max_seq_length:
            over_limit.append(index)
    return over_limit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a continuation-chunked SFT dataset for long math rows.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--max-seq-length", type=int, default=4096)
    parser.add_argument(
        "--drop-overlong-base",
        action="store_true",
        help="Skip rows whose non-assistant context already exceeds max_seq_length.",
    )
    parser.add_argument(
        "--drop-unchunkable",
        action="store_true",
        help="Skip rows that still cannot be chunked to fit max_seq_length.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    source_rows = load_rows(args.source)

    chunked_rows: list[dict[str, object]] = []
    chunk_counts = Counter()
    over_limit_before = 0
    dropped_base_rows: list[int] = []
    dropped_unchunkable_rows: list[int] = []

    for index, row in enumerate(source_rows, start=1):
        messages = row.get("messages")
        if not isinstance(messages, list):
            raise ValueError(f"Row {index}: missing messages list")
        length_before = token_length(tokenizer, messages)  # type: ignore[arg-type]
        if length_before > args.max_seq_length:
            over_limit_before += 1
        if messages[:-1]:
            base_length = token_length(tokenizer, messages[:-1])  # type: ignore[arg-type]
            if base_length > args.max_seq_length - SAFETY_MARGIN:
                if args.drop_overlong_base:
                    dropped_base_rows.append(index)
                    continue
                raise ValueError(
                    f"Row {index}: non-assistant context already exceeds max_seq_length "
                    f"({base_length} > {args.max_seq_length - SAFETY_MARGIN})"
                )
        try:
            row_chunks = chunk_messages(tokenizer, messages, args.max_seq_length)  # type: ignore[arg-type]
        except ValueError as exc:
            if args.drop_unchunkable and "Unable to fit assistant chunk within max_seq_length" in str(exc):
                dropped_unchunkable_rows.append(index)
                continue
            raise
        chunk_counts[len(row_chunks)] += 1
        for chunk_messages_row in row_chunks:
            chunked_rows.append({"messages": chunk_messages_row})

    over_limit_after = validate_rows(tokenizer, chunked_rows, args.max_seq_length)
    if over_limit_after:
        raise ValueError(f"Chunked dataset still has rows over limit: {over_limit_after[:10]}")

    manifest = {
        "source_file": str(args.source),
        "output_file": str(args.output),
        "model": str(args.model),
        "max_seq_length": args.max_seq_length,
        "continue_prompt": CONTINUE_PROMPT,
        "row_shape": ROW_SHAPE,
        "source_row_count": len(source_rows),
        "output_row_count": len(chunked_rows),
        "source_rows_over_limit": over_limit_before,
        "dropped_base_rows": dropped_base_rows,
        "dropped_unchunkable_rows": dropped_unchunkable_rows,
        "chunk_distribution": {str(key): value for key, value in sorted(chunk_counts.items())},
    }

    write_jsonl(args.output, chunked_rows)
    write_json(args.manifest_output, manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
