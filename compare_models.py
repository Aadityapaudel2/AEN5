from __future__ import annotations

import argparse
import csv
import queue
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

BOOTSTRAP_ROOT = Path(__file__).resolve().parent
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from athena_paths import (
    get_base_chat_model_dir,
    get_coherence_ablation_set_path,
    get_coherence_ablation_yaml_path,
    get_compare_runs_dir,
    get_default_chat_model_dir,
)
from desktop_engine.events import EngineEvent

BG = "#08101d"
PANEL = "#0d1830"
ENTRY = "#0a1324"
FG = "#eef3ff"
MUTED = "#90a6d1"
ACCENT_A = "#66c7ff"
ACCENT_B = "#f6ae63"
BAD = "#ff8b8b"

_DESKTOP_ENGINE_CLS = None


def _get_desktop_engine_cls():
    global _DESKTOP_ENGINE_CLS
    if _DESKTOP_ENGINE_CLS is None:
        from desktop_engine import DesktopEngine as _DesktopEngine

        _DESKTOP_ENGINE_CLS = _DesktopEngine
    return _DESKTOP_ENGINE_CLS


@dataclass(frozen=True)
class PromptCase:
    label: str
    prompt: str
    prompt_id: str
    source_path: str


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _char_count(text: str) -> int:
    return len((text or "").strip())


