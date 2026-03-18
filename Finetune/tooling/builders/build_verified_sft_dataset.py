from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ATHENA_ROOT = Path(r"D:\AthenaPlayground\AthenaV5")
AIMO_ROOT = ATHENA_ROOT / "evaluation" / "testdata" / "aimo"
LOGIC_TRAIN_ROOT = ATHENA_ROOT / "Finetune" / "trainingdata" / "logic_train33_sources"
LOGIC_SPLIT_MANIFEST = ATHENA_ROOT / "Finetune" / "trainingdata" / "logic_train_holdout_split_manifest.json"
VOE_ROOT = ATHENA_ROOT / "testdata_unpublished_2026-03-09" / "voe_1"
OUTPUT_DIR = ATHENA_ROOT / "Finetune" / "trainingdata"


MOJIBAKE_MARKERS = ("Ã", "â", "Î", "Ï", "Â")
TEXT_REPLACEMENTS = {
    "\ufeff": "",
    "\u00a0": " ",
    "â€”": "-",
    "â€“": "-",
    "âˆ’": "-",
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
    "â€˜": "'",
    "â€¦": "...",
}


@dataclass(frozen=True)
class SftExample:
    source_name: str
    split: str
    user: str
    assistant: str
    answer_display: str
    answer_numeric: int
    domain: str
    subgroup: str


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if raw:
            rows.append(json.loads(raw))
    return rows


