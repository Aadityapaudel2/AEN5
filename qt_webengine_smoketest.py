#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from qt_ui import ASSETS_HTML, QT_BOOTSTRAP_LOG, append_qt_bootstrap_log, ensure_logs  # noqa: E402

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402


def main() -> None:
    ensure_logs()
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        print("DISPLAY is not set. Run this from XRDP/X11.", file=sys.stderr)
        raise SystemExit(1)

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    view = QWebEngineView()

    result: dict[str, object] = {
        "display": os.environ.get("DISPLAY", ""),
        "asset": str(ASSETS_HTML),
        "loaded": False,
        "url": "",
    }

    def _on_loaded(ok: bool) -> None:
        result["loaded"] = bool(ok)
        result["url"] = view.url().toString()
        append_qt_bootstrap_log(f"smoketest: {json.dumps(result, ensure_ascii=False)}")
        print(json.dumps(result, ensure_ascii=False))
        QTimer.singleShot(150, app.quit)

    view.loadFinished.connect(_on_loaded)
    view.resize(960, 640)
    view.setUrl(ASSETS_HTML.as_uri())
    view.show()
    QTimer.singleShot(4000, lambda: (_on_loaded(False) if result["loaded"] is False else None))
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
