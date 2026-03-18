from __future__ import annotations

import sys

from desktop_app.main import main


def _compat_argv(argv: list[str]) -> list[str]:
    cleaned = [argv[0]]
    skip_next = False
    for idx, item in enumerate(argv[1:], start=1):
        if skip_next:
            skip_next = False
            continue
        if item in {"--port", "--path-prefix"}:
            skip_next = True
            continue
        cleaned.append(item)
    return cleaned


if __name__ == "__main__":
    sys.argv = _compat_argv(sys.argv)
    main()
