from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cb8_bootcert.py"
NOTEBOOKS = [
    Path(r"N:\Research\AENAIMO260_0_2_3_BENCHMARKGRADE_V1.ipynb"),
    Path(r"N:\Research\AEN_Valid_Canons\AENAIMO260_0_2_3_BENCHMARKGRADE.ipynb"),
]
COPY_TARGET = Path(r"N:\Research\cb8_bootcert.py")


def _cb8_source_lines() -> list[str]:
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(SOURCE), "exec")
    return source.splitlines(keepends=True)


def _is_cb8_cell(cell: dict[str, object]) -> bool:
    if cell.get("cell_type") != "code":
        return False
    source = "".join(cell.get("source", []))  # type: ignore[arg-type]
    return (
        "CB08_RUNTIME_REVISION" in source
        and "def start_aen_runtime" in source
        and "Load Athena-Artemis-Aria Sessions" in source
    )


def sync_notebook(path: Path, source_lines: list[str]) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for cell in notebook.get("cells", []):
        if not isinstance(cell, dict) or not _is_cb8_cell(cell):
            continue
        backup = path.with_suffix(path.suffix + ".pre_v146_memory_first_bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        cell["source"] = list(source_lines)
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"synced CB08: {path}")
        return
    raise RuntimeError(f"CB08 cell not found: {path}")


def main() -> int:
    source_lines = _cb8_source_lines()
    for notebook in NOTEBOOKS:
        sync_notebook(notebook, source_lines)
    COPY_TARGET.write_text("".join(source_lines), encoding="utf-8")
    print(f"synced copy: {COPY_TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
