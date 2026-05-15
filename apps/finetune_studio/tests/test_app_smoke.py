from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PYSIDE6_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is required for UI smoke tests.")
class FinetuneStudioUiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_window_builds_expected_tabs(self) -> None:
        from apps.finetune_studio.app import FinetuneStudioWindow

        window = FinetuneStudioWindow()
        labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]
        self.assertEqual(labels, ["Overview", "Compose", "Data", "Arguments", "Jobs"])
        self.assertGreaterEqual(window.preset_combo.count(), 3)
        window.close()


if __name__ == "__main__":
    unittest.main()
