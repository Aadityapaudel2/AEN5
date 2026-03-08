#!/usr/bin/env python3
from __future__ import annotations

import argparse
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal  # pyright: ignore[reportMissingImports]

import wrap
from athena_tools import (
    build_tool_followup_message,
    build_tool_messages,
    decide_tool_call,
    execute_python_tool,
    format_tool_request_markdown,
    format_tool_result_markdown,
    hidden_generate_response,
    stream_visible_response,
)
from qt_ui import (
    QApplication,
    AthenaQtUI,
    CLEAN_LOG,
    RAW_LOG,
    ROOT,
    append_log,
    append_ui_event,
)


class ToolOverlaySignals(QObject):
    append_message = Signal(str, str)
    begin_assistant_stream = Signal()
    finish_direct = Signal(str, str)


class AthenaToolQtUI(AthenaQtUI):
    def __init__(self, model_dir: Optional[Path] = None) -> None:
        super().__init__(model_dir=model_dir)
        self.tool_signals = ToolOverlaySignals()
        self.tool_signals.append_message.connect(self._append_overlay_message)
        self.tool_signals.begin_assistant_stream.connect(self._begin_overlay_assistant_stream)
        self.tool_signals.finish_direct.connect(self._finish_direct_turn)
        self._assistant_stream_ready = threading.Event()
        self.transcript.append(
            {
                "role": "system",
                "content": (
                    "Tool mode active: python tool available via athena_tools.py.\n"
                    "Stable base runtime is unchanged; this window is an opt-in tool overlay."
                ),
            }
        )
        self.setWindowTitle(f"Athena V5  -  {self.streamer.model_label} [tools]")
        self._render_now()

    def _status_text(self, state: str) -> str:
        base = super()._status_text(state)
        return f"{base}  |  tool_mode=python"

    def _append_overlay_message(self, role: str, content: str) -> None:
        self.transcript.append({"role": role, "content": content})
        self._render_now()

    def _begin_overlay_assistant_stream(self) -> None:
        self.transcript.append({"role": "assistant", "content": ""})
        self._current_assistant_idx = len(self.transcript) - 1
        self._last_assistant_body_html = ""
        self._render_now()
        self._assistant_stream_ready.set()

    def _finish_direct_turn(self, cleaned_user_text: str, assistant_text: str) -> None:
        final_text = wrap.clean_assistant_text(assistant_text or "")
        self.transcript.append({"role": "assistant", "content": final_text})
        if final_text:
            self.history.append((cleaned_user_text, final_text))
        append_log(RAW_LOG, "ASSISTANT", final_text)
        append_log(CLEAN_LOG, "ASSISTANT", final_text)
        append_ui_event(
            "stream_stop",
            mode="qt-web-tools",
            model_dir=str(self.streamer.model_dir),
            details={"reason": "completed", "output_chars": len(final_text), "used_tool": False},
        )
        self._current_assistant_idx = None
        self._stop_requested = False
        self._stream_had_error = False
        self._last_stream_error_message = ""
        self._stream_char_queue.clear()
        self._pending_finish_payload = None
        self.is_streaming = False
        self.btn_send.setEnabled(True)
        self.chk_thinking.setEnabled(True)
        self.chk_show_thoughts.setEnabled(True)
        self.entry.setFocus()
        self._set_avatar_state("idle")
        self._render_now()
        self.set_status("Ready")

    def send(self) -> None:
        if self.is_streaming:
            return
        user_text = self.entry.toPlainText().strip()
        image_paths = list(self._pending_image_paths)
        if not user_text and not image_paths:
            return
        self.entry.clear()
        self._clear_pending_images(remove_files=False)

        display_user = user_text if user_text else "[image input]"
        if image_paths:
            image_md_lines: list[str] = []
            for idx, path in enumerate(image_paths, start=1):
                try:
                    image_uri = path.resolve().as_uri()
                    image_md_lines.append(f"![attached image {idx}]({image_uri})")
                except Exception:
                    image_md_lines.append(f"[image {idx}: {path.name}]")
                try:
                    if path.parent.resolve() == self._image_stage_dir:
                        self._session_temp_image_paths.append(path)
                except Exception:
                    pass
            display_user = f"{display_user}\n\n" + "\n\n".join(image_md_lines)

        log_user = user_text if user_text else "[image input]"
        if image_paths:
            log_user = f"{log_user}\n[attached images: {len(image_paths)}]"

        append_log(RAW_LOG, "USER", log_user)
        self.transcript.append({"role": "user", "content": display_user})
        self._current_assistant_idx = None
        self._stop_requested = False
        self._stream_had_error = False
        self._last_stream_error_message = ""
        self._last_assistant_body_html = ""
        self._stream_char_queue.clear()
        self._pending_finish_payload = None
        self._render_now()

        self.is_streaming = True
        self.btn_send.setEnabled(False)
        self.chk_thinking.setEnabled(False)
        self.chk_show_thoughts.setEnabled(False)
        self._set_avatar_state("thinking" if self.settings.hide_thoughts and self.chk_thinking.isChecked() else "speaking")
        self.set_status("Streaming...")
        append_ui_event(
            "stream_start",
            mode="qt-web-tools",
            model_dir=str(self.streamer.model_dir),
            details={
                "input_chars": len(user_text),
                "images_attached": len(image_paths),
                "thinking_enabled": bool(self.chk_thinking.isChecked()),
                "show_thoughts": bool(self.chk_show_thoughts.isChecked()),
            },
        )

        threading.Thread(target=self._tool_stream_worker, args=(user_text, image_paths), daemon=True).start()

    def _tool_stream_worker(self, user_text: str, image_paths: list[Path]) -> None:
        cleaned_user_text = (user_text or "").strip()
        final_visible_chunks: list[str] = []
        try:
            use_multimodal = bool(image_paths and self.streamer.supports_vision and self.streamer.processor is not None)
            tool_messages = build_tool_messages(
                self.history,
                user_text,
                system_prompt=self.system_prompt,
                user_images=image_paths if use_multimodal else None,
            )
            initial_response = hidden_generate_response(
                self.streamer,
                tool_messages,
                enable_thinking=self.chk_thinking.isChecked(),
            )
            call = decide_tool_call(user_text, initial_response)
            if call is None or call.tool != "python":
                self.tool_signals.finish_direct.emit(cleaned_user_text, initial_response)
                return

            result = execute_python_tool(call.code, cwd=ROOT)
            self.tool_signals.append_message.emit("system", format_tool_request_markdown(call))
            self.tool_signals.append_message.emit("system", format_tool_result_markdown(result))

            self._assistant_stream_ready.clear()
            self.tool_signals.begin_assistant_stream.emit()
            self._assistant_stream_ready.wait(timeout=5.0)
            if not self._assistant_stream_ready.is_set():
                raise RuntimeError("Assistant stream slot did not initialize.")

            followup_messages = list(tool_messages)
            followup_messages.append({"role": "assistant", "content": call.raw})
            followup_messages.append({"role": "user", "content": build_tool_followup_message(result)})

            final_response = stream_visible_response(
                self.streamer,
                followup_messages,
                lambda chunk: self._emit_final_chunk(final_visible_chunks, chunk),
                enable_thinking=self.chk_thinking.isChecked(),
                hide_thoughts=not self.chk_show_thoughts.isChecked(),
            )
            self.signals.finished.emit(cleaned_user_text, final_response)
        except Exception as exc:
            msg = str(exc).strip() or f"{exc.__class__.__name__}: {repr(exc)}"
            if self._current_assistant_idx is None:
                self.tool_signals.finish_direct.emit(cleaned_user_text, f"[stream error] {msg}")
            else:
                self.signals.error.emit(msg)
                self.signals.finished.emit(cleaned_user_text, wrap.clean_assistant_text("".join(final_visible_chunks)))

    def _emit_final_chunk(self, store: list[str], chunk: str) -> None:
        if not chunk:
            return
        store.append(chunk)
        self.signals.chunk.emit(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="", help="Optional model path override for this tool UI instance.")
    args = parser.parse_args()
    model_dir = Path(args.model_dir).expanduser().resolve() if args.model_dir else None

    app = QApplication.instance() or QApplication([])
    ui = AthenaToolQtUI(model_dir=model_dir)
    ui.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