class ComparePane:
    def __init__(self, app: "ModelCompareApp", key: str, accent: str) -> None:
        self.app = app
        self.key = key
        self.accent = accent
        self.side_title = "Model"
        self.selected_model_name = ""
        self.assistant_name = "Athena"
        self.incoming_label = "User prompt"
        self.engine = None
        self.session = None
        self.model_path: Path | None = None
        self.tools_enabled = False
        self.assistant_open = False
        self.turn_active = False
        self.widget: ScrolledText
        self.title_var = tk.StringVar(value="")
        self.identity_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Idle")
        self.info_var = tk.StringVar(value="No model loaded")
        self.metrics_var = tk.StringVar(value="Words: 0 | Chars: 0")
        self.context_var = tk.StringVar(value="Context: warm the model to estimate exact tokens")
        self.last_assistant_text = ""
        self.last_latency_ms: int | None = None
        self.last_word_count = 0
        self.last_char_count = 0
        self.last_input_tokens = 0
        self.last_max_context_tokens = 0
        self.last_remaining_tokens: int | None = None
        self.last_remaining_after_output_cap: int | None = None
        self.last_usage_ratio: float | None = None
        self._refresh_identity_labels()

    def bind_widget(self, widget: ScrolledText) -> None:
        self.widget = widget

    def set_side_title(self, title: str) -> None:
        clean_title = (title or "").strip()
        self.side_title = clean_title or "Model"
        self._refresh_identity_labels()

    def set_selected_model(self, model_path: str) -> None:
        raw = (model_path or "").strip()
        if not raw:
            self.selected_model_name = ""
            self.info_var.set("No model selected")
            self._refresh_identity_labels()
            return
        path = Path(raw)
        self.selected_model_name = path.name or raw
        if self.model_path is not None and str(self.model_path) == raw:
            self.info_var.set(f"Loaded: {self.selected_model_name} | {raw}")
        else:
            self.info_var.set(f"Selected: {self.selected_model_name} | {raw}")
        self._refresh_identity_labels()

    def set_assistant_name(self, name: str) -> None:
        clean_name = (name or "").strip()
        self.assistant_name = clean_name or "Athena"
        self._refresh_identity_labels()

    def set_incoming_label(self, label: str) -> None:
        clean_label = (label or "").strip()
        self.incoming_label = clean_label or "User prompt"
        self._refresh_identity_labels()

    def ensure_session(self, *, model_path: Path, tools_enabled: bool) -> bool:
        resolved = model_path.expanduser().resolve()
        needs_reset = (
            self.engine is None
            or self.session is None
            or self.model_path is None
            or resolved != self.model_path
            or tools_enabled != self.tools_enabled
        )
        if not needs_reset:
            return False
        engine_cls = _get_desktop_engine_cls()
        self.engine = engine_cls(model_dir=resolved, tools_enabled=tools_enabled, load_model=True)
        self.session = self.engine.create_session()
        self.model_path = resolved
        self.selected_model_name = resolved.name
        self.tools_enabled = tools_enabled
        self.assistant_open = False
        self.turn_active = False
        self.last_assistant_text = ""
        self.last_latency_ms = None
        self.last_word_count = 0
        self.last_char_count = 0
        self.clear_transcript()
        self.info_var.set(f"Loaded: {resolved.name} | {resolved}")
        self.metrics_var.set("Words: 0 | Chars: 0")
        self.status_var.set("Ready to warm")
        self._append_line("system", f"Model set to {resolved}")
        return True

    def _refresh_identity_labels(self) -> None:
        incoming = self.incoming_label or "User prompt"
        speaker = self.assistant_name or "Athena"
        model_name = f" [{self.selected_model_name}]" if self.selected_model_name else ""
        if incoming == "User prompt":
            self.title_var.set(f"{self.side_title}{model_name}")
            self.identity_var.set(f"Speaker: {speaker} | Incoming: user prompt")
        else:
            self.title_var.set(f"{self.side_title}{model_name} as {speaker}")
            self.identity_var.set(f"Speaker: {speaker} | Incoming: {incoming}")

    def runtime_loaded(self) -> bool:
        if self.session is None:
            return False
        snapshot = self.session.runtime_snapshot()
        return bool(snapshot.get("model_loaded"))

    def warm(self) -> None:
        if self.engine is None:
            return
        self.app.push_event(self.key, EngineEvent(type="status", text="Loading model..."))
        try:
            self.engine.warm_start()
            snapshot = self.engine.runtime_snapshot()
            device = snapshot.get("device", "unknown")
            label = snapshot.get("model_label", self.model_path.name if self.model_path else "model")
            self.app.push_event(self.key, EngineEvent(type="status", text=f"Loaded {label} on {device}"))
        except Exception as exc:
            self.app.push_event(self.key, EngineEvent(type="turn_error", message=str(exc)))
            raise

    def submit_prompt(
        self,
        prompt: str,
        *,
        display_text: str | None = None,
        display_label: str | None = None,
        system_prompt_override: str | None = None,
    ) -> None:
        if self.session is None:
            raise RuntimeError("Session not ready.")
        visible_text = (display_text if display_text is not None else prompt).strip()
        estimate = self.session.estimate_tokens(
            prompt.strip(),
            tools_enabled=self.tools_enabled,
            system_prompt_override=system_prompt_override,
        )
        self.turn_active = True
        self.assistant_open = False
        self.last_assistant_text = ""
        self.last_latency_ms = None
        self.last_word_count = 0
        self.last_char_count = 0
        self.last_input_tokens = int(estimate.get("input_tokens") or 0)
        self.last_max_context_tokens = int(estimate.get("max_context_tokens") or 0)
        self.last_remaining_tokens = estimate.get("remaining_tokens")
        self.last_remaining_after_output_cap = estimate.get("remaining_after_output_cap")
        usage_ratio = estimate.get("usage_ratio")
        self.last_usage_ratio = float(usage_ratio) if isinstance(usage_ratio, (float, int)) else None
        self.metrics_var.set("Words: 0 | Chars: 0")
        self._append_line("user", visible_text, label=display_label)
        self.session.submit_turn(
            prompt.strip(),
            display_user_content=visible_text,
            listener=lambda event: self.app.push_event(self.key, event),
            system_prompt_override=system_prompt_override,
        )

    def stop(self) -> None:
        if self.session is not None:
            self.session.cancel_turn()
        self.turn_active = False
        self.assistant_open = False
        self.status_var.set("Stopped")

    def reset(self) -> None:
        if self.session is not None:
            self.session.reset_conversation()
        self.turn_active = False
        self.assistant_open = False
        self.last_assistant_text = ""
        self.last_latency_ms = None
        self.last_word_count = 0
        self.last_char_count = 0
        self.clear_transcript()
        self.metrics_var.set("Words: 0 | Chars: 0")
        self.status_var.set("Cleared")

    def clear_transcript(self) -> None:
        self.widget.configure(state=tk.NORMAL)
        self.widget.delete("1.0", tk.END)
        self.widget.configure(state=tk.DISABLED)

    def set_context_text(self, text: str) -> None:
        self.context_var.set(text)

    def update_context_estimate(self, prompt: str, *, tools_enabled: bool = False, prefix: str = "Next turn") -> None:
        self.update_context_estimate_with_system(prompt, tools_enabled=tools_enabled, prefix=prefix)

    def update_context_estimate_with_system(
        self,
        prompt: str,
        *,
        tools_enabled: bool = False,
        prefix: str = "Next turn",
        system_prompt_override: str | None = None,
    ) -> None:
        if self.session is None:
            self.context_var.set("Context: warm both to estimate exact tokens")
            return
        payload = self.session.estimate_tokens(
            prompt,
            tools_enabled=tools_enabled,
            system_prompt_override=system_prompt_override,
        )
        if not payload.get("available"):
            reason = str(payload.get("reason") or "Exact token estimate unavailable.")
            self.context_var.set(f"Context: {reason}")
            return
        input_tokens = int(payload.get("input_tokens") or 0)
        max_context = int(payload.get("max_context_tokens") or 0)
        max_new_tokens = int(payload.get("max_new_tokens") or 0)
        remaining = payload.get("remaining_tokens")
        remaining_after = payload.get("remaining_after_output_cap")
        usage_ratio = payload.get("usage_ratio")
        usage_text = ""
        if isinstance(usage_ratio, (float, int)):
            usage_text = f" | used: {float(usage_ratio) * 100.0:.1f}%"
        if max_context > 0 and isinstance(remaining_after, int):
            self.context_var.set(
                f"{prefix}: {input_tokens:,} tok | window {max_context:,}{usage_text} | remain after {max_new_tokens:,} out: {remaining_after:,}"
            )
            return
        if max_context > 0 and isinstance(remaining, int):
            self.context_var.set(f"{prefix}: {input_tokens:,} tok | window {max_context:,}{usage_text} | remaining: {remaining:,}")
            return
        self.context_var.set(f"{prefix}: {input_tokens:,} tok")

    def on_event(self, event: EngineEvent) -> None:
        if event.type == "status":
            self.status_var.set(event.text or "Working...")
            return
        if event.type == "assistant_delta":
            if not self.assistant_open:
                self._append_header("assistant")
                self.assistant_open = True
            self._append_text(event.text)
            return
        if event.type == "tool_request":
            self._close_assistant_block()
            self._append_line("tool", event.text.strip())
            return
        if event.type == "tool_result":
            self._close_assistant_block()
            self._append_line("tool", event.text.strip())
            return
        if event.type == "turn_done":
            self._close_assistant_block()
            self.turn_active = False
            self.last_assistant_text = (event.assistant or "").strip()
            self.last_word_count = _word_count(self.last_assistant_text)
            self.last_char_count = _char_count(self.last_assistant_text)
            self.metrics_var.set(f"Words: {self.last_word_count} | Chars: {self.last_char_count}")
            latency = event.metrics.get("latency_ms") if isinstance(event.metrics, dict) else None
            self.last_latency_ms = int(latency) if isinstance(latency, int) else None
            if self.last_latency_ms is not None:
                self.status_var.set(f"Done in {self.last_latency_ms} ms")
            else:
                self.status_var.set("Done")
            return
        if event.type == "turn_error":
            self._close_assistant_block()
            self.turn_active = False
            self.status_var.set("Error")
            self._append_line("error", event.message or "Unknown error.")

    def _append_header(self, kind: str, *, label: str | None = None) -> None:
        default_label = {
            "assistant": self.assistant_name,
            "user": self.incoming_label,
            "tool": "Trace",
            "error": "Error",
            "system": "System",
        }.get(kind, kind.title())
        final_label = (label or "").strip() or default_label
        self.widget.configure(state=tk.NORMAL)
        if self.widget.index("end-1c") != "1.0":
            self.widget.insert(tk.END, "\n\n")
        self.widget.insert(tk.END, f"{final_label}\n", (kind, "header"))
        self.widget.configure(state=tk.DISABLED)
        self.widget.see(tk.END)

    def _append_line(self, kind: str, text: str, *, label: str | None = None) -> None:
        self._append_header(kind, label=label)
        self._append_text(f"{text}\n")

    def _append_text(self, text: str) -> None:
        self.widget.configure(state=tk.NORMAL)
        self.widget.insert(tk.END, text, ("body",))
        self.widget.configure(state=tk.DISABLED)
        self.widget.see(tk.END)

    def _close_assistant_block(self) -> None:
        if not self.assistant_open:
            return
        self.widget.configure(state=tk.NORMAL)
        if not self.widget.get("end-2c", "end-1c").endswith("\n"):
            self.widget.insert(tk.END, "\n")
        self.widget.configure(state=tk.DISABLED)
        self.widget.see(tk.END)
        self.assistant_open = False


