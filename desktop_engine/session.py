from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable, Optional, Sequence

from athena_paths import get_default_chat_model_dir, get_gui_config, get_gui_config_path, get_system_prompt_path
from desktop_engine.events import EngineEvent
from desktop_engine.runtime import AthenaRuntime, ChatTurnResult, RuntimeMessage

EventListener = Callable[[EngineEvent], None]


def _message_dict(message: RuntimeMessage) -> dict[str, str]:
    return {"role": message.role, "content": message.content}


def _local_user_message_content(prompt: str, image_paths: Sequence[str]) -> str:
    clean_prompt = (prompt or "").strip()
    parts: list[str] = []
    if clean_prompt:
        parts.append(clean_prompt)
    if image_paths:
        marker = f"[attached image {len(image_paths)}]" if len(image_paths) == 1 else f"[attached images: {len(image_paths)}]"
        parts.append(marker)
        for idx, path in enumerate(image_paths, start=1):
            try:
                uri = Path(path).resolve().as_uri()
            except Exception:
                uri = ""
            parts.append(f"![attached image {idx}]({uri})" if uri else f"[image {idx}: {Path(path).name}]")
    return "\n\n".join(parts) if parts else "Image attached."


@dataclass(frozen=True)
class WorkerRunResult:
    turn: ChatTurnResult
    model_loaded: bool


