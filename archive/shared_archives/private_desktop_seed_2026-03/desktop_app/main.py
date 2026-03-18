from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional
from uuid import uuid4

BOOTSTRAP_ROOT = Path(__file__).resolve().parent.parent
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from athena_paths import get_default_chat_model_dir, get_desktop_image_stage_dir, get_desktop_transcript_html_path, get_log_root, get_root_dir
from browser.render import render_transcript_html
from desktop_engine import DesktopEngine, EngineEvent
from desktop_app.session_logger import DesktopSessionLogger

PROJECT_ROOT = get_root_dir()
TRANSCRIPT_HTML = get_desktop_transcript_html_path()
STAGE_DIR = get_desktop_image_stage_dir()
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault(
    "QT_LOGGING_RULES",
    "qt.webenginecontext.warning=false;qt.webenginecontext.info=false;qt.webenginecontext.debug=false;qt.qpa.gl=false",
)
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
_required_qt_flags = [
    "--no-sandbox",
    "--disable-gpu-sandbox",
    "--disable-gpu",
    "--disable-gpu-compositing",
    "--use-angle=swiftshader",
    "--disable-logging",
    "--log-level=3",
]
_existing_qt_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
_flag_set = set(_existing_qt_flags.split()) if _existing_qt_flags else set()
for _flag in _required_qt_flags:
    if _flag not in _flag_set:
        _existing_qt_flags = f"{_existing_qt_flags} {_flag}".strip()
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _existing_qt_flags

try:
    from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
    from PySide6.QtGui import QImage, QKeyEvent, QPixmap
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPlainTextEdit,
        QPushButton,
        QSizePolicy,
        QSplitter,
        QTextEdit,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "PySide6 + QtWebEngine is required for the desktop app.\n"
        "Install with:\n"
        "  D:\\AthenaPlayground\\.venv\\Scripts\\python.exe -m pip install PySide6 PySide6-Addons\n"
        f"\nImport error: {exc}"
    )


def _runtime_summary(snapshot: dict) -> str:
    tools_on = bool(snapshot.get("tools_enabled"))
    loaded = bool(snapshot.get("model_loaded", False))
    vision = bool(snapshot.get("supports_vision", False))
    sampling_enabled = bool(snapshot.get("sampling_enabled", True))
    load_error = snapshot.get("model_load_error", "") or "none"
    temperature = snapshot.get("temperature", "n/a")
    top_p = snapshot.get("top_p", "n/a")
    top_k = snapshot.get("top_k", "n/a")
    repetition_penalty = snapshot.get("repetition_penalty", "n/a")
    max_new_tokens = snapshot.get("max_new_tokens", "n/a")
    gui_config_path = snapshot.get("gui_config_path", "n/a")
    system_prompt_path = snapshot.get("system_prompt_path", "n/a")
    system_prompt_format = snapshot.get("system_prompt_format", "n/a")
    return (
        "Runtime\n"
        f"  Model: {snapshot.get('model_label') or 'unknown'}\n"
        f"  Device: {snapshot.get('device', 'unloaded')}\n"
        f"  Vision: {'on' if vision else 'off'}\n"
        "\n"
        "Features\n"
        f"  Tools: {'on' if tools_on else 'off'}\n"
        f"  Sampling: {'on' if sampling_enabled else 'off'}\n"
        "\n"
        "Generation\n"
        f"  Temperature: {temperature}\n"
        f"  Top-p: {top_p}\n"
        f"  Top-k: {top_k}\n"
        f"  Repetition penalty: {repetition_penalty}\n"
        f"  Max new tokens: {max_new_tokens}\n"
        "\n"
        "Paths\n"
        f"  Model path:\n    {snapshot.get('model_dir')}\n"
        f"  GUI config:\n    {gui_config_path}\n"
        f"  System prompt ({system_prompt_format}):\n    {system_prompt_path}\n"
        "\n"
        "State\n"
        f"  Loaded: {'yes' if loaded else 'no'}\n"
        f"  Load error: {load_error}"
    )