def maybe_fix_mojibake(text: str) -> str:
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        for encoding in ("cp1252", "latin-1"):
            try:
                candidate = text.encode(encoding, errors="ignore").decode("utf-8")
            except UnicodeError:
                continue
            if sum(candidate.count(marker) for marker in MOJIBAKE_MARKERS) < sum(text.count(marker) for marker in MOJIBAKE_MARKERS):
                text = candidate
                break
    for old, new in TEXT_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def clean_text(text: str) -> str:
    text = maybe_fix_mojibake(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_lonely_outer_quote(text: str) -> str:
    if text.startswith('"') and text.count('"') == 1:
        return text[1:].strip()
    if text.startswith("'") and text.count("'") == 1:
        return text[1:].strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1].strip()
    return text


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_fingerprint(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def extract_structured_field(text: str, key: str, next_keys: list[str]) -> str:
    pattern = rf"^\s*{re.escape(key)}\s*:\s*(.*)$"
    match = re.search(pattern, text, flags=re.M)
    if not match:
        return ""
    start = match.end()
    end = len(text)
    for next_key in next_keys:
        next_match = re.search(rf"^\s*{re.escape(next_key)}\s*:", text[start:], flags=re.M)
        if next_match:
            end = min(end, start + next_match.start())
    head = match.group(1).strip()
    body = text[start:end]
    combined = (head + "\n" + body).strip()
    combined = re.sub(r"^[>|]\s*", "", combined)
    combined = clean_text(combined)
    return strip_lonely_outer_quote(combined)


def extract_final_answer(text: str) -> str | None:
    patterns = [
        r"^\s*final\s*:\s*['\"]?(\d+)['\"]?(?:['\"])?\s*$",
        r"Hence the correct solution is:\s*(\d+)",
        r"Answer:\s*(?:\\boxed\{)?(\d+)(?:\})?\.?",
        r"^\s*(\d+)\s*$",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.I | re.M)
        if matches:
            return matches[-1]
    return None


def remove_logic_answer_wrappers(answer_block: str) -> str:
    text = clean_text(answer_block)
    text = re.sub(r"^\s*explanation\s*:\s*\|?\s*", "", text, flags=re.I)
    text = re.sub(r"\n\s*final\s*:\s*['\"]?\d+['\"]?\s*$", "", text, flags=re.I)
    return strip_lonely_outer_quote(clean_text(text))


def split_aimo_problem_file(text: str) -> tuple[str, str, str]:
    cleaned = clean_text(text)
    marker = "\nSolution.\n"
    if marker not in cleaned:
        raise ValueError("Missing 'Solution.' marker")
    preamble, solution_tail = cleaned.split(marker, 1)
    parts = preamble.split("\n\n", 1)
    if len(parts) != 2:
        raise ValueError("Unable to split title and problem statement")
    title, problem = parts[0].strip(), parts[1].strip()

    lines = [line.rstrip() for line in solution_tail.splitlines()]
    nonempty = [line.strip() for line in lines if line.strip()]
    final_display = nonempty[-1] if nonempty and re.fullmatch(r"\d+", nonempty[-1]) else extract_final_answer(solution_tail)
    if not final_display:
        raise ValueError("Missing final numeric answer")

    while lines and not lines[-1].strip():
        lines.pop()
    if lines and re.fullmatch(r"\d+", lines[-1].strip()):
        lines.pop()
    solution_body = "\n".join(lines).strip()
    solution_body = re.split(r"\n(?:\d+\)\s+)?Uniqueness Test\b", solution_body, maxsplit=1, flags=re.I)[0].strip()
    solution_body = re.sub(r"(?m)^Answer:\s*(?:\\boxed\{)?\d+(?:\})?\.?\s*$", "", solution_body).strip()
    solution_body = clean_text(solution_body)
    if solution_body.startswith("Solution."):
        solution_body = solution_body[len("Solution."):].strip()

    return title, problem, solution_body if solution_body else "", final_display


def build_aimo_examples() -> list[SftExample]:
    manifest_rows = load_jsonl(AIMO_ROOT / "manifest.jsonl")
    examples: list[SftExample] = []
    for row in sorted(manifest_rows, key=lambda item: str(item["filename"])):
        filename = str(row["filename"])
        path = AIMO_ROOT / str(row["problem_path"])
        title, problem, solution_body, final_display = split_aimo_problem_file(path.read_text(encoding="utf-8", errors="replace"))
        manifest_answer = str(row["answer"])
        if int(final_display) != int(manifest_answer):
            raise ValueError(f"AIMO answer mismatch for {filename}: file={final_display} manifest={manifest_answer}")
        assistant = "Solution.\n"
        if solution_body:
            assistant += solution_body + "\n\n"
        assistant += f"Final answer: {final_display}"
        examples.append(
            SftExample(
                source_name=filename,
                split="aimo_verified",
                user=problem.strip(),
                assistant=assistant.strip(),
                answer_display=final_display,
                answer_numeric=int(final_display),
                domain=str(row["domain"]),
                subgroup=str(row["subdomain"]),
            )
        )
    return examples


def build_logic_examples() -> list[SftExample]:
    manifest = load_json(LOGIC_SPLIT_MANIFEST)
    train_root = Path(str(manifest["train_output"]))
    logic_train_manifest = load_json(train_root / "manifest.json")
    manifest_entries = {
        str(item["source_name"]): str(item["final_answer"])
        for item in logic_train_manifest["files"]
    }
    examples: list[SftExample] = []
    for source_name in sorted(manifest_entries):
        path = train_root / source_name
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_text(raw_text)
        description = extract_structured_field(cleaned, "description", ["question", "answer", "final"])
        question = extract_structured_field(cleaned, "question", ["answer", "final"])
        answer_block = extract_structured_field(cleaned, "answer", ["final"])
        parsed_final_display = extract_final_answer(cleaned)
        manifest_final_display = manifest_entries[source_name]
        final_display = parsed_final_display or manifest_final_display
        if parsed_final_display and int(parsed_final_display) != int(manifest_final_display):
            raise ValueError(
                f"Logic answer mismatch for {source_name}: parsed={parsed_final_display} manifest={manifest_final_display}"
            )
        if not description or not question or not answer_block or not final_display:
            raise ValueError(f"Missing structured fields in logic source {source_name}")
        user = clean_text(f"{description}\n\n{question}")
        solution_body = remove_logic_answer_wrappers(answer_block)
        assistant = f"Solution.\n{solution_body}\n\nFinal answer: {final_display}"
        examples.append(
            SftExample(
                source_name=source_name,
                split="logic_train33",
                user=user.strip(),
                assistant=assistant.strip(),
                answer_display=final_display,
                answer_numeric=int(final_display),
                domain="logic",
                subgroup="training_selected",
            )
        )
    return examples


def to_messages_row(example: SftExample) -> dict[str, object]:
    return {
        "messages": [
            {"role": "user", "content": example.user},
            {"role": "assistant", "content": example.assistant},
        ]
    }


def validate_examples(examples: list[SftExample], expected_count: int, label: str) -> dict[str, int]:
    if len(examples) != expected_count:
        raise ValueError(f"{label}: expected {expected_count} rows, got {len(examples)}")

    seen_fingerprints: set[tuple[str, str]] = set()
    counts = Counter()
    for example in examples:
        if not example.user.strip():
            raise ValueError(f"{label}: empty user content in {example.source_name}")
        if not example.assistant.strip():
            raise ValueError(f"{label}: empty assistant content in {example.source_name}")
        if example.user.lower().startswith("user:") or example.assistant.lower().startswith("assistant:"):
            raise ValueError(f"{label}: role prefix leaked into content for {example.source_name}")
        if not re.search(rf"Final answer:\s*{re.escape(example.answer_display)}\s*$", example.assistant):
            raise ValueError(f"{label}: final answer missing or malformed in {example.source_name}")
        fingerprint = (normalize_for_fingerprint(example.user), normalize_for_fingerprint(example.assistant))
        if fingerprint in seen_fingerprints:
            raise ValueError(f"{label}: duplicate row detected for {example.source_name}")
        seen_fingerprints.add(fingerprint)
        counts[example.domain] += 1
    return dict(counts)


def build_manifest(
    aimo_examples: list[SftExample],
    logic_examples: list[SftExample],
    combined_examples: list[SftExample],
    output_paths: dict[str, str],
) -> dict[str, object]:
    logic_split_manifest = load_json(LOGIC_SPLIT_MANIFEST)
    return {
        "builder_script": str(OUTPUT_DIR.parent / "tooling" / "builders" / "build_verified_sft_dataset.py"),
        "trainer_path": str(ATHENA_ROOT / "Finetune" / "train.py"),
        "format": {
            "type": "jsonl_messages",
            "system_message_used": False,
            "row_shape": {
                "messages": [
                    {"role": "user", "content": "<clean problem statement>"},
                    {"role": "assistant", "content": "<clean worked solution ending with Final answer: ...>"},
                ]
            },
        },
        "source_roots": {
            "aimo": str(AIMO_ROOT),
            "logic_train33": str(LOGIC_TRAIN_ROOT),
            "logic_locked_eval": str(ATHENA_ROOT / "evaluation" / "testdata" / "logic"),
            "voe_locked_eval": str(VOE_ROOT),
        },
        "output_files": output_paths,
        "counts": {
            "aimo_verified_rows": len(aimo_examples),
            "logic_train33_rows": len(logic_examples),
            "combined_rows": len(combined_examples),
            "logic_locked_eval_rows": 7,
            "voe_locked_eval_rows": sum(1 for _ in VOE_ROOT.glob("*.tex")),
        },
        "aimo_domain_counts": dict(Counter(example.domain for example in aimo_examples)),
        "logic_policy": {
            "training_source": "selected non-bad logic files from logic_train33_sources",
            "excluded_known_bad_count": int(logic_split_manifest["known_bad_excluded_count"]),
            "held_out_internal_count": int(logic_split_manifest["held_out_count"]),
            "held_out_internal_names": list(logic_split_manifest["held_out_names"]),
            "locked_eval_excluded_from_training_count": int(logic_split_manifest["locked_eval_logic_count"]),
        },
        "skipped": {
            "logic_known_bad": list(logic_split_manifest["known_bad_excluded"]),
            "logic_internal_holdout": list(logic_split_manifest["held_out_names"]),
        },
        "ordering_policy": "deterministic_filename_sort; combined dataset is aimo rows followed by logic rows",
        "ready_for_immediate_use_with_train_py": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the canonical 125-row math+logic SFT dataset.")
    parser.add_argument("--aimo-output", type=Path, default=OUTPUT_DIR / "aimo_verified_sft.jsonl")
    parser.add_argument("--logic-output", type=Path, default=OUTPUT_DIR / "logic_verified_sft.jsonl")
    parser.add_argument("--combined-output", type=Path, default=OUTPUT_DIR / "math_plus_logic_verified_sft.jsonl")
    parser.add_argument("--manifest-output", type=Path, default=OUTPUT_DIR / "verified_sft_build_manifest.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    aimo_examples = build_aimo_examples()
    logic_examples = build_logic_examples()
    combined_examples = aimo_examples + logic_examples

    aimo_domains = validate_examples(aimo_examples, expected_count=92, label="aimo")
    validate_examples(logic_examples, expected_count=33, label="logic")
    validate_examples(combined_examples, expected_count=125, label="combined")

    write_jsonl(args.aimo_output, [to_messages_row(example) for example in aimo_examples])
    write_jsonl(args.logic_output, [to_messages_row(example) for example in logic_examples])
    write_jsonl(args.combined_output, [to_messages_row(example) for example in combined_examples])

    manifest = build_manifest(
        aimo_examples=aimo_examples,
        logic_examples=logic_examples,
        combined_examples=combined_examples,
        output_paths={
            "aimo_verified_sft.jsonl": str(args.aimo_output),
            "logic_verified_sft.jsonl": str(args.logic_output),
            "math_plus_logic_verified_sft.jsonl": str(args.combined_output),
        },
    )
    manifest["aimo_domain_counts"] = aimo_domains
    write_json(args.manifest_output, manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