class ModelCompareApp:
    def __init__(self, *, model_a: Optional[Path] = None, model_b: Optional[Path] = None) -> None:
        self.root = tk.Tk()
        self.root.title("Athena Model Compare")
        self.root.geometry("1700x1020")
        self.root.configure(bg=BG)

        default_a = model_a or get_default_chat_model_dir()
        fallback_b = get_base_chat_model_dir()
        default_b = model_b or (fallback_b if fallback_b.exists() else default_a)

        self.model_a_var = tk.StringVar(value=str(default_a))
        self.model_b_var = tk.StringVar(value=str(default_b))
        self.tools_var = tk.BooleanVar(value=False)
        self.prompt_nav_var = tk.StringVar(value="Manual prompt")
        self.prompt_choice_var = tk.StringVar(value="")
        self.prompt_stats_var = tk.StringVar(value="Prompt words: 0 | chars: 0")
        self.export_var = tk.StringVar(value="CSV log: not created yet")
        self.dialogue_status_var = tk.StringVar(value="Dialogue idle")
        self.left_persona_var = tk.StringVar(value="Athena")
        self.right_persona_var = tk.StringVar(value="Aria")
        self.turn_limit_var = tk.StringVar(value="12")
        self.setup_a_var = tk.StringVar(value="")
        self.setup_b_var = tk.StringVar(value="")
        self.busy = False
        self.prompt_cases: list[PromptCase] = []
        self.prompt_index = -1
        self.event_queue: queue.Queue[tuple[str, EngineEvent]] = queue.Queue()
        self.awaiting_turns: set[str] = set()
        self.pending_prompt_case: PromptCase | None = None
        self.pending_prompt_text = ""
        self.current_csv_path: Path | None = None
        self.current_dialogue_csv_path: Path | None = None
        self.active_run_mode: str | None = None
        self.dialogue_waiting_for: str | None = None
        self.dialogue_turn_index = 0
        self.dialogue_turn_limit: int | None = None
        self.dialogue_prompt_case: PromptCase | None = None
        self.dialogue_last_message = ""
        self.dialogue_last_speaker = "Seed"
        self.dialogue_can_resume = False

        self.panes = {
            "left": ComparePane(self, "left", ACCENT_A),
            "right": ComparePane(self, "right", ACCENT_B),
        }

        self.prompt_box: tk.Text
        self.send_btn: ttk.Button
        self.start_dialogue_btn: ttk.Button
        self.continue_dialogue_btn: ttk.Button
        self.inject_left_btn: ttk.Button
        self.inject_right_btn: ttk.Button
        self.warm_btn: ttk.Button
        self.prev_btn: ttk.Button
        self.next_btn: ttk.Button
        self.prompt_selector: ttk.Combobox

        self._build_styles()
        self._build_ui()
        self._sync_pane_display_state()
        self._autoload_prompt_set()
        self._set_busy(False)
        self._refresh_prompt_stats()
        self.root.after(40, self._poll_events)

    def push_event(self, key: str, event: EngineEvent) -> None:
        self.event_queue.put((key, event))

    def run(self) -> None:
        self.root.mainloop()

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Root.TFrame", background=BG)
        style.configure("Panel.TLabelframe", background=PANEL, foreground=FG, borderwidth=1)
        style.configure("Panel.TLabelframe.Label", background=PANEL, foreground=FG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Panel.TLabel", background=PANEL, foreground=FG)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("AccentA.TLabel", background=PANEL, foreground=ACCENT_A)
        style.configure("AccentB.TLabel", background=PANEL, foreground=ACCENT_B)
        style.configure("Title.TLabel", background=BG, foreground=FG)
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED)
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.configure("TButton", padding=(10, 6))

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="Root.TFrame", padding=16)
        shell.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(shell, text="Athena Model Compare", font=("Segoe UI Semibold", 18), style="Title.TLabel")
        title.pack(anchor="w")
        subtitle = ttk.Label(
            shell,
            text="One prompt at a time, or a live dialogue loop between two checkpoints. System A/B are optional per-model system prompts for this compare session.",
            style="Subtitle.TLabel",
        )
        subtitle.pack(anchor="w", pady=(2, 14))

        controls = ttk.Frame(shell, style="Panel.TFrame", padding=14)
        controls.pack(fill=tk.X)

        self._build_model_row(
            controls,
            row=0,
            label="Model A",
            variable=self.model_a_var,
            browse=lambda: self._pick_model(self.model_a_var),
        )
        self._build_model_row(
            controls,
            row=1,
            label="Model B",
            variable=self.model_b_var,
            browse=lambda: self._pick_model(self.model_b_var),
        )
        self._build_instruction_row(controls, row=2, label="System A", variable=self.setup_a_var)
        self._build_instruction_row(controls, row=3, label="System B", variable=self.setup_b_var)

        ttk.Checkbutton(controls, text="Tools On", variable=self.tools_var).grid(row=0, column=3, padx=(12, 0), pady=4, sticky="w")
        self.warm_btn = ttk.Button(controls, text="Warm Both", command=self.warm_models)
        self.warm_btn.grid(row=0, column=4, padx=(12, 0), pady=4, sticky="ew")
        ttk.Button(controls, text="Stop Both", command=self.stop_all).grid(row=1, column=4, padx=(12, 0), pady=4, sticky="ew")
        ttk.Button(controls, text="Clear Chats", command=self.reset_all).grid(row=1, column=3, padx=(12, 0), pady=4, sticky="ew")
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(4, minsize=110)

        content = ttk.Frame(shell, style="Root.TFrame")
        content.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        self._build_pane(content, column=0, title="Model A Output", pane=self.panes["left"], title_style="AccentA.TLabel")
        self._build_pane(content, column=1, title="Model B Output", pane=self.panes["right"], title_style="AccentB.TLabel")

        composer = ttk.Frame(shell, style="Panel.TFrame", padding=14)
        composer.pack(fill=tk.X, pady=(14, 0))
        composer.columnconfigure(0, weight=1)

        dialogue_row = ttk.Frame(composer, style="Panel.TFrame")
        dialogue_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(dialogue_row, text="Dialogue Loop", style="Panel.TLabel").pack(side=tk.LEFT)
        ttk.Label(dialogue_row, text="Left", style="Muted.TLabel").pack(side=tk.LEFT, padx=(12, 4))
        left_persona = tk.Entry(
            dialogue_row,
            textvariable=self.left_persona_var,
            bg=ENTRY,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            font=("Segoe UI", 10),
            width=12,
        )
        left_persona.pack(side=tk.LEFT)
        left_persona.bind("<KeyRelease>", lambda event: self._on_persona_changed())
        ttk.Label(dialogue_row, text="Right", style="Muted.TLabel").pack(side=tk.LEFT, padx=(10, 4))
        right_persona = tk.Entry(
            dialogue_row,
            textvariable=self.right_persona_var,
            bg=ENTRY,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            font=("Segoe UI", 10),
            width=12,
        )
        right_persona.pack(side=tk.LEFT)
        right_persona.bind("<KeyRelease>", lambda event: self._on_persona_changed())
        ttk.Label(dialogue_row, text="Turns (0=until stop)", style="Muted.TLabel").pack(side=tk.LEFT, padx=(10, 4))
        turns_entry = tk.Entry(
            dialogue_row,
            textvariable=self.turn_limit_var,
            bg=ENTRY,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            font=("Segoe UI", 10),
            width=8,
        )
        turns_entry.pack(side=tk.LEFT)
        turns_entry.bind("<KeyRelease>", lambda event: self._refresh_context_estimates())
        ttk.Label(dialogue_row, textvariable=self.dialogue_status_var, style="Muted.TLabel").pack(side=tk.LEFT, padx=(12, 0))
        self.inject_right_btn = ttk.Button(dialogue_row, text="Inject -> Right", command=lambda: self.inject_dialogue("right"))
        self.inject_right_btn.pack(side=tk.RIGHT)
        self.inject_left_btn = ttk.Button(dialogue_row, text="Inject -> Left", command=lambda: self.inject_dialogue("left"))
        self.inject_left_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.continue_dialogue_btn = ttk.Button(dialogue_row, text="Continue", command=self.continue_dialogue)
        self.continue_dialogue_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.start_dialogue_btn = ttk.Button(dialogue_row, text="Start Dialogue", command=self.start_dialogue)
        self.start_dialogue_btn.pack(side=tk.RIGHT, padx=(0, 8))

        nav_row = ttk.Frame(composer, style="Panel.TFrame")
        nav_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(nav_row, text="Load Prompt YAML", command=self.load_prompt_yaml).pack(side=tk.LEFT)
        ttk.Button(nav_row, text="Load Coherence Set", command=self.load_coherence_set).pack(side=tk.LEFT, padx=(8, 0))
        self.prev_btn = ttk.Button(nav_row, text="Prev", command=lambda: self.step_prompt(-1))
        self.prev_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.next_btn = ttk.Button(nav_row, text="Next", command=lambda: self.step_prompt(1))
        self.next_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.prompt_selector = ttk.Combobox(
            nav_row,
            textvariable=self.prompt_choice_var,
            state="readonly",
            width=36,
        )
        self.prompt_selector.pack(side=tk.LEFT, padx=(12, 0))
        self.prompt_selector.bind("<<ComboboxSelected>>", self._on_prompt_selected)
        ttk.Label(nav_row, textvariable=self.prompt_nav_var, style="Muted.TLabel").pack(side=tk.LEFT, padx=(12, 0))
        self.send_btn = ttk.Button(nav_row, text="Send To Both", command=self.send_prompt)
        self.send_btn.pack(side=tk.RIGHT)

        self.prompt_box = tk.Text(
            composer,
            height=6,
            wrap=tk.WORD,
            bg=ENTRY,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            padx=12,
            pady=12,
            font=("Segoe UI", 11),
        )
        self.prompt_box.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.prompt_box.bind("<Control-Return>", self._on_send_key)
        self.prompt_box.bind("<Return>", self._on_send_key)
        self.prompt_box.bind("<Shift-Return>", self._on_shift_return)
        self.prompt_box.bind("<KeyRelease>", self._on_prompt_edited)

        footer = ttk.Frame(composer, style="Panel.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(footer, textvariable=self.prompt_stats_var, style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Label(footer, textvariable=self.export_var, style="Muted.TLabel").pack(side=tk.RIGHT)

    def _build_model_row(self, parent: ttk.Frame, *, row: int, label: str, variable: tk.StringVar, browse) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=ENTRY,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
        entry.bind("<KeyRelease>", lambda event: self._on_model_changed())
        ttk.Button(parent, text="Browse", command=browse).grid(row=row, column=2, sticky="ew", pady=4)

    def _build_instruction_row(self, parent: ttk.Frame, *, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=ENTRY,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            font=("Segoe UI", 10),
        )
        entry.grid(row=row, column=1, columnspan=4, sticky="ew", padx=(10, 0), pady=4)
        entry.bind("<KeyRelease>", lambda event: self._refresh_context_estimates())

    def _on_model_changed(self) -> None:
        self._sync_pane_display_state()
        self._refresh_context_estimates()

    def _on_persona_changed(self) -> None:
        self._sync_pane_display_state()
        self._refresh_context_estimates()

    def _sync_pane_display_state(self) -> None:
        left_name, right_name = self._dialogue_personas()
        left_incoming = right_name if self.active_run_mode == "dialogue" or self.dialogue_can_resume else "User prompt"
        right_incoming = left_name if self.active_run_mode == "dialogue" or self.dialogue_can_resume else "User prompt"
        self.panes["left"].set_assistant_name(left_name)
        self.panes["left"].set_incoming_label(left_incoming)
        self.panes["right"].set_assistant_name(right_name)
        self.panes["right"].set_incoming_label(right_incoming)
        self.panes["left"].set_selected_model(self.model_a_var.get())
        self.panes["right"].set_selected_model(self.model_b_var.get())
        self.inject_left_btn.configure(text=f"Inject -> {left_name}")
        self.inject_right_btn.configure(text=f"Inject -> {right_name}")

    def _build_pane(self, parent: ttk.Frame, *, column: int, title: str, pane: ComparePane, title_style: str) -> None:
        pane.set_side_title(title)
        frame = ttk.LabelFrame(parent, text="", style="Panel.TLabelframe", padding=12)
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 8 if column == 0 else 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)

        ttk.Label(frame, textvariable=pane.title_var, style=title_style, font=("Segoe UI Semibold", 13)).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, textvariable=pane.status_var, style="Panel.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(frame, textvariable=pane.identity_var, style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        ttk.Label(frame, textvariable=pane.info_var, style="Muted.TLabel").grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 2))
        ttk.Label(frame, textvariable=pane.metrics_var, style="Muted.TLabel").grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(frame, textvariable=pane.context_var, style="Muted.TLabel").grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        transcript = ScrolledText(
            frame,
            wrap=tk.WORD,
            bg=ENTRY,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            padx=12,
            pady=12,
            font=("Segoe UI", 10),
        )
        transcript.grid(row=5, column=0, columnspan=2, sticky="nsew")
        transcript.configure(state=tk.DISABLED)
        transcript.tag_configure("header", font=("Segoe UI Semibold", 10))
        transcript.tag_configure("user", foreground=ACCENT_A)
        transcript.tag_configure("assistant", foreground=pane.accent)
        transcript.tag_configure("tool", foreground="#d4e07e")
        transcript.tag_configure("error", foreground=BAD)
        transcript.tag_configure("system", foreground=MUTED)
        pane.bind_widget(transcript)

    def _pick_model(self, variable: tk.StringVar) -> None:
        initial = Path(variable.get()).expanduser()
        selection = filedialog.askdirectory(
            title="Select model directory",
            initialdir=str(initial.parent if initial.exists() else BOOTSTRAP_ROOT),
        )
        if selection:
            variable.set(selection)
            self._on_model_changed()

    def _poll_events(self) -> None:
        while True:
            try:
                key, event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            pane = self.panes.get(key)
            if pane is not None:
                pane.on_event(event)
            if event.type in {"turn_done", "turn_error"}:
                if self.active_run_mode == "compare" and key in self.awaiting_turns:
                    self.awaiting_turns.discard(key)
                    if not self.awaiting_turns:
                        self._finalize_compare_run()
                elif self.active_run_mode == "dialogue" and key == self.dialogue_waiting_for:
                    if event.type == "turn_done":
                        self._handle_dialogue_turn_done(key)
                    else:
                        self._handle_dialogue_turn_error(key, event.message or "Unknown error.")
        self.root.after(40, self._poll_events)

    def _current_prompt(self) -> str:
        return self.prompt_box.get("1.0", tk.END).strip()

    def _on_send_key(self, event) -> str:
        self.send_prompt()
        return "break"

    def _on_shift_return(self, event) -> Optional[str]:
        return None

    def _on_prompt_edited(self, event=None) -> None:
        self._refresh_prompt_stats()

    def _refresh_prompt_stats(self) -> None:
        prompt = self._current_prompt()
        self.prompt_stats_var.set(f"Prompt words: {_word_count(prompt)} | chars: {_char_count(prompt)}")
        self._refresh_context_estimates()

    def _resolve_model_inputs(self) -> tuple[Path, Path]:
        left = Path(self.model_a_var.get().strip()).expanduser()
        right = Path(self.model_b_var.get().strip()).expanduser()
        if not left.is_dir():
            raise FileNotFoundError(f"Model A directory not found: {left}")
        if not right.is_dir():
            raise FileNotFoundError(f"Model B directory not found: {right}")
        return left.resolve(), right.resolve()

    def _prepare_panes(self) -> tuple[Path, Path]:
        left_path, right_path = self._resolve_model_inputs()
        tools_enabled = bool(self.tools_var.get())
        self.panes["left"].ensure_session(model_path=left_path, tools_enabled=tools_enabled)
        self.panes["right"].ensure_session(model_path=right_path, tools_enabled=tools_enabled)
        return left_path, right_path

    def _model_setup_text(self, key: str) -> str:
        if key == "left":
            return self.setup_a_var.get().strip()
        return self.setup_b_var.get().strip()

    def warm_models(self) -> None:
        if self.busy:
            return
        try:
            self._prepare_panes()
        except Exception as exc:
            messagebox.showerror("Athena Model Compare", str(exc))
            return
        self._set_busy(True)
        threading.Thread(target=self._warm_worker, daemon=True).start()

    def _warm_worker(self) -> None:
        try:
            for key in ("left", "right"):
                pane = self.panes[key]
                if not pane.runtime_loaded():
                    pane.warm()
        finally:
            self.root.after(0, self._finish_warm)

    def _finish_warm(self) -> None:
        self._set_busy(False)
        self._refresh_context_estimates()

    def send_prompt(self) -> None:
        prompt = self._current_prompt()
        if not prompt:
            messagebox.showinfo("Athena Model Compare", "Enter a prompt first.")
            return
        if self.busy or any(pane.turn_active for pane in self.panes.values()):
            messagebox.showinfo("Athena Model Compare", "A compare run is already in progress.")
            return
        try:
            self._prepare_panes()
        except Exception as exc:
            messagebox.showerror("Athena Model Compare", str(exc))
            return
        self.dialogue_can_resume = False
        self._sync_pane_display_state()
        self.active_run_mode = "compare"
        self.dialogue_waiting_for = None
        self.awaiting_turns = {"left", "right"}
        self.pending_prompt_case = self._selected_prompt_case(prompt)
        self.pending_prompt_text = prompt
        self._set_busy(True)
        threading.Thread(target=self._dispatch_prompt, args=(prompt,), daemon=True).start()

    def _dispatch_prompt(self, prompt: str) -> None:
        try:
            for key in ("left", "right"):
                pane = self.panes[key]
                if not pane.runtime_loaded():
                    pane.warm()
            self.root.after(0, lambda: self._submit_compare_prompt(prompt))
        except Exception as exc:
            self.push_event("left", EngineEvent(type="turn_error", message=str(exc)))
            self.push_event("right", EngineEvent(type="turn_error", message=str(exc)))

    def _submit_compare_prompt(self, prompt: str) -> None:
        try:
            self.panes["left"].submit_prompt(
                self._build_compare_prompt("left", prompt),
                display_text=prompt,
                system_prompt_override=self._model_setup_text("left"),
            )
            self.panes["right"].submit_prompt(
                self._build_compare_prompt("right", prompt),
                display_text=prompt,
                system_prompt_override=self._model_setup_text("right"),
            )
        except Exception as exc:
            self.push_event("left", EngineEvent(type="turn_error", message=str(exc)))
            self.push_event("right", EngineEvent(type="turn_error", message=str(exc)))

    def _build_compare_prompt(self, key: str, prompt: str) -> str:
        return prompt.strip()

    def start_dialogue(self) -> None:
        seed_prompt = self._current_prompt()
        if not seed_prompt:
            messagebox.showinfo("Athena Model Compare", "Enter a seed prompt first.")
            return
        if self.busy or any(pane.turn_active for pane in self.panes.values()):
            messagebox.showinfo("Athena Model Compare", "A run is already in progress.")
            return
        try:
            turn_limit = self._parse_turn_limit()
            self._prepare_panes()
        except Exception as exc:
            messagebox.showerror("Athena Model Compare", str(exc))
            return

        left_name, right_name = self._dialogue_personas()
        self.active_run_mode = "dialogue"
        self.awaiting_turns = set()
        self.dialogue_waiting_for = "left"
        self.dialogue_turn_index = 0
        self.dialogue_turn_limit = None if turn_limit == 0 else turn_limit
        self.dialogue_prompt_case = self._selected_prompt_case(seed_prompt)
        self.pending_prompt_text = seed_prompt.strip()
        self.dialogue_last_message = seed_prompt.strip()
        self.dialogue_last_speaker = "Controller"
        self.dialogue_can_resume = True
        self._sync_pane_display_state()
        for key, name in (("left", left_name), ("right", right_name)):
            pane = self.panes[key]
            pane.reset()
            pane.status_var.set(f"{name} ready")
        self.dialogue_status_var.set(f"Loop active: {left_name} starts")
        self._set_busy(True)
        threading.Thread(target=self._warm_and_queue_dialogue_start, daemon=True).start()

    def inject_dialogue(self, target_key: str) -> None:
        prompt = self._current_prompt()
        if not prompt:
            messagebox.showinfo("Athena Model Compare", "Enter an injection prompt first.")
            return
        if self.busy or any(pane.turn_active for pane in self.panes.values()):
            messagebox.showinfo("Athena Model Compare", "A run is already in progress.")
            return
        if not self.dialogue_can_resume:
            messagebox.showinfo("Athena Model Compare", "Start a dialogue first, then inject prompts into a node.")
            return
        try:
            self._prepare_panes()
        except Exception as exc:
            messagebox.showerror("Athena Model Compare", str(exc))
            return
        self._sync_pane_display_state()
        self.active_run_mode = "dialogue"
        self.awaiting_turns = set()
        self.dialogue_waiting_for = target_key
        self.dialogue_last_message = prompt.strip()
        self.dialogue_last_speaker = "Controller"
        self.dialogue_status_var.set(f"Injected prompt to {self.panes[target_key].assistant_name}")
        self._set_busy(True)
        threading.Thread(target=self._warm_and_queue_dialogue_continue, args=(target_key, prompt.strip()), daemon=True).start()

    def continue_dialogue(self) -> None:
        if self.busy or any(pane.turn_active for pane in self.panes.values()):
            messagebox.showinfo("Athena Model Compare", "A run is already in progress.")
            return
        if not self.dialogue_can_resume:
            messagebox.showinfo("Athena Model Compare", "Start a dialogue first, then continue it.")
            return
        if not self.dialogue_last_message.strip():
            messagebox.showinfo("Athena Model Compare", "There is no prior dialogue turn to continue from.")
            return
        try:
            self._prepare_panes()
            turn_limit = self._parse_turn_limit()
        except Exception as exc:
            messagebox.showerror("Athena Model Compare", str(exc))
            return

        self.active_run_mode = "dialogue"
        self.awaiting_turns = set()
        self.dialogue_waiting_for = self._resolve_continue_target()
        if turn_limit == 0:
            self.dialogue_turn_limit = None
        else:
            self.dialogue_turn_limit = self.dialogue_turn_index + turn_limit
        self._sync_pane_display_state()
        target_name = self.panes[self.dialogue_waiting_for].assistant_name
        self.dialogue_status_var.set(f"Continuing with {target_name}")
        self._set_busy(True)
        threading.Thread(target=self._warm_and_queue_dialogue_continue_from_history, daemon=True).start()

    def _warm_and_queue_dialogue_start(self) -> None:
        try:
            for key in ("left", "right"):
                pane = self.panes[key]
                if not pane.runtime_loaded():
                    pane.warm()
            self.root.after(0, lambda: self._submit_dialogue_turn("left", self.dialogue_last_message, "Controller"))
        except Exception as exc:
            self.push_event("left", EngineEvent(type="turn_error", message=str(exc)))

    def _warm_and_queue_dialogue_continue(self, target_key: str, prompt: str) -> None:
        try:
            pane = self.panes[target_key]
            if not pane.runtime_loaded():
                pane.warm()
            self.root.after(0, lambda: self._submit_dialogue_turn(target_key, prompt, "Controller"))
        except Exception as exc:
            self.push_event(target_key, EngineEvent(type="turn_error", message=str(exc)))

    def _warm_and_queue_dialogue_continue_from_history(self) -> None:
        target_key = self.dialogue_waiting_for
        if target_key is None:
            self.root.after(0, self._finish_dialogue)
            return
        try:
            pane = self.panes[target_key]
            if not pane.runtime_loaded():
                pane.warm()
            incoming_text = self.dialogue_last_message
            incoming_name = self.dialogue_last_speaker or "Controller"
            self.root.after(0, lambda: self._submit_dialogue_turn(target_key, incoming_text, incoming_name))
        except Exception as exc:
            self.push_event(target_key, EngineEvent(type="turn_error", message=str(exc)))

    def _submit_dialogue_turn(self, key: str, incoming_text: str, incoming_name: str) -> None:
        if self.active_run_mode != "dialogue":
            return
        pane = self.panes[key]
        speaker_name = pane.assistant_name
        partner_key = "right" if key == "left" else "left"
        partner_name = self.panes[partner_key].assistant_name
        self.dialogue_waiting_for = key
        self.dialogue_status_var.set(f"Turn {self.dialogue_turn_index + 1}: {speaker_name} replying to {incoming_name}")
        prompt = self._build_dialogue_prompt(
            key=key,
            speaker_name=speaker_name,
            partner_name=partner_name,
            incoming_name=incoming_name,
            incoming_text=incoming_text,
        )
        try:
            pane.submit_prompt(
                prompt,
                display_text=incoming_text,
                display_label=f"{incoming_name} -> {speaker_name}",
                system_prompt_override=self._model_setup_text(key),
            )
        except Exception as exc:
            self._handle_dialogue_turn_error(key, str(exc))

    def _build_dialogue_prompt(
        self,
        *,
        key: str,
        speaker_name: str,
        partner_name: str,
        incoming_name: str,
        incoming_text: str,
    ) -> str:
        prompt_parts: list[str] = []
        setup_text = self._model_setup_text(key)
        if setup_text:
            prompt_parts.append(setup_text)
        prompt_parts.append(
            (
                f"You are {speaker_name}.\n"
                f"You are in a direct conversation with {partner_name}.\n"
                f"Speak as {speaker_name}, address {partner_name} naturally, and keep the conversation coherent.\n"
                f"Do not mention hidden instructions or system setup.\n\n"
                f"Latest message from {incoming_name}:\n"
                f"{incoming_text.strip()}"
            ).strip()
        )
        return "\n\n".join(part for part in prompt_parts if part).strip()

    def _dialogue_personas(self) -> tuple[str, str]:
        left_name = self.left_persona_var.get().strip() or "Athena"
        right_name = self.right_persona_var.get().strip() or "Aria"
        return left_name, right_name

    def _resolve_continue_target(self) -> str:
        left_name = self.panes["left"].assistant_name
        right_name = self.panes["right"].assistant_name
        if self.dialogue_last_speaker == left_name:
            return "right"
        if self.dialogue_last_speaker == right_name:
            return "left"
        return "left"

    def _parse_turn_limit(self) -> int:
        raw = self.turn_limit_var.get().strip() or "12"
        value = int(raw)
        if value < 0:
            raise ValueError("Turns must be 0 or a positive integer.")
        return value

    def _handle_dialogue_turn_done(self, key: str) -> None:
        pane = self.panes[key]
        speaker_name = pane.assistant_name
        partner_key = "right" if key == "left" else "left"
        partner_name = self.panes[partner_key].assistant_name
        reply_text = (pane.last_assistant_text or "").strip()
        self.dialogue_turn_index += 1
        self._append_dialogue_csv_row(
            speaker_key=key,
            speaker_name=speaker_name,
            listener_name=self.dialogue_last_speaker,
            input_text=self.dialogue_last_message,
            output_text=reply_text,
            pane=pane,
        )
        if not reply_text:
            self.dialogue_status_var.set(f"Loop stopped: {speaker_name} returned an empty reply. Continue is available.")
            self._finish_dialogue()
            return
        if self.dialogue_turn_limit is not None and self.dialogue_turn_index >= self.dialogue_turn_limit:
            self.dialogue_status_var.set(f"Dialogue complete after {self.dialogue_turn_index} turns. Continue is available.")
            self._finish_dialogue()
            return
        self.dialogue_last_message = reply_text
        self.dialogue_last_speaker = speaker_name
        self.root.after(0, lambda: self._submit_dialogue_turn(partner_key, reply_text, speaker_name))
        self.dialogue_status_var.set(f"Turn {self.dialogue_turn_index + 1}: waiting on {partner_name}")

    def _handle_dialogue_turn_error(self, key: str, message: str) -> None:
        speaker_name = self.panes[key].assistant_name
        self.dialogue_status_var.set(f"Loop error on {speaker_name}. Continue is available.")
        self._finish_dialogue()

    def _finish_dialogue(self) -> None:
        self.active_run_mode = None
        self.dialogue_waiting_for = None
        self.awaiting_turns = set()
        self._set_busy(False)
        self._refresh_context_estimates()

    def _selected_prompt_case(self, prompt: str) -> PromptCase:
        if 0 <= self.prompt_index < len(self.prompt_cases):
            case = self.prompt_cases[self.prompt_index]
            if case.prompt.strip() == prompt.strip():
                return case
        return PromptCase(label="Manual prompt", prompt=prompt.strip(), prompt_id="manual", source_path="")

    def _finalize_compare_run(self) -> None:
        self._append_csv_row()
        self.active_run_mode = None
        self._set_busy(False)
        self.awaiting_turns = set()
        self._refresh_context_estimates()

    def stop_all(self) -> None:
        for pane in self.panes.values():
            pane.stop()
        self.awaiting_turns = set()
        self.active_run_mode = None
        self.dialogue_waiting_for = None
        self.dialogue_status_var.set("Dialogue stopped")
        self._set_busy(False)
        self._sync_pane_display_state()
        self._refresh_context_estimates()

    def reset_all(self) -> None:
        for pane in self.panes.values():
            pane.reset()
        self.dialogue_can_resume = False
        self.dialogue_status_var.set("Dialogue idle")
        self._sync_pane_display_state()
        self._refresh_context_estimates()

    def load_prompt_yaml(self) -> None:
        initial = get_coherence_ablation_yaml_path()
        selected = filedialog.askopenfilename(
            title="Select YAML prompt set",
            initialdir=str(initial.parent),
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not selected:
            return
        self._load_prompt_cases(Path(selected))

    def load_coherence_set(self) -> None:
        yaml_path = get_coherence_ablation_yaml_path()
        if yaml_path.exists():
            self._load_prompt_cases(yaml_path)
            return
        self._load_prompt_cases(get_coherence_ablation_set_path())

    def _load_prompt_cases(self, path: Path) -> None:
        try:
            self.prompt_cases = _load_prompt_cases(path)
        except Exception as exc:
            messagebox.showerror("Athena Model Compare", f"Could not load {path.name}: {exc}")
            return
        if not self.prompt_cases:
            messagebox.showinfo("Athena Model Compare", "No prompts found in the selected file.")
            return
        self.prompt_index = 0
        self._refresh_prompt_selector()
        self._show_prompt_case()
        self._set_busy(self.busy)

    def step_prompt(self, delta: int) -> None:
        if not self.prompt_cases:
            return
        self.prompt_index = max(0, min(len(self.prompt_cases) - 1, self.prompt_index + delta))
        self._show_prompt_case()

    def _show_prompt_case(self) -> None:
        if not self.prompt_cases:
            self.prompt_nav_var.set("Manual prompt")
            self.prompt_choice_var.set("")
            return
        case = self.prompt_cases[self.prompt_index]
        self.prompt_box.delete("1.0", tk.END)
        self.prompt_box.insert("1.0", case.prompt)
        source = Path(case.source_path).name if case.source_path else "prompt set"
        self.prompt_choice_var.set(case.label)
        self.prompt_nav_var.set(f"{source} - {case.label} ({self.prompt_index + 1}/{len(self.prompt_cases)})")
        self._refresh_prompt_stats()

    def _refresh_prompt_selector(self) -> None:
        values = [case.label for case in self.prompt_cases]
        self.prompt_selector.configure(values=values)
        if not values:
            self.prompt_choice_var.set("")

    def _on_prompt_selected(self, event=None) -> None:
        label = self.prompt_choice_var.get().strip()
        if not label:
            return
        for index, case in enumerate(self.prompt_cases):
            if case.label == label:
                self.prompt_index = index
                self._show_prompt_case()
                return

    def _set_busy(self, active: bool) -> None:
        self.busy = active
        state = tk.DISABLED if active else tk.NORMAL
        self.send_btn.configure(state=state)
        self.start_dialogue_btn.configure(state=state)
        self.continue_dialogue_btn.configure(state=state)
        self.inject_left_btn.configure(state=state)
        self.inject_right_btn.configure(state=state)
        self.warm_btn.configure(state=state)
        self.prev_btn.configure(state=state if self.prompt_cases else tk.DISABLED)
        self.next_btn.configure(state=state if self.prompt_cases else tk.DISABLED)
        self.prompt_selector.configure(state="disabled" if active or not self.prompt_cases else "readonly")

    def _autoload_prompt_set(self) -> None:
        yaml_path = get_coherence_ablation_yaml_path()
        if yaml_path.exists():
            try:
                self.prompt_cases = _load_prompt_cases(yaml_path)
            except Exception:
                self.prompt_cases = []
            if self.prompt_cases:
                self.prompt_index = 0
                self._refresh_prompt_selector()
                self._show_prompt_case()

    def _dialogue_mode_visible(self) -> bool:
        return self.active_run_mode == "dialogue" or self.dialogue_can_resume

    def _refresh_context_estimates(self) -> None:
        if self.busy or any(pane.turn_active for pane in self.panes.values()):
            for pane in self.panes.values():
                pane.set_context_text("Context: exact estimate pauses while generating")
            return
        draft = self._current_prompt()
        if self._dialogue_mode_visible():
            self._refresh_dialogue_context_estimates(draft)
            return
        self._refresh_compare_context_estimates(draft)

    def _refresh_compare_context_estimates(self, draft: str) -> None:
        tools_enabled = bool(self.tools_var.get())
        if not draft.strip():
            for pane in self.panes.values():
                pane.set_context_text("Context: type a prompt to estimate the next turn")
            return
        for key, pane in self.panes.items():
            pane.update_context_estimate_with_system(
                self._build_compare_prompt(key, draft),
                tools_enabled=tools_enabled,
                prefix="Next turn",
                system_prompt_override=self._model_setup_text(key),
            )

    def _refresh_dialogue_context_estimates(self, draft: str) -> None:
        tools_enabled = bool(self.tools_var.get())
        if not draft.strip():
            for pane in self.panes.values():
                pane.set_context_text("Context: type a prompt, then inject it to a node")
            return
        for key, pane in self.panes.items():
            partner_key = "right" if key == "left" else "left"
            pane.update_context_estimate_with_system(
                self._build_dialogue_prompt(
                    key=key,
                    speaker_name=pane.assistant_name,
                    partner_name=self.panes[partner_key].assistant_name,
                    incoming_name="Controller",
                    incoming_text=draft,
                ),
                tools_enabled=tools_enabled,
                prefix=f"Inject to {pane.assistant_name}",
                system_prompt_override=self._model_setup_text(key),
            )

    def _ensure_csv_log_path(self) -> Path:
        if self.current_csv_path is not None:
            return self.current_csv_path
        compare_dir = get_compare_runs_dir()
        compare_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_csv_path = compare_dir / f"compare_{stamp}.csv"
        with self.current_csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "timestamp",
                    "prompt_id",
                    "prompt_label",
                    "prompt_text",
                    "prompt_source",
                    "tools_enabled",
                    "model_a_path",
                    "model_a_system_prompt",
                    "model_a_input_tokens",
                    "model_a_max_context_tokens",
                    "model_a_remaining_after_output_cap",
                    "model_a_usage_pct",
                    "model_a_answer",
                    "model_a_words",
                    "model_a_chars",
                    "model_a_latency_ms",
                    "model_b_path",
                    "model_b_system_prompt",
                    "model_b_input_tokens",
                    "model_b_max_context_tokens",
                    "model_b_remaining_after_output_cap",
                    "model_b_usage_pct",
                    "model_b_answer",
                    "model_b_words",
                    "model_b_chars",
                    "model_b_latency_ms",
                ]
            )
        self.export_var.set(f"CSV log: {self.current_csv_path}")
        return self.current_csv_path

    def _ensure_dialogue_csv_log_path(self) -> Path:
        if self.current_dialogue_csv_path is not None:
            return self.current_dialogue_csv_path
        compare_dir = get_compare_runs_dir()
        compare_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_dialogue_csv_path = compare_dir / f"dialogue_{stamp}.csv"
        with self.current_dialogue_csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "timestamp",
                    "prompt_id",
                    "prompt_label",
                    "prompt_source",
                    "tools_enabled",
                    "turn_index",
                    "speaker_key",
                    "speaker_name",
                    "listener_name",
                    "model_path",
                    "system_prompt_override",
                    "input_text",
                    "input_tokens",
                    "max_context_tokens",
                    "remaining_after_output_cap",
                    "usage_pct",
                    "output_text",
                    "output_words",
                    "output_chars",
                    "latency_ms",
                ]
            )
        self.export_var.set(f"CSV log: {self.current_dialogue_csv_path}")
        return self.current_dialogue_csv_path

    def _append_csv_row(self) -> None:
        prompt_case = self.pending_prompt_case or PromptCase(
            label="Manual prompt",
            prompt=self.pending_prompt_text,
            prompt_id="manual",
            source_path="",
        )
        csv_path = self._ensure_csv_log_path()
        left = self.panes["left"]
        right = self.panes["right"]
        with csv_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    prompt_case.prompt_id,
                    prompt_case.label,
                    prompt_case.prompt,
                    prompt_case.source_path,
                    int(bool(self.tools_var.get())),
                    str(left.model_path or ""),
                    self._model_setup_text("left"),
                    left.last_input_tokens,
                    left.last_max_context_tokens,
                    left.last_remaining_after_output_cap if left.last_remaining_after_output_cap is not None else "",
                    f"{left.last_usage_ratio * 100.0:.2f}" if left.last_usage_ratio is not None else "",
                    left.last_assistant_text,
                    left.last_word_count,
                    left.last_char_count,
                    left.last_latency_ms if left.last_latency_ms is not None else "",
                    str(right.model_path or ""),
                    self._model_setup_text("right"),
                    right.last_input_tokens,
                    right.last_max_context_tokens,
                    right.last_remaining_after_output_cap if right.last_remaining_after_output_cap is not None else "",
                    f"{right.last_usage_ratio * 100.0:.2f}" if right.last_usage_ratio is not None else "",
                    right.last_assistant_text,
                    right.last_word_count,
                    right.last_char_count,
                    right.last_latency_ms if right.last_latency_ms is not None else "",
                ]
            )
        self.export_var.set(f"CSV log: {csv_path}")

    def _append_dialogue_csv_row(
        self,
        *,
        speaker_key: str,
        speaker_name: str,
        listener_name: str,
        input_text: str,
        output_text: str,
        pane: ComparePane,
    ) -> None:
        prompt_case = self.dialogue_prompt_case or PromptCase(
            label="Manual prompt",
            prompt=self.pending_prompt_text,
            prompt_id="manual",
            source_path="",
        )
        csv_path = self._ensure_dialogue_csv_log_path()
        with csv_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    prompt_case.prompt_id,
                    prompt_case.label,
                    prompt_case.source_path,
                    int(bool(self.tools_var.get())),
                    self.dialogue_turn_index,
                    speaker_key,
                    speaker_name,
                    listener_name,
                    str(pane.model_path or ""),
                    self._model_setup_text(speaker_key),
                    input_text,
                    pane.last_input_tokens,
                    pane.last_max_context_tokens,
                    pane.last_remaining_after_output_cap if pane.last_remaining_after_output_cap is not None else "",
                    f"{pane.last_usage_ratio * 100.0:.2f}" if pane.last_usage_ratio is not None else "",
                    output_text,
                    pane.last_word_count,
                    pane.last_char_count,
                    pane.last_latency_ms if pane.last_latency_ms is not None else "",
                ]
            )
        self.export_var.set(f"CSV log: {csv_path}")

    def _clear_dialogue_log(self) -> None:
        return None

    def _append_dialogue_log(self, speaker: str, text: str) -> None:
        return None


