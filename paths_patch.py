from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import athena_paths


ROOT = Path(__file__).resolve().parent
VERIFY_SCRIPT = ROOT / "verify.py"
RUN_VLLM = ROOT / "run_vllm.ps1"
RUN_UI_PRIVATE = ROOT / "run_ui_private.ps1"
RUNTIME_ROOT = ROOT / ".local" / "runtime"

PUBLIC_BASE_URL = "http://127.0.0.1:8001/v1"
PRIVATE_BASE_URL = "http://127.0.0.1:8002/v1"

RUNTIME_ARTIFACTS = {
    "public": (
        RUNTIME_ROOT / "vllm_runtime.env",
        RUNTIME_ROOT / "vllm_runtime.json",
    ),
    "private": (
        RUNTIME_ROOT / "vllm_private_runtime.env",
        RUNTIME_ROOT / "vllm_private_runtime.json",
    ),
}


def _powershell_exe() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(candidate) if candidate.exists() else "powershell"


POWERSHELL = _powershell_exe()


class PathsPatchApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Athena Paths Patch")
        self.root.geometry("980x640")
        self.root.minsize(820, 520)

        self.private_path = tk.StringVar()
        self.public_path = tk.StringVar()
        self.target = tk.StringVar(value="Public")
        self.status_text = tk.StringVar(value="Ready.")
        self._processes: list[subprocess.Popen[str]] = []

        self._configure_style()
        self._build()
        self.refresh_routes(quiet=True)

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        bg = "#101418"
        panel = "#171d23"
        field = "#202832"
        fg = "#eef3f8"
        muted = "#aab7c4"
        accent = "#5cc8a7"
        self.root.configure(bg=bg)
        style.configure(".", background=bg, foreground=fg, fieldbackground=field)
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure("Panel.TLabel", background=panel, foreground=fg)
        style.configure("Title.TLabel", background=bg, foreground=fg, font=("Segoe UI", 18, "bold"))
        style.configure("Subtle.TLabel", background=bg, foreground=muted, font=("Segoe UI", 9))
        style.configure("TButton", padding=(12, 7), font=("Segoe UI", 10))
        style.configure("Accent.TButton", padding=(12, 7), font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", foreground=[("active", fg), ("!active", fg)])
        style.configure("TEntry", padding=7, fieldbackground=field, foreground=fg)
        style.configure("TCombobox", padding=6, fieldbackground=field, foreground=fg)
        style.configure("Status.TLabel", background=panel, foreground=accent, font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Athena Paths Patch", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Authoritative private/public model routes for Athena-managed launches",
            style="Subtle.TLabel",
        ).pack(anchor=tk.W, pady=(3, 14))

        self.route_file_label = ttk.Label(outer, style="Muted.TLabel")
        self.route_file_label.pack(anchor=tk.W, pady=(0, 12))

        self._build_route_row(
            outer,
            scope="private",
            title="Private Desktop",
            variable=self.private_path,
        )
        self._build_route_row(
            outer,
            scope="public",
            title="Public Portal",
            variable=self.public_path,
        )

        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(12, 10))
        ttk.Label(actions, text="Target", style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Combobox(
            actions,
            textvariable=self.target,
            values=("Public", "Private", "Both"),
            state="readonly",
            width=10,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(actions, text="Set Routes", style="Accent.TButton", command=self.set_routes).pack(side=tk.LEFT)
        ttk.Button(actions, text="Run", command=self.run_target).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Verify", command=self.run_verify).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Stop", command=self.stop_target).pack(side=tk.LEFT, padx=(8, 0))

        status = ttk.Frame(outer, style="Panel.TFrame", padding=(12, 10))
        status.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(status, textvariable=self.status_text, style="Status.TLabel").pack(anchor=tk.W)

        output_frame = ttk.Frame(outer)
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output = tk.Text(
            output_frame,
            height=12,
            wrap=tk.WORD,
            bg="#0b0f13",
            fg="#dce6ef",
            insertbackground="#dce6ef",
            relief=tk.FLAT,
            padx=12,
            pady=10,
            font=("Consolas", 10),
        )
        scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output.yview)
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_route_row(self, parent: ttk.Frame, *, scope: str, title: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        frame.pack(fill=tk.X, pady=(0, 10))

        top = ttk.Frame(frame, style="Panel.TFrame")
        top.pack(fill=tk.X)
        ttk.Label(top, text=title, style="Panel.TLabel", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        marker = ttk.Label(top, text="", style="Panel.TLabel")
        marker.pack(side=tk.RIGHT)
        setattr(self, f"{scope}_marker", marker)

        row = ttk.Frame(frame, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=(9, 0))
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Double-Button-1>", lambda _event, selected_scope=scope: self.browse(selected_scope))

    def browse(self, scope: str) -> None:
        current = self.private_path.get() if scope == "private" else self.public_path.get()
        initial = current if current and Path(current).exists() else str(ROOT)
        selected = filedialog.askdirectory(title=f"Select {scope} model folder", initialdir=initial)
        if not selected:
            return
        if scope == "private":
            self.private_path.set(selected)
        else:
            self.public_path.set(selected)
        self._refresh_marker(scope, selected)

    def append_output(self, text: str) -> None:
        self.output.insert(tk.END, text.rstrip() + "\n")
        self.output.see(tk.END)

    def append_output_threadsafe(self, text: str) -> None:
        self.root.after(0, self.append_output, text)

    def clear_output(self) -> None:
        self.output.delete("1.0", tk.END)

    def refresh_routes(self, quiet: bool = False) -> None:
        routes = athena_paths.get_authoritative_model_routes()
        self.private_path.set(routes["private_model_dir"])
        self.public_path.set(routes["public_model_dir"])
        self.route_file_label.configure(text=f"routes: {routes['routes_file']}")
        self._refresh_marker("private", routes["private_model_dir"])
        self._refresh_marker("public", routes["public_model_dir"])
        if not quiet:
            self.status_text.set("Routes refreshed from canonical route file.")

    def _refresh_marker(self, scope: str, path_text: str) -> None:
        marker = getattr(self, f"{scope}_marker")
        path = Path(path_text)
        config = path / "config.json"
        single = path / "model.safetensors"
        index = path / "model.safetensors.index.json"
        shard_count = len(list(path.glob("model.safetensors-*.safetensors"))) if path.exists() else 0
        if not path.exists():
            marker.configure(text="missing")
        elif not config.exists():
            marker.configure(text="no config.json")
        elif single.exists():
            if scope == "private" and self._looks_private_exportable(path):
                marker.configure(text="private exportable")
            elif scope == "private":
                marker.configure(text="not AthenaV1 overlay")
            else:
                marker.configure(text="single safetensors")
        elif index.exists() or shard_count:
            if scope == "private":
                marker.configure(text="not private-exportable: sharded")
            else:
                marker.configure(text=f"sharded safetensors ({shard_count})")
        else:
            marker.configure(text="no weights")

    def _looks_private_exportable(self, path: Path) -> bool:
        config_path = path / "config.json"
        if not config_path.exists() or not (path / "model.safetensors").exists():
            return False
        try:
            import json

            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return False
        architectures = [str(item) for item in list(config.get("architectures") or [])]
        model_type = str(config.get("model_type") or "")
        return "Qwen3_5ForCausalLM" in architectures or model_type == "qwen3_5_text"

    def _selected_scopes(self) -> tuple[str, ...]:
        selected = self.target.get().strip().lower()
        if selected == "both":
            return ("private", "public")
        if selected == "private":
            return ("private",)
        return ("public",)

    def _path_for_scope(self, scope: str) -> str:
        return self.private_path.get().strip() if scope == "private" else self.public_path.get().strip()

    def _validate_path_for_scope(self, scope: str, path_text: str) -> Path:
        if not path_text:
            raise ValueError("model directory was empty")
        path = Path(path_text).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"model directory does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"model path is not a directory: {path}")
        if not (path / "config.json").exists():
            raise ValueError(f"model directory is missing config.json: {path}")
        has_single = (path / "model.safetensors").exists()
        has_index = (path / "model.safetensors.index.json").exists()
        has_shards = any(path.glob("model.safetensors-*.safetensors"))
        if not (has_single or has_index or has_shards):
            raise ValueError(f"model directory has no safetensors weights: {path}")
        if scope == "private":
            if not has_single:
                raise ValueError(f"private route must contain a single model.safetensors: {path}")
            if not self._looks_private_exportable(path):
                raise ValueError(f"private route is not AthenaV1 exporter-compatible: {path}")
        return path

    def set_routes(self) -> bool:
        validated: dict[str, Path] = {}
        for scope in self._selected_scopes():
            path_text = self._path_for_scope(scope)
            try:
                validated[scope] = self._validate_path_for_scope(scope, path_text)
            except Exception as exc:
                messagebox.showerror("Athena Paths Patch", f"{scope}: {exc}")
                self.status_text.set("Routes were not changed.")
                return False

        changed: dict[str, Path] = {}
        for scope, path in validated.items():
            try:
                changed[scope] = athena_paths.set_authoritative_model_route(scope, path)
            except Exception as exc:
                messagebox.showerror("Athena Paths Patch", f"{scope}: {exc}")
                self.status_text.set("Routes were not changed.")
                return False

        self.refresh_routes(quiet=True)
        self.clear_output()
        for scope, path in changed.items():
            self.append_output(f"canonical_{scope}_model_dir={path}")
            self.append_output(f"next_{scope}_served_model={path.name}")
        scopes = ", ".join(changed)
        self.status_text.set(f"path changed successfully: {scopes} route file updated")
        return True

    def _child_env(self, scope: str, model_dir: Path) -> dict[str, str]:
        env = os.environ.copy()
        for name in (
            "ATHENA_CHAT_MODEL_DIR",
            "ATHENA_VLLM_MODEL_DIR",
            "ATHENA_VLLM_MODEL",
            "ATHENA_VLLM_BASE_URL",
            "ATHENA_PUBLIC_CHAT_MODEL_DIR",
            "ATHENA_PUBLIC_VLLM_MODEL_DIR",
            "ATHENA_PUBLIC_VLLM_MODEL_NAME",
            "ATHENA_PUBLIC_VLLM_BASE_URL",
            "ATHENA_PRIVATE_CHAT_MODEL_DIR",
            "ATHENA_PRIVATE_VLLM_SOURCE_MODEL_DIR",
            "ATHENA_PRIVATE_VLLM_BASE_URL",
        ):
            env.pop(name, None)
        if scope == "public":
            env["ATHENA_PUBLIC_CHAT_MODEL_DIR"] = str(model_dir)
            env["ATHENA_PUBLIC_VLLM_MODEL_DIR"] = str(model_dir)
            env["ATHENA_PUBLIC_VLLM_MODEL_NAME"] = model_dir.name
            env["ATHENA_PUBLIC_VLLM_BASE_URL"] = PUBLIC_BASE_URL
            env["ATHENA_RUNTIME_SCOPE"] = "public"
            env["ATHENA_PRIVATE_MODE"] = "0"
        else:
            env["ATHENA_PRIVATE_CHAT_MODEL_DIR"] = str(model_dir)
            env["ATHENA_PRIVATE_VLLM_SOURCE_MODEL_DIR"] = str(model_dir)
            env["ATHENA_PRIVATE_VLLM_BASE_URL"] = PRIVATE_BASE_URL
            env["ATHENA_RUNTIME_SCOPE"] = "private"
            env["ATHENA_PRIVATE_MODE"] = "1"
        return env

    def _run_powershell_capture(self, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", *args]
        return subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_powershell_stream(self, label: str, args: list[str], env: dict[str, str] | None = None) -> None:
        command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", *args]
        self.append_output(f"{label}")
        self.append_output(" ".join(f'"{part}"' if " " in part else part for part in command))

        def worker() -> None:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self._processes.append(process)
                if process.stdout is not None:
                    for line in process.stdout:
                        self.append_output_threadsafe(line.rstrip())
                exit_code = process.wait()
                self.root.after(0, self.status_text.set, f"{label} finished with code {exit_code}.")
            except Exception as exc:
                self.append_output_threadsafe(f"{label} failed to launch: {exc}")
                self.root.after(0, self.status_text.set, f"{label} failed to launch.")

        threading.Thread(target=worker, daemon=True).start()

    def _cleanup_runtime_artifacts(self, scope: str) -> None:
        for path in RUNTIME_ARTIFACTS[scope]:
            try:
                path.unlink(missing_ok=True)
                self.append_output(f"cleared_runtime_artifact={path}")
            except Exception as exc:
                self.append_output(f"could_not_clear_runtime_artifact={path} reason={exc}")

    def _stop_managed_runtime(self, scope: str) -> None:
        runtime_name = "private" if scope == "private" else "shared"
        base_url = PRIVATE_BASE_URL if scope == "private" else PUBLIC_BASE_URL
        result = self._run_powershell_capture(
            ["-File", str(RUN_VLLM), "-RuntimeName", runtime_name, "-BaseUrl", base_url, "-Stop"]
        )
        if result.stdout:
            self.append_output(result.stdout)
        if result.stderr:
            self.append_output(result.stderr)
        if result.returncode != 0:
            raise RuntimeError(f"{scope} managed runtime stop failed with code {result.returncode}")
        self._cleanup_runtime_artifacts(scope)

    def _canonical_routes(self) -> dict[str, Path]:
        routes = athena_paths.get_authoritative_model_routes()
        return {
            "private": Path(routes["private_model_dir"]),
            "public": Path(routes["public_model_dir"]),
        }

    def run_target(self) -> None:
        try:
            if not self.set_routes():
                return
            routes = self._canonical_routes()
            self.append_output("")
            for scope in self._selected_scopes():
                self.append_output(f"stopping_managed_{scope}_runtime=true")
                self._stop_managed_runtime(scope)
                model_dir = routes[scope]
                env = self._child_env(scope, model_dir)
                if scope == "public":
                    self.append_output(f"public_resolved_model_dir={model_dir}")
                    self.append_output(f"public_served_model={model_dir.name}")
                    self._run_powershell_stream(
                        "Public managed vLLM launch",
                        [
                            "-File",
                            str(RUN_VLLM),
                            "-RuntimeName",
                            "shared",
                            "-ModelDir",
                            str(model_dir),
                            "-ServedModelName",
                            model_dir.name,
                            "-BaseUrl",
                            PUBLIC_BASE_URL,
                            "-Port",
                            "8001",
                            "-LanguageModelOnly",
                            "-Restart",
                        ],
                        env=env,
                    )
                else:
                    self.append_output(f"private_resolved_model_dir={model_dir}")
                    self.append_output(f"private_served_model={model_dir.name}")
                    self._run_powershell_stream(
                        "Private desktop launch",
                        [
                            "-File",
                            str(RUN_UI_PRIVATE),
                            "-ModelDir",
                            str(model_dir),
                            "-BaseUrl",
                            PRIVATE_BASE_URL,
                            "-ForceRuntimeRestart",
                        ],
                        env=env,
                    )
            targets = ", ".join(self._selected_scopes())
            self.status_text.set(f"Run started for {targets}. Use Verify after launch settles.")
        except Exception as exc:
            messagebox.showerror("Athena Paths Patch", str(exc))
            self.status_text.set("Run stopped before launch completed.")

    def stop_target(self) -> None:
        self.clear_output()
        try:
            for scope in self._selected_scopes():
                self.append_output(f"stopping_managed_{scope}_runtime=true")
                self._stop_managed_runtime(scope)
            targets = ", ".join(self._selected_scopes())
            self.status_text.set(f"Managed runtime stopped for {targets}.")
        except Exception as exc:
            messagebox.showerror("Athena Paths Patch", str(exc))
            self.status_text.set("Stop failed.")

    def run_verify(self) -> None:
        if not VERIFY_SCRIPT.exists():
            messagebox.showerror("Athena Paths Patch", f"verify.py not found: {VERIFY_SCRIPT}")
            return
        self.status_text.set("Running verify.py...")
        self.root.update_idletasks()
        result = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.clear_output()
        final_line = ""
        for line in (result.stdout or "").splitlines():
            if line.strip():
                final_line = line.strip()
        if final_line:
            self.append_output(final_line)
        if result.stderr:
            self.append_output(result.stderr)
        if result.returncode == 0:
            self.status_text.set("Verify completed successfully.")
        else:
            self.status_text.set(f"Verify failed with code {result.returncode}.")


def main() -> int:
    root = tk.Tk()
    PathsPatchApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