def _display_user_content(prompt: str, image_paths: list[Path]) -> str:
    clean_prompt = prompt.strip()
    parts: list[str] = []
    if clean_prompt:
        parts.append(clean_prompt)
    if image_paths:
        marker = f"[attached image {len(image_paths)}]" if len(image_paths) == 1 else f"[attached images: {len(image_paths)}]"
        parts.append(marker)
        for idx, path in enumerate(image_paths, start=1):
            try:
                uri = path.resolve().as_uri()
            except Exception:
                uri = ""
            parts.append(f"![attached image {idx}]({uri})" if uri else f"[image {idx}: {path.name}]")
    return "\n\n".join(parts) if parts else "Image attached."


class InputTextEdit(QTextEdit):
    sendRequested = Signal()
    imagesPasted = Signal(object)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.sendRequested.emit()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:  # type: ignore[override]
        pasted: list[object] = []
        try:
            if source.hasImage():
                image_data = source.imageData()
                if isinstance(image_data, QImage) and not image_data.isNull():
                    pasted.append(image_data)
        except Exception:
            pass

        try:
            if source.hasUrls():
                for url in source.urls():
                    if not url.isLocalFile():
                        continue
                    local_path = url.toLocalFile()
                    if not local_path:
                        continue
                    if Path(local_path).suffix.lower() in IMAGE_SUFFIXES:
                        pasted.append(local_path)
        except Exception:
            pass

        if pasted:
            self.imagesPasted.emit(pasted)
            return
        super().insertFromMimeData(source)


class UiSignals(QObject):
    eventReceived = Signal(object)


class ClipboardBridge(QObject):
    @Slot(str, result=bool)
    def copyText(self, text: str) -> bool:
        payload = str(text or "")
        if not payload:
            return False
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(payload)
        return clipboard.text() == payload