def _load_prompt_cases(path: Path) -> list[PromptCase]:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return _load_prompt_cases_from_yaml(path)
    return _extract_prompt_cases_from_markdown(path)


def _load_prompt_cases_from_yaml(path: Path) -> list[PromptCase]:
    try:
        import yaml
    except Exception as exc:
        raise RuntimeError("PyYAML is required to load YAML prompt sets.") from exc

    raw = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    prompts_obj: Any
    if isinstance(raw, dict):
        prompts_obj = raw.get("prompts")
    else:
        prompts_obj = raw
    if not isinstance(prompts_obj, list):
        raise ValueError("YAML prompt set must contain a top-level 'prompts' list.")

    cases: list[PromptCase] = []
    for index, item in enumerate(prompts_obj, start=1):
        if isinstance(item, str):
            prompt = item.strip()
            if not prompt:
                continue
            cases.append(PromptCase(label=f"Prompt {index}", prompt=prompt, prompt_id=f"prompt_{index}", source_path=str(path)))
            continue
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        prompt_id = str(item.get("id") or f"prompt_{index}").strip() or f"prompt_{index}"
        label = str(item.get("title") or item.get("label") or prompt_id).strip() or prompt_id
        cases.append(PromptCase(label=label, prompt=prompt, prompt_id=prompt_id, source_path=str(path)))
    return cases


