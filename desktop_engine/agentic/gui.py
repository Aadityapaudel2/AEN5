from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from athena_paths import get_evaluation_testdata_dir, get_orchestrator_model_dir, get_root_dir

from .loop import run_math_loop
from .schemas import MathLoopResult, MathLoopStep


class MathLoopObserverApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("2-Body Math Loop Observer")
        self.root.geometry("1680x980")
        self.root.minsize(1320, 820)

        self.result_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.result: MathLoopResult | None = None
        self.worker: threading.Thread | None = None
        self.step_records: list[MathLoopStep] = []

        self.model_dir_var = tk.StringVar(value=str(get_orchestrator_model_dir()))
        self.max_rounds_var = tk.IntVar(value=2)
        self.tools_enabled_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Idle")
        self.final_answer_var = tk.StringVar(value="")
        self.verified_var = tk.StringVar(value="")
        self.rounds_var = tk.StringVar(value="")
        self.stopped_reason_var = tk.StringVar(value="")
        self.error_var = tk.StringVar(value="")
        self.problem_file_var = tk.StringVar(value="")

        self._build_ui()
        self.root.after(150, self._poll_result_queue)

    def _build_ui(self) -> None:
        self.root.configure(bg="#07162e")
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Model Dir").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(header, textvariable=self.model_dir_var).grid(row=0, column=1, sticky="ew")
        self.browse_model_button = ttk.Button(header, text="Browse", command=self._browse_model_dir)
        self.browse_model_button.grid(row=0, column=2, padx=(8, 0))

        ttk.Label(header, text="Rounds").grid(row=0, column=3, sticky="w", padx=(16, 8))
        ttk.Spinbox(header, from_=1, to=4, textvariable=self.max_rounds_var, width=6).grid(row=0, column=4, sticky="w")
        ttk.Checkbutton(header, text="Tools On", variable=self.tools_enabled_var).grid(row=0, column=5, padx=(16, 0))
        self.load_problem_button = ttk.Button(header, text="Load Problem File", command=self._load_problem_file)
        self.load_problem_button.grid(row=0, column=6, padx=(16, 0))
        self.run_loop_button = ttk.Button(header, text="Run Loop", command=self._run_loop)
        self.run_loop_button.grid(row=0, column=7, padx=(8, 0))

        ttk.Label(header, textvariable=self.problem_file_var, foreground="#9fc6ff").grid(
            row=1, column=0, columnspan=8, sticky="w", pady=(8, 0)
        )

        body = ttk.Panedwindow(main, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew")

        left = ttk.Frame(body, padding=(0, 0, 8, 0))
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        body.add(left, weight=3)
        body.add(right, weight=2)

        ttk.Label(left, text="Problem").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.problem_text = tk.Text(
            left,
            wrap="word",
            font=("Consolas", 11),
            bg="#041126",
            fg="#f3f7ff",
            insertbackground="#f3f7ff",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.problem_text.grid(row=1, column=0, sticky="nsew")

        summary = ttk.LabelFrame(right, text="Result Summary", padding=10)
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(1, weight=1)
        summary.columnconfigure(3, weight=1)

        self._summary_row(summary, 0, "Status", self.status_var, "Final Answer", self.final_answer_var)
        self._summary_row(summary, 1, "Verified", self.verified_var, "Rounds Used", self.rounds_var)
        self._summary_row(summary, 2, "Stopped Reason", self.stopped_reason_var, "Error", self.error_var)

        step_frame = ttk.LabelFrame(right, text="Trace Steps", padding=10)
        step_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 10))
        step_frame.columnconfigure(0, weight=1)
        step_frame.rowconfigure(0, weight=1)
        self.step_list = tk.Listbox(
            step_frame,
            font=("Consolas", 10),
            bg="#041126",
            fg="#f3f7ff",
            selectbackground="#0b4fa5",
            relief="flat",
        )
        self.step_list.grid(row=0, column=0, sticky="nsew")
        self.step_list.bind("<<ListboxSelect>>", self._on_step_selected)

        detail_frame = ttk.LabelFrame(right, text="Step Detail", padding=10)
        detail_frame.grid(row=2, column=0, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)
        self.detail_notebook = ttk.Notebook(detail_frame)
        self.detail_notebook.grid(row=0, column=0, sticky="nsew")

        self.prompt_view = self._make_detail_text(self.detail_notebook)
        self.raw_view = self._make_detail_text(self.detail_notebook)
        self.parsed_view = self._make_detail_text(self.detail_notebook)
        self.tools_view = self._make_detail_text(self.detail_notebook)
        self.detail_notebook.add(self.prompt_view, text="Prompt")
        self.detail_notebook.add(self.raw_view, text="Raw Output")
        self.detail_notebook.add(self.parsed_view, text="Parsed")
        self.detail_notebook.add(self.tools_view, text="Tool Events")

    def _summary_row(
        self,
        parent: ttk.LabelFrame,
        row_index: int,
        left_label: str,
        left_var: tk.StringVar,
        right_label: str,
        right_var: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=left_label).grid(row=row_index, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Label(parent, textvariable=left_var, foreground="#9fc6ff").grid(
            row=row_index, column=1, sticky="w", pady=2
        )
        ttk.Label(parent, text=right_label).grid(row=row_index, column=2, sticky="w", padx=(16, 8), pady=2)
        ttk.Label(parent, textvariable=right_var, foreground="#9fc6ff").grid(
            row=row_index, column=3, sticky="w", pady=2
        )

    def _make_detail_text(self, parent: ttk.Notebook) -> tk.Text:
        widget = tk.Text(
            parent,
            wrap="word",
            font=("Consolas", 10),
            bg="#041126",
            fg="#f3f7ff",
            insertbackground="#f3f7ff",
            relief="flat",
            padx=10,
            pady=10,
        )
        widget.configure(state="disabled")
        return widget

    def _browse_model_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.model_dir_var.get() or str(get_root_dir()))
        if selected:
            self.model_dir_var.set(selected)

    def _load_problem_file(self) -> None:
        initial_dir = get_evaluation_testdata_dir() / "aimo" / "problems"
        selected = filedialog.askopenfilename(
            initialdir=str(initial_dir),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not selected:
            return
        path = Path(selected)
        text = path.read_text(encoding="utf-8-sig")
        self.problem_text.delete("1.0", "end")
        self.problem_text.insert("1.0", text.strip())
        self.problem_file_var.set(f"Loaded: {path}")

    def _run_loop(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Math Loop", "A run is already in progress.")
            return
        problem = self.problem_text.get("1.0", "end").strip()
        if not problem:
            messagebox.showwarning("Math Loop", "Provide a problem before running the loop.")
            return
        model_dir = self.model_dir_var.get().strip()
        max_rounds = int(self.max_rounds_var.get())
        tools_enabled = bool(self.tools_enabled_var.get())
        self._set_running_state(True)
        self._clear_result_views()
        self.status_var.set("Running...")

        def worker() -> None:
            try:
                result = run_math_loop(
                    problem,
                    model_dir=model_dir,
                    max_rounds=max_rounds,
                    tools_enabled=tools_enabled,
                    on_step=lambda step: self.result_queue.put(("step", step)),
                )
                self.result_queue.put(("result", result))
            except Exception as exc:  # noqa: BLE001
                self.result_queue.put(("error", exc))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.browse_model_button.configure(state=state)
        self.load_problem_button.configure(state=state)
        self.run_loop_button.configure(state=state)

    def _poll_result_queue(self) -> None:
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "result":
                    self._apply_result(payload)  # type: ignore[arg-type]
                elif kind == "step":
                    self._append_step(payload)  # type: ignore[arg-type]
                else:
                    self._apply_error(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        self.root.after(150, self._poll_result_queue)

    def _apply_result(self, result: MathLoopResult) -> None:
        self._set_running_state(False)
        self.result = result
        self.step_records = list(result.trace.steps)
        self.status_var.set(result.status)
        self.final_answer_var.set(result.final_answer or "(empty)")
        self.verified_var.set(str(result.verified).lower())
        self.rounds_var.set(str(result.rounds_used))
        self.stopped_reason_var.set(result.trace.stopped_reason or "-")
        self.error_var.set(result.error_message or "-")
        self.step_list.delete(0, "end")
        for step in self.step_records:
            label = f"round {step.round_index} | {step.role} | {step.status} | {step.latency_ms} ms"
            self.step_list.insert("end", label)
        if self.step_records:
            self.step_list.selection_set(0)
            self._show_step_detail(self.step_records[0])

    def _apply_error(self, exc: Exception) -> None:
        self._set_running_state(False)
        self.status_var.set("failed")
        self.error_var.set(str(exc))
        messagebox.showerror("Math Loop", str(exc))

    def _append_step(self, step: MathLoopStep) -> None:
        self.step_records.append(step)
        label = f"round {step.round_index} | {step.role} | {step.status} | {step.latency_ms} ms"
        self.step_list.insert("end", label)
        self.status_var.set(f"Running... {step.role} {step.status}")
        last_index = self.step_list.size() - 1
        if last_index >= 0:
            self.step_list.selection_clear(0, "end")
            self.step_list.selection_set(last_index)
            self.step_list.see(last_index)
            self._show_step_detail(step)

    def _clear_result_views(self) -> None:
        self.result = None
        self.step_records = []
        self.step_list.delete(0, "end")
        self.final_answer_var.set("")
        self.verified_var.set("")
        self.rounds_var.set("")
        self.stopped_reason_var.set("")
        self.error_var.set("")
        self._set_text(self.prompt_view, "")
        self._set_text(self.raw_view, "")
        self._set_text(self.parsed_view, "")
        self._set_text(self.tools_view, "")

    def _on_step_selected(self, _event: object) -> None:
        selection = self.step_list.curselection()
        if not selection:
            return
        index = int(selection[0])
        if 0 <= index < len(self.step_records):
            self._show_step_detail(self.step_records[index])

    def _show_step_detail(self, step: MathLoopStep) -> None:
        self._set_text(self.prompt_view, step.prompt_text)
        self._set_text(self.raw_view, step.raw_output)
        self._set_text(self.parsed_view, json.dumps(step.parsed_output, ensure_ascii=False, indent=2))
        self._set_text(self.tools_view, json.dumps(step.tool_events, ensure_ascii=False, indent=2))

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")


def launch() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background="#07162e", foreground="#f3f7ff", fieldbackground="#07162e")
    style.configure("TFrame", background="#07162e")
    style.configure("TLabelframe", background="#07162e", foreground="#f3f7ff")
    style.configure("TLabelframe.Label", background="#07162e", foreground="#f3f7ff")
    style.configure("TLabel", background="#07162e", foreground="#f3f7ff")
    style.configure("TCheckbutton", background="#07162e", foreground="#f3f7ff")
    style.configure("TButton", padding=6)
    style.configure("TNotebook", background="#07162e")
    style.configure("TNotebook.Tab", padding=(10, 4))
    app = MathLoopObserverApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
