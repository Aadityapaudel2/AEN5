#!/usr/bin/env python3
"""
Build chat-SFT artifacts from turn-level JSONL.

Input row:
  {"role":"student|teacher","metadata":{"dialogue_id":...,"turn":...},"content":"..."}

Output row:
  {"meta": {...}, "messages": [{"role":"user|assistant","content":"..."}, ...]}
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "trainingdata" / "bhagavadgita" / "bhagavaggitatrainingdata.jsonl"
DEFAULT_OUTPUT = ROOT / "trainingdata" / "bhagavadgita" / "bhagavaggitatrainingdata_train.jsonl"
DEFAULT_ASSISTANT_ROLE = "teacher"
DEFAULT_ARTIFACT_STYLE = "assistant_turn"
ROLE_PREFIXES = ("user:", "assistant:", "athena:", "teacher:", "student:")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert turn-level JSONL into chat SFT artifacts.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--assistant_role", choices=["student", "teacher"], default=DEFAULT_ASSISTANT_ROLE)
    parser.add_argument("--artifact_style", choices=["dialogue", "assistant_turn"], default=DEFAULT_ARTIFACT_STYLE)
    parser.add_argument("--max_context_messages", type=int, default=12)
    parser.add_argument("--min_messages", type=int, default=2)
    parser.add_argument("--drop_empty", action="store_true")
    parser.add_argument("--require_user_before_assistant", action="store_true")
    parser.add_argument("--merge_consecutive_same_role", action="store_true")
    parser.add_argument("--strip_role_prefixes", action="store_true")
    return parser.parse_args()


def clean_text(text: str, *, strip_role_prefixes: bool) -> str:
    cleaned = (text or "").replace("\r\n", "\n").strip()
    if not strip_role_prefixes:
        return cleaned
    lowered = cleaned.lower()
    for prefix in ROLE_PREFIXES:
        if lowered.startswith(prefix):
            return cleaned[len(prefix) :].lstrip()
    return cleaned


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line:
                yield json.loads(line)


def load_by_dialogue(path: Path) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(path):
        dialogue_id = row.get("metadata", {}).get("dialogue_id")
        grouped[dialogue_id].append(row)
    return grouped


def sorted_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(turns, key=lambda row: row.get("metadata", {}).get("turn", 0))


def map_messages(
    turns: list[dict[str, Any]],
    *,
    assistant_role: str,
    strip_role_prefixes: bool,
) -> list[dict[str, Any]]:
    source_user_role = "teacher" if assistant_role == "student" else "student"
    mapped: list[dict[str, Any]] = []
    for turn in turns:
        source_role = turn.get("role")
        content = clean_text(turn.get("content", ""), strip_role_prefixes=strip_role_prefixes)
        if not content:
            continue
        if source_role == assistant_role:
            role = "assistant"
        elif source_role == source_user_role:
            role = "user"
        else:
            continue
        mapped.append(
            {
                "role": role,
                "content": content,
                "source_turn": turn.get("metadata", {}).get("turn"),
            }
        )
    return mapped


def merge_adjacent_same_role(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not messages:
        return []
    merged = [dict(messages[0])]
    for message in messages[1:]:
        previous = merged[-1]
        if previous["role"] != message["role"]:
            merged.append(dict(message))
            continue
        previous["content"] = f"{previous['content']}\n\n{message['content']}".strip()
        previous["source_turn"] = message.get("source_turn", previous.get("source_turn"))
    return merged


def emit_dialogue_sample(
    *,
    dialogue_id: Any,
    meta: dict[str, Any],
    messages: list[dict[str, Any]],
    min_messages: int,
    drop_empty: bool,
) -> list[dict[str, Any]]:
    assistant_count = sum(1 for message in messages if message["role"] == "assistant")
    if drop_empty and assistant_count == 0:
        return []
    if len(messages) < min_messages:
        return []
    payload = dict(meta)
    payload["dialogue_id"] = dialogue_id
    return [{"meta": payload, "messages": _strip_source_turns(messages)}]


def emit_assistant_turn_samples(
    *,
    dialogue_id: Any,
    meta: dict[str, Any],
    messages: list[dict[str, Any]],
    max_context_messages: int,
    min_messages: int,
    drop_empty: bool,
    require_user_before_assistant: bool,
) -> list[dict[str, Any]]:
    assistant_positions = [index for index, message in enumerate(messages) if message["role"] == "assistant"]
    if drop_empty and not assistant_positions:
        return []

    samples: list[dict[str, Any]] = []
    for target_index in assistant_positions:
        start_index = max(0, target_index - max_context_messages + 1)
        window = messages[start_index : target_index + 1]

        first_user_index = next((index for index, message in enumerate(window) if message["role"] == "user"), None)
        if first_user_index is not None and first_user_index > 0:
            window = window[first_user_index:]
        if len(window) < min_messages:
            continue
        if require_user_before_assistant and not any(message["role"] == "user" for message in window[:-1]):
            continue

        payload = dict(meta)
        payload["dialogue_id"] = dialogue_id
        payload["sample_style"] = "assistant_turn"
        payload["target_index_in_window"] = len(window) - 1
        payload["target_source_turn"] = messages[target_index].get("source_turn")
        samples.append({"meta": payload, "messages": _strip_source_turns(window)})
    return samples


def _strip_source_turns(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"role": message["role"], "content": message["content"]} for message in messages]


def _sample_messages(
    *,
    dialogue_id: Any,
    meta: dict[str, Any],
    messages: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    if args.artifact_style == "dialogue":
        return emit_dialogue_sample(
            dialogue_id=dialogue_id,
            meta=meta,
            messages=messages,
            min_messages=args.min_messages,
            drop_empty=bool(args.drop_empty),
        )
    return emit_assistant_turn_samples(
        dialogue_id=dialogue_id,
        meta=meta,
        messages=messages,
        max_context_messages=max(2, args.max_context_messages),
        min_messages=max(2, args.min_messages),
        drop_empty=bool(args.drop_empty),
        require_user_before_assistant=bool(args.require_user_before_assistant),
    )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grouped = load_by_dialogue(input_path)
    output_samples = 0
    output_messages = 0
    source_turns = 0

    with output_path.open("w", encoding="utf-8") as handle:
        for dialogue_id, turns in sorted(grouped.items(), key=lambda item: (item[0] is None, item[0])):
            source_turns += len(turns)
            ordered_turns = sorted_turns(turns)
            meta = dict(ordered_turns[0].get("metadata", {})) if ordered_turns else {}
            meta["dialogue_id"] = dialogue_id

            messages = map_messages(
                ordered_turns,
                assistant_role=args.assistant_role,
                strip_role_prefixes=bool(args.strip_role_prefixes),
            )
            if args.merge_consecutive_same_role:
                messages = merge_adjacent_same_role(messages)

            samples = _sample_messages(dialogue_id=dialogue_id, meta=meta, messages=messages, args=args)
            for sample in samples:
                handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
                output_samples += 1
                output_messages += len(sample.get("messages", []))

    average_messages = (output_messages / output_samples) if output_samples else 0.0
    print(f"Input dialogues: {len(grouped)}")
    print(f"Input turns: {source_turns}")
    print(f"Output samples: {output_samples}")
    print(f"Average messages/sample: {average_messages:.2f}")
    print(f"Wrote: {output_path}")


if __name__ == "__main__":
    main()