def _extract_prompt_cases_from_markdown(path: Path) -> list[PromptCase]:
    text = path.read_text(encoding="utf-8-sig")
    heading_re = re.compile(
        r"^##\s+(Prompt\s+\d+)\s*$.*?^```text\s*(.*?)\s*^```",
        re.MULTILINE | re.DOTALL,
    )
    cases = [
        PromptCase(label=match.group(1).strip(), prompt=match.group(2).strip(), prompt_id=f"prompt_{idx}", source_path=str(path))
        for idx, match in enumerate(heading_re.finditer(text), start=1)
        if match.group(2).strip()
    ]
    if cases:
        return cases
    fallback_re = re.compile(r"^```text\s*(.*?)\s*^```", re.MULTILINE | re.DOTALL)
    return [
        PromptCase(label=f"Prompt {idx}", prompt=match.group(1).strip(), prompt_id=f"prompt_{idx}", source_path=str(path))
        for idx, match in enumerate(fallback_re.finditer(text), start=1)
        if match.group(1).strip()
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Athena side-by-side model compare tool")
    parser.add_argument("--model-a", type=Path, default=None, help="Left-side model directory")
    parser.add_argument("--model-b", type=Path, default=None, help="Right-side model directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = ModelCompareApp(model_a=args.model_a, model_b=args.model_b)
    app.run()


if __name__ == "__main__":
    main()