class ChatWorker:
    def __init__(self, *, model_dir: Optional[Path | str] = None, tools_enabled: bool = False, load_model: bool = True):
        self.model_dir = Path(model_dir).expanduser().resolve() if model_dir else get_default_chat_model_dir()
        self.tools_enabled = bool(tools_enabled)
        self.load_model = bool(load_model)
        self._lock = threading.Lock()
        self._runtime: AthenaRuntime | None = None
        self._model_load_error = ""

    @property
    def model_loaded(self) -> bool:
        return self._runtime is not None

    @property
    def model_load_error(self) -> str:
        return self._model_load_error

    def warm_start(self) -> None:
        if not self.load_model:
            return
        with self._lock:
            self._ensure_loaded()

    def cancel(self) -> None:
        runtime = self._runtime
        if runtime is not None:
            runtime.cancel()

    def set_tools_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.tools_enabled = bool(enabled)
            if self._runtime is not None:
                self._runtime.tools_enabled = self.tools_enabled

    def runtime_snapshot(self) -> dict[str, Any]:
        if self._runtime is None:
            gui_config = get_gui_config()
            system_prompt_path = get_system_prompt_path()
            return {
                "model_dir": str(self.model_dir),
                "model_label": self.model_dir.name,
                "gui_config_path": str(get_gui_config_path()),
                "system_prompt_path": str(system_prompt_path),
                "system_prompt_format": system_prompt_path.suffix.lower().lstrip(".") or "text",
                "temperature": float(gui_config["temperature"]),
                "max_new_tokens": int(gui_config["max_new_tokens"]),
                "top_p": float(gui_config["top_p"]),
                "top_k": int(gui_config["top_k"]),
                "repetition_penalty": float(gui_config["repetition_penalty"]),
                "tools_enabled": self.tools_enabled,
                "sampling_enabled": float(gui_config["temperature"]) > 0.0,
                "model_loaded": False,
                "model_load_error": self._model_load_error,
            }
        data = self._runtime.runtime_config()
        data["model_loaded"] = True
        data["model_load_error"] = self._model_load_error
        return data

    def estimate_tokens(
        self,
        *,
        prompt: str,
        history: Sequence[RuntimeMessage | dict[str, Any]],
        image_paths: Sequence[str],
        tools_enabled: bool | None = None,
        system_prompt_override: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime
        if runtime is None:
            return {
                "available": False,
                "reason": "Warm the model to estimate exact tokens.",
                "input_tokens": 0,
                "max_context_tokens": 0,
                "remaining_tokens": None,
                "remaining_after_output_cap": None,
            }
        with self._lock:
            return runtime.estimate_turn_tokens(
                prompt=prompt,
                history=history,
                image_paths=image_paths,
                tools_enabled=self.tools_enabled if tools_enabled is None else bool(tools_enabled),
                system_prompt_override=system_prompt_override,
            )

    def run_turn(
        self,
        *,
        prompt: str,
        history: Sequence[RuntimeMessage],
        image_paths: Sequence[str],
        emit: EventListener,
        system_prompt_override: str | None = None,
    ) -> WorkerRunResult:
        if not self.load_model:
            message = "Portal setup mode is active. Model loading is disabled."
            emit(EngineEvent(type="assistant_delta", text=message, role="assistant"))
            return WorkerRunResult(
                turn=ChatTurnResult(assistant=message, visible_messages=[RuntimeMessage("assistant", message)]),
                model_loaded=False,
            )
        with self._lock:
            if self._runtime is None:
                emit(EngineEvent(type="status", text="Loading model..."))
            self._ensure_loaded()
            emit(EngineEvent(type="status", text="Generating..."))
            result = self._runtime.stream_turn(
                prompt=prompt,
                history=history,
                image_paths=image_paths,
                on_event=emit,
                system_prompt_override=system_prompt_override,
            )
            return WorkerRunResult(turn=result, model_loaded=self.model_loaded)

    def _ensure_loaded(self) -> None:
        if self._runtime is not None:
            return
        try:
            self._runtime = AthenaRuntime(model_dir=self.model_dir, tools_enabled=self.tools_enabled)
        except Exception as exc:
            self._model_load_error = str(exc)
            raise


class EngineSession:
    def __init__(self, worker: ChatWorker):
        self._worker = worker
        self._history: list[RuntimeMessage] = []
        self._turn_thread: threading.Thread | None = None
        self._listener: EventListener | None = None
        self._lock = threading.Lock()

    def set_listener(self, listener: EventListener | None) -> None:
        self._listener = listener

    def restore_history(self, messages: Iterable[RuntimeMessage | dict[str, Any]]) -> None:
        normalized: list[RuntimeMessage] = []
        for item in messages:
            if isinstance(item, RuntimeMessage):
                normalized.append(item)
                continue
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "")
            if not role or not content:
                continue
            normalized.append(RuntimeMessage(role=role, content=content))
        with self._lock:
            self._history = normalized

    def history_snapshot(self) -> list[dict[str, str]]:
        with self._lock:
            return [_message_dict(item) for item in self._history]

    def runtime_snapshot(self) -> dict[str, Any]:
        return self._worker.runtime_snapshot()

    def estimate_tokens(
        self,
        prompt: str,
        *,
        image_paths: Optional[Sequence[str]] = None,
        tools_enabled: bool | None = None,
        system_prompt_override: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            history = list(self._history)
        return self._worker.estimate_tokens(
            prompt=prompt,
            history=history,
            image_paths=[str(path) for path in (image_paths or [])],
            tools_enabled=tools_enabled,
            system_prompt_override=system_prompt_override,
        )

    def set_tools_enabled(self, enabled: bool) -> None:
        self._worker.set_tools_enabled(enabled)

    def submit_turn(
        self,
        prompt: str,
        *,
        image_paths: Optional[Sequence[str]] = None,
        display_user_content: str | None = None,
        listener: EventListener | None = None,
        system_prompt_override: str | None = None,
    ) -> None:
        callback = listener or self._listener
        with self._lock:
            if self._turn_thread is not None and self._turn_thread.is_alive():
                raise RuntimeError("A turn is already in progress.")
            image_list = [str(path) for path in (image_paths or [])]
            worker_thread = threading.Thread(
                target=self._run_turn,
                args=(prompt, image_list, display_user_content, callback, system_prompt_override),
                daemon=True,
            )
            self._turn_thread = worker_thread
            worker_thread.start()

    def cancel_turn(self) -> None:
        self._worker.cancel()

    def reset_conversation(self) -> None:
        self.cancel_turn()
        with self._lock:
            self._history = []

    def _emit(self, callback: EventListener | None, event: EngineEvent) -> None:
        if callback is not None:
            callback(event)

    def _run_turn(
        self,
        prompt: str,
        image_paths: list[str],
        display_user_content: str | None,
        callback: EventListener | None,
        system_prompt_override: str | None,
    ) -> None:
        started_at = perf_counter()
        history_snapshot = self.history_snapshot()
        runtime_history = [RuntimeMessage(role=item["role"], content=item["content"]) for item in history_snapshot]
        self._emit(callback, EngineEvent(type="status", text="Preparing response..."))
        try:
            worker_result = self._worker.run_turn(
                prompt=prompt,
                history=runtime_history,
                image_paths=image_paths,
                emit=lambda event: self._emit(callback, event),
                system_prompt_override=system_prompt_override,
            )
            user_content = display_user_content or _local_user_message_content(prompt, image_paths)
            next_history = runtime_history + [RuntimeMessage("user", user_content)] + worker_result.turn.visible_messages
            with self._lock:
                self._history = list(next_history)
            metrics = {
                "latency_ms": int((perf_counter() - started_at) * 1000),
                "image_count": len(image_paths),
                "visible_message_count": len(next_history),
            }
            self._emit(
                callback,
                EngineEvent(
                    type="turn_done",
                    assistant=worker_result.turn.assistant,
                    visible_messages=[_message_dict(item) for item in next_history],
                    metrics=metrics,
                    model_loaded=worker_result.model_loaded,
                ),
            )
        except Exception as exc:
            self._emit(callback, EngineEvent(type="turn_error", message=str(exc)))


class DesktopEngine:
    def __init__(self, *, model_dir: Optional[Path | str] = None, tools_enabled: bool = False, load_model: bool = True):
        self._chat_worker = ChatWorker(model_dir=model_dir, tools_enabled=tools_enabled, load_model=load_model)

    def create_session(self) -> EngineSession:
        return EngineSession(self._chat_worker)

    def runtime_snapshot(self) -> dict[str, Any]:
        return self._chat_worker.runtime_snapshot()

    def set_tools_enabled(self, enabled: bool) -> None:
        self._chat_worker.set_tools_enabled(enabled)

    def warm_start(self) -> None:
        self._chat_worker.warm_start()
