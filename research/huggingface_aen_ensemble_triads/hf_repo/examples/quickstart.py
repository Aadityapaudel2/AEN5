from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aen_ensemble_triads import AEN


def main() -> None:
    aen = AEN.from_pretrained(str(ROOT), profile="clean_aime2026", long_context="auto")
    print(aen.describe())


if __name__ == "__main__":
    main()
