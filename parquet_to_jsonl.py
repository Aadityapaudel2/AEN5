PARQUET_PATH = r"N:\Downloads Chrome\train-00000-of-00001.parquet"
OUTPUT_JSONL_PATH = r"D:\AthenaPlayground\AthenaV5\train_p.jsonl"

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable


def _iter_rows_with_pyarrow(parquet_path: Path) -> Iterable[dict]:
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path)
    yield from table.to_pylist()


def _iter_rows_with_pandas(parquet_path: Path) -> Iterable[dict]:
    import pandas as pd

    frame = pd.read_parquet(parquet_path)
    yield from frame.to_dict(orient="records")


def iter_parquet_rows(parquet_path: Path) -> Iterable[dict]:
    try:
        yield from _iter_rows_with_pyarrow(parquet_path)
        return
    except ImportError:
        pass

    try:
        yield from _iter_rows_with_pandas(parquet_path)
        return
    except ImportError as exc:
        raise SystemExit(
            "Parquet support requires `pyarrow` or `pandas`.\n"
            "Example:\n"
            "  D:\\AthenaPlayground\\.venv\\Scripts\\python.exe -m pip install pyarrow"
        ) from exc


def _convert_to_jsonl(rows: list[dict], output_path: Path) -> int:
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def _convert_to_csv(rows: list[dict], output_path: Path) -> int:
    if not rows:
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("")
        return 0

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(str(key))

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return len(rows)


def convert(parquet_path: Path, output_path: Path) -> int:
    parquet_path = parquet_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    if not parquet_path.is_file():
        raise SystemExit(f"Parquet file not found: {parquet_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(iter_parquet_rows(parquet_path))
    suffix = output_path.suffix.lower()
    if suffix == ".csv":
        return _convert_to_csv(rows, output_path)
    if suffix in {"", ".jsonl"}:
        return _convert_to_jsonl(rows, output_path)
    raise SystemExit(f"Unsupported output format: {output_path.suffix}. Use .jsonl or .csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a Parquet file to JSONL or CSV.")
    parser.add_argument("parquet_path", nargs="?", default="", help="Input .parquet file")
    parser.add_argument("output_path", nargs="?", default="", help="Output .jsonl or .csv file (defaults next to input)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_parquet_path = args.parquet_path or PARQUET_PATH
    if not raw_parquet_path:
        raise SystemExit("Set PARQUET_PATH on the first line or pass a parquet path as an argument.")
    parquet_path = Path(raw_parquet_path)
    raw_output_path = args.output_path or OUTPUT_JSONL_PATH
    output_path = Path(raw_output_path) if raw_output_path else parquet_path.with_suffix(".jsonl")
    row_count = convert(parquet_path, output_path)
    print(f"Wrote {row_count} rows to {output_path.resolve()}")


if __name__ == "__main__":
    main()