class AthenaDesktopWindow(QMainWindow):
    def __init__(self, *, model_dir: Optional[Path] = None, tools_enabled: bool = False, load_model: bool = True) -> None:
        super().__init__()
        STAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.engine = DesktopEngine(model_dir=model_dir, tools_enabled=tools_enabled, load_model=load_model)
        self.session = self.engine.create_session()
        self.session_logger = DesktopSessionLogger(get_log_root())
        self.signals = UiSignals()
        self.signals.eventReceived.connect(self._on_engine_event)
        self.clipboard_bridge = ClipboardBridge(self)
        self.web_channel: Optional[QWebChannel] = None
        self.pending_images: list[Path] = []
        self.session_temp_images: list[Path] = []
        self.transcript_messages: list[dict[str, str]] = []
        self.turn_in_flight = False
        self.web_ready = False
        self.initial_message = [
            {"role": "system", "content": "Desktop engine ready."},
            {"role": "system", "content": "Athena now runs locally through the native engine, not the browser adapter."},
        ]

        self._build_ui()
        self._load_transcript()
        self._refresh_runtime_panel()
        self._refresh_image_preview()
        self.session_logger.log(
            "session_open",
            runtime_snapshot=self.session.runtime_snapshot(),
            project_root=str(PROJECT_ROOT),
            stage_dir=str(STAGE_DIR),
        )

    def _build_ui(self) -> None:
        self.setWindowTitle("Athena V5 Desktop")
        self.resize(1420, 920)

        root = QWidget(self)
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(18, 18, 18, 18)
        shell.setSpacing(14)

        topbar = QFrame(self)
        topbar.setObjectName("Topbar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 16, 18, 16)
        topbar_layout.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)
        title = QLabel("Athena V5 Desktop", topbar)
        title.setObjectName("Title")
        subtitle = QLabel("Native local engine. Direct streaming. Tool traces stay visible.", topbar)
        subtitle.setObjectName("Subtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        topbar_layout.addLayout(title_col, stretch=1)

        self.runtime_line = QLabel("Initializing runtime snapshot...", topbar)
        self.runtime_line.setObjectName("RuntimeLine")
        self.runtime_line.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        topbar_layout.addWidget(self.runtime_line, stretch=0)
        shell.addWidget(topbar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        main_panel = QFrame(self)
        main_panel.setObjectName("MainPanel")
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        self.web = QWebEngineView(self)
        self.web.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.web.loadFinished.connect(self._on_web_loaded)
        self.web_channel = QWebChannel(self.web.page())
        self.web_channel.registerObject("clipboardBridge", self.clipboard_bridge)
        self.web.page().setWebChannel(self.web_channel)
        self.web.setUrl(QUrl.fromLocalFile(str(TRANSCRIPT_HTML.resolve())))
        main_layout.addWidget(self.web, stretch=1)

        composer = QFrame(self)
        composer.setObjectName("ComposerPanel")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(14, 14, 14, 14)
        composer_layout.setSpacing(10)

        self.entry = InputTextEdit(self)
        self.entry.setPlaceholderText("Send Athena a prompt. Enter sends. Shift+Enter adds a newline.")
        self.entry.setMinimumHeight(120)
        self.entry.sendRequested.connect(self.send_turn)
        self.entry.imagesPasted.connect(self._on_images_pasted)
        composer_layout.addWidget(self.entry)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self.attach_btn = QPushButton("Attach", self)
        self.attach_btn.clicked.connect(self._pick_images)
        self.clear_images_btn = QPushButton("Clear Images", self)
        self.clear_images_btn.clicked.connect(self._clear_pending_images)
        self.tools_btn = QToolButton(self)
        self.tools_btn.setCheckable(True)
        self.tools_btn.toggled.connect(self._on_tools_toggled)
        self.send_btn = QPushButton("Send", self)
        self.send_btn.clicked.connect(self.send_turn)
        self.stop_btn = QPushButton("Stop", self)
        self.stop_btn.clicked.connect(self.stop_turn)
        self.clear_btn = QPushButton("Clear Chat", self)
        self.clear_btn.clicked.connect(self.clear_chat)

        self.image_line = QLabel("No pending images", self)
        self.image_line.setObjectName("ImageLine")

        button_row.addWidget(self.attach_btn)
        button_row.addWidget(self.clear_images_btn)
        button_row.addWidget(self.tools_btn)
        button_row.addWidget(self.image_line, stretch=1)
        button_row.addWidget(self.send_btn)
        button_row.addWidget(self.stop_btn)
        button_row.addWidget(self.clear_btn)
        composer_layout.addLayout(button_row)

        self.image_preview = QLabel("No preview", self)
        self.image_preview.setObjectName("ImagePreview")
        self.image_preview.setFixedHeight(118)
        self.image_preview.setVisible(False)
        composer_layout.addWidget(self.image_preview)

        main_layout.addWidget(composer, stretch=0)
        splitter.addWidget(main_panel)

        side_panel = QFrame(self)
        side_panel.setObjectName("SidePanel")
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(10)

        side_head = QHBoxLayout()
        side_head.setContentsMargins(0, 0, 0, 0)
        side_head.setSpacing(8)
        side_label = QLabel("Runtime", self)
        side_label.setObjectName("PanelTitle")
        self.panel_toggle = QToolButton(self)
        self.panel_toggle.setCheckable(True)
        self.panel_toggle.setChecked(True)
        self.panel_toggle.setText("Hide")
        self.panel_toggle.toggled.connect(self._toggle_side_panel)
        side_head.addWidget(side_label, stretch=1)
        side_head.addWidget(self.panel_toggle, stretch=0)
        side_layout.addLayout(side_head)

        self.runtime_snapshot = QPlainTextEdit(self)
        self.runtime_snapshot.setReadOnly(True)
        self.runtime_snapshot.setObjectName("RuntimeSnapshot")
        side_layout.addWidget(self.runtime_snapshot, stretch=1)

        self.status_line = QLabel("Ready.", self)
        self.status_line.setObjectName("StatusLine")
        side_layout.addWidget(self.status_line, stretch=0)
        splitter.addWidget(side_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([1100, 320])
        shell.addWidget(splitter, stretch=1)
        self.side_panel = side_panel

        root.setStyleSheet(
            """
            QWidget {
                background: #07111f;
                color: #edf4ff;
                font-family: "Bahnschrift SemiLight", "Segoe UI", sans-serif;
            }
            #Topbar {
                border: 1px solid rgba(84, 136, 211, 0.25);
                border-radius: 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(17, 31, 56, 230),
                    stop:1 rgba(9, 18, 34, 235));
            }
            #Title {
                font-size: 28px;
                font-family: "Bahnschrift SemiBold", "Segoe UI", sans-serif;
            }
            #Subtitle {
                color: #9bb2d9;
                font-size: 12px;
            }
            #RuntimeLine {
                color: #c8dcff;
                font-size: 12px;
            }
            #MainPanel, #SidePanel, #ComposerPanel {
                border: 1px solid rgba(79, 122, 197, 0.24);
                border-radius: 18px;
                background: rgba(9, 17, 31, 222);
            }
            QTextEdit, QPlainTextEdit {
                border: 1px solid rgba(89, 140, 220, 0.3);
                border-radius: 12px;
                background: rgba(12, 22, 40, 242);
                color: #edf4ff;
                padding: 10px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 1px solid #69abff;
            }
            QPushButton, QToolButton {
                min-height: 34px;
                padding: 4px 12px;
                border-radius: 10px;
                border: 1px solid #335987;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e3358,
                    stop:1 #13233e);
                color: #f4f8ff;
                font-size: 12px;
                font-family: "Bahnschrift SemiBold", "Segoe UI", sans-serif;
            }
            QPushButton:hover, QToolButton:hover {
                background: #214272;
            }
            QPushButton:disabled {
                color: #8ea2c4;
                border: 1px solid #24344f;
                background: #122034;
            }
            #ImageLine, #StatusLine {
                color: #9bb2d9;
                font-size: 12px;
            }
            #PanelTitle {
                font-family: "Bahnschrift SemiBold", "Segoe UI", sans-serif;
                font-size: 15px;
            }
            #ImagePreview {
                border: 1px solid rgba(102, 156, 232, 0.26);
                border-radius: 12px;
                background: rgba(11, 19, 35, 236);
                padding: 6px;
            }
            """
        )

    def _toggle_side_panel(self, checked: bool) -> None:
        self.side_panel.setVisible(checked)
        self.panel_toggle.setText("Hide" if checked else "Show")

    def _set_busy(self, busy: bool) -> None:
        self.turn_in_flight = busy
        self.send_btn.setEnabled(not busy)
        self.attach_btn.setEnabled(not busy)
        self.clear_images_btn.setEnabled((not busy) and bool(self.pending_images))
        self.tools_btn.setEnabled(not busy)
        self.entry.setEnabled(not busy)

    def _refresh_runtime_panel(self) -> None:
        snapshot = self.session.runtime_snapshot()
        self.runtime_snapshot.setPlainText(_runtime_summary(snapshot))
        model_label = snapshot.get("model_label") or "unloaded"
        tools_state = "on" if snapshot.get("tools_enabled") else "off"
        sampling_state = "on" if snapshot.get("sampling_enabled", True) else "off"
        loaded_state = "yes" if snapshot.get("model_loaded", False) else "no"
        self.runtime_line.setText(f"{model_label}  |  tools={tools_state}  |  sampling={sampling_state}  |  loaded={loaded_state}")
        self._sync_tools_toggle(snapshot)

    def _sync_tools_toggle(self, snapshot: Optional[dict] = None) -> None:
        state = snapshot if snapshot is not None else self.session.runtime_snapshot()
        enabled = bool(state.get("tools_enabled"))
        self.tools_btn.blockSignals(True)
        self.tools_btn.setChecked(enabled)
        self.tools_btn.blockSignals(False)
        self.tools_btn.setText("Tools On" if enabled else "Tools Off")
        self.tools_btn.setToolTip("Enable or disable verified tool use for the next turn.")

    def _on_tools_toggled(self, checked: bool) -> None:
        self.session.set_tools_enabled(bool(checked))
        self._refresh_runtime_panel()
        self.status_line.setText("Tools enabled." if checked else "Tools disabled.")

    def _refresh_image_preview(self) -> None:
        count = len(self.pending_images)
        self.clear_images_btn.setEnabled((not self.turn_in_flight) and count > 0)
        if count == 0:
            self.image_line.setText("No pending images")
            self.image_preview.clear()
            self.image_preview.setText("No preview")
            self.image_preview.setVisible(False)
            return
        names = [path.name for path in self.pending_images[:2]]
        if count > 2:
            names.append(f"+{count - 2} more")
        self.image_line.setText(f"{count} image(s): {', '.join(names)}")
        pix = QPixmap(str(self.pending_images[0]))
        if pix.isNull():
            self.image_preview.setText(self.pending_images[0].name)
        else:
            scaled = pix.scaled(
                260,
                104,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_preview.setPixmap(scaled)
        self.image_preview.setVisible(True)

    def _pick_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select images",
            str(get_default_chat_model_dir()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if not files:
            return
        for item in files:
            path = Path(item).expanduser().resolve()
            if path.is_file():
                self.pending_images.append(path)
        self._refresh_image_preview()

    def _persist_pasted_image(self, item: object) -> Optional[Path]:
        if isinstance(item, str):
            path = Path(item).expanduser().resolve()
            return path if path.is_file() else None
        if isinstance(item, QImage) and not item.isNull():
            target = STAGE_DIR / f"clip_{uuid4().hex}.png"
            if item.save(str(target), "PNG"):
                self.session_temp_images.append(target)
                return target
        return None

    def _on_images_pasted(self, items: object) -> None:
        if not isinstance(items, list):
            return
        added = 0
        for item in items:
            persisted = self._persist_pasted_image(item)
            if persisted is None:
                continue
            self.pending_images.append(persisted)
            added += 1
        if added:
            self.status_line.setText(f"Attached {added} image(s).")
            self._refresh_image_preview()

    def _cleanup_session_images(self) -> None:
        for path in list(self.session_temp_images):
            try:
                if path.exists():
                    path.unlink(missing_ok=True)
            except Exception:
                pass
        self.session_temp_images.clear()

    def _clear_pending_images(self) -> None:
        self.pending_images.clear()
        self._refresh_image_preview()

    def _load_transcript(self) -> None:
        self.transcript_messages = list(self.initial_message)
        if self.web_ready:
            html = render_transcript_html(self.transcript_messages)
            payload = json.dumps(html)
            self.web.page().runJavaScript(
                f"window.AthenaDesktopTranscript && window.AthenaDesktopTranscript.setTranscriptHtml({payload});"
            )

    def _on_web_loaded(self, ok: bool) -> None:
        self.web_ready = bool(ok)
        if ok:
            self._load_transcript()

    def _emit_js(self, expression: str) -> None:
        if self.web_ready:
            self.web.page().runJavaScript(expression)

    def _send_live_user_message(self, prompt: str, image_paths: list[Path]) -> None:
        prompt_text = prompt.strip() or "Image attached."
        image_urls = [path.resolve().as_uri() for path in image_paths if path.exists()]
        self._emit_js(
            "window.AthenaDesktopTranscript && "
            f"window.AthenaDesktopTranscript.appendLiveMessage('user', {json.dumps(prompt_text)}, {json.dumps(image_urls)});"
        )

    def _begin_live_assistant(self) -> None:
        self._emit_js("window.AthenaDesktopTranscript && window.AthenaDesktopTranscript.beginAssistantMessage();")

    def _append_assistant_delta(self, text: str) -> None:
        self._emit_js(
            "window.AthenaDesktopTranscript && "
            f"window.AthenaDesktopTranscript.appendAssistantDelta({json.dumps(text)});"
        )

    def _append_live_system(self, text: str) -> None:
        self._emit_js(
            "window.AthenaDesktopTranscript && "
            f"window.AthenaDesktopTranscript.appendLiveMessage('system', {json.dumps(text)}, []);"
        )

    def send_turn(self) -> None:
        if self.turn_in_flight:
            return
        prompt = self.entry.toPlainText().strip()
        image_paths = list(self.pending_images)
        if not prompt and not image_paths:
            return
        display_content = _display_user_content(prompt, image_paths)
        self._set_busy(True)
        self.status_line.setText("Submitting turn...")
        self._send_live_user_message(prompt, image_paths)
        self.entry.clear()
        self.pending_images.clear()
        self._refresh_image_preview()
        self.session_logger.log(
            "turn_submit",
            prompt=prompt,
            display_content=display_content,
            image_paths=[str(path) for path in image_paths],
            pending_image_count=len(image_paths),
        )
        self.session.submit_turn(
            prompt,
            image_paths=[str(path) for path in image_paths],
            display_user_content=display_content,
            listener=lambda event: self.signals.eventReceived.emit(event),
        )

    def stop_turn(self) -> None:
        if not self.turn_in_flight:
            self.status_line.setText("Nothing to stop.")
            return
        self.session.cancel_turn()
        self.status_line.setText("Stop requested...")

    def clear_chat(self) -> None:
        self.session.reset_conversation()
        self._cleanup_session_images()
        self._clear_pending_images()
        self._set_busy(False)
        self.status_line.setText("Conversation cleared.")
        self.session_logger.log("conversation_cleared", visible_message_count=len(self.transcript_messages))
        self._load_transcript()
        self._refresh_runtime_panel()

    def _on_engine_event(self, event: EngineEvent) -> None:
        if event.type == "status":
            self.status_line.setText(event.text or "Working...")
            self._refresh_runtime_panel()
            return
        if event.type == "assistant_delta":
            self._append_assistant_delta(event.text)
            self.status_line.setText("Streaming response...")
            return
        if event.type in {"tool_request", "tool_result"}:
            self._append_live_system(event.text)
            self.status_line.setText("Running verified tool step...")
            self.session_logger.log(event.type, event=event.to_dict())
            return
        if event.type == "turn_done":
            self.transcript_messages = list(event.visible_messages)
            html = render_transcript_html(self.transcript_messages)
            payload = json.dumps(html)
            self._emit_js(
                "window.AthenaDesktopTranscript && "
                f"window.AthenaDesktopTranscript.setTranscriptHtml({payload});"
            )
            self._set_busy(False)
            self._refresh_runtime_panel()
            metrics = event.metrics or {}
            self.status_line.setText(
                f"Ready. latency={metrics.get('latency_ms', 0)}ms messages={metrics.get('visible_message_count', 0)}"
            )
            self.session_logger.log(
                "turn_done",
                assistant=event.assistant,
                visible_messages=event.visible_messages,
                metrics=metrics,
                model_loaded=event.model_loaded,
            )
            return
        if event.type == "turn_error":
            self._append_live_system(f"Turn error\n\n{event.message}")
            self._set_busy(False)
            self._refresh_runtime_panel()
            self.status_line.setText(f"Turn failed: {event.message}")
            self.session_logger.log("turn_error", message=event.message)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self.session_logger.log("session_close", visible_message_count=len(self.transcript_messages))
            self.session.cancel_turn()
            self._cleanup_session_images()
        finally:
            super().closeEvent(event)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Athena V5 desktop shell")
    parser.add_argument("--tools", action="store_true")
    parser.add_argument("--no-load-model", action="store_true")
    parser.add_argument("--model-dir", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_dir = Path(args.model_dir).expanduser().resolve() if args.model_dir else None
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Athena V5 Desktop")
    window = AthenaDesktopWindow(model_dir=model_dir, tools_enabled=bool(args.tools), load_model=not bool(args.no_load_model))
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
