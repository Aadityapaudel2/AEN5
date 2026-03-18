from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from transformers import AutoTokenizer

from athena_paths import (
    get_default_chat_model_dir,
    get_gui_config,
    get_gui_config_path,
    get_system_prompt_path,
)
from desktop_engine.events import EngineEvent
from desktop_engine.runtime import (
    ChatTurnResult,
    RuntimeMessage,
    StreamSanitizer,
    clean_assistant_text,
    sanitize_user_text,
    _load_system_prompt,
)


class VllmOpenAIRuntime:
    def __init__(self, *, model_dir: Optional[Path | str] = None, tools_enabled: Optional[bool] = None):
        self.model_dir = Path(model_dir).expanduser().resolve() if model_dir else get_default_chat_model_dir()
        self.model_label = self.model_dir.name
        self.tools_enabled = bool(tools_enabled)
        self.system_prompt, self.system_prompt_path, self.system_prompt_format = _load_system_prompt(self.model_dir)
        self.gui_config = get_gui_config(self.model_dir)
        self.gui_config_path = get_gui_config_path(self.model_dir)
        self.temperature = float(self.gui_config["temperature"])
        self.max_new_tokens = int(self.gui_config["max_new_tokens"])
        self.top_p = float(self.gui_config["top_p"])
        self.top_k = int(self.gui_config["top_k"])
        self.repetition_penalty = float(self.gui_config["repetition_penalty"])
        self.no_repeat_ngram_size = int(self.gui_config["no_repeat_ngram_size"])
        self.stop_event = threading.Event()

        self.base_url = (os.getenv("ATHENA_VLLM_BASE_URL") or "http://127.0.0.1:8001/v1").strip().rstrip("/")
        self.api_key = (os.getenv("ATHENA_VLLM_API_KEY") or "athena-local").strip() or "athena-local"
        self.remote_model = (os.getenv("ATHENA_VLLM_MODEL") or "").strip()
        self.timeout_seconds = max(10.0, float((os.getenv("ATHENA_VLLM_TIMEOUT_SECONDS") or "300").strip() or "300"))
        self.max_context_token_hint = max(0, int((os.getenv("ATHENA_VLLM_MAX_CONTEXT_TOKENS") or "0").strip() or "0"))
        self.enable_thinking = ((os.getenv("ATHENA_VLLM_ENABLE_THINKING") or "0").strip().lower() in {"1", "true", "yes", "on"})

        self._active_response_lock = threading.Lock()
        self._active_response: Any | None = None
        self._tokenizer_lock = threading.Lock()
        self._tokenizer = None

    def runtime_config(self) -> dict[str, Any]:
        return {
            "model_dir": self.base_url,
            "model_label": self.remote_model or self.model_label,
            "base_model_dir": self.base_url,
            "adapter_dir": "",
            "overlay_source_dir": "",
            "overlay_state_dict_path": "",
            "device": "remote:vllm",
            "dtype": "remote",
            "temperature": self.temperature,
            "max_new_tokens": self.max_new_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "no_repeat_ngram_size": self.no_repeat_ngram_size,
            "tools_enabled": self.tools_enabled,
            "supports_vision": False,
            "image_processor_loaded": False,
            "image_support_error": "Vision routing is not configured for the vLLM backend.",
            "sampling_enabled": self.temperature > 0.0,
            "max_context_tokens": self.max_context_tokens(),
            "gui_config_path": str(self.gui_config_path),
            "system_prompt_path": self.system_prompt_path,
            "system_prompt_format": self.system_prompt_format,
            "runtime_scope": (os.getenv("ATHENA_RUNTIME_SCOPE") or ("private" if os.getenv("ATHENA_PRIVATE_MODE") else "shared")).strip() or "shared",
            "runtime_backend": "vllm_openai",
            "runtime_backend_label": "vLLM OpenAI-compatible",
        }

    def warm_start(self) -> None:
        self._ensure_remote_model()
        self._ensure_tokenizer()

    def cancel(self) -> None:
        self.stop_event.set()
        with self._active_response_lock:
            response = self._active_response
            self._active_response = None
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def max_context_tokens(self) -> int:
        return self.max_context_token_hint

    def estimate_turn_tokens(
        self,
        *,
        prompt: str,
        history: Sequence[RuntimeMessage | dict[str, Any]],
        image_paths: Optional[Sequence[str]] = None,
        tools_enabled: bool = False,
        system_prompt_override: str | None = None,
    ) -> dict[str, Any]:
        if image_paths:
            return {
                "available": False,
                "reason": "Image uploads are not configured for the vLLM backend yet.",
                "input_tokens": 0,
                "max_context_tokens": self.max_context_tokens(),
                "remaining_tokens": None,
                "remaining_after_output_cap": None,
            }
        user_text = (prompt or "").strip()
        if not user_text:
            return {
                "available": False,
                "reason": "Prompt is empty.",
                "input_tokens": 0,
                "max_context_tokens": self.max_context_tokens(),
                "remaining_tokens": None,
                "remaining_after_output_cap": None,
            }
        turns = self._history_to_turns(history)
        messages = self._build_messages(
            turns,
            user_text,
            tools_enabled=tools_enabled,
            system_prompt_override=system_prompt_override,
        )
        joined = "\n".join(self._message_text(msg) for msg in messages)
        input_tokens = max(1, len(joined) // 4)
        max_context = self.max_context_tokens()
        remaining = max(max_context - input_tokens, 0) if max_context > 0 else None
        remaining_after_output_cap = (
            max(max_context - input_tokens - self.max_new_tokens, 0) if max_context > 0 else None
        )
        usage_ratio = (float(input_tokens) / float(max_context)) if max_context > 0 else None
        return {
            "available": True,
            "estimate_mode": "heuristic",
            "input_tokens": input_tokens,
            "max_context_tokens": max_context,
            "remaining_tokens": remaining,
            "remaining_after_output_cap": remaining_after_output_cap,
            "max_new_tokens": self.max_new_tokens,
            "tools_enabled": bool(tools_enabled),
            "usage_ratio": usage_ratio,
        }

    def stream_turn(
        self,
        *,
        prompt: str,
        history: Sequence[RuntimeMessage | dict[str, Any]],
        image_paths: Optional[Sequence[str]] = None,
        on_delta: Optional[Callable[[str], None]] = None,
        on_event: Optional[Callable[[EngineEvent], None]] = None,
        system_prompt_override: str | None = None,
    ) -> ChatTurnResult:
        user_text = (prompt or "").strip()
        if not user_text and not image_paths:
            raise ValueError("Prompt is empty.")
        if image_paths:
            raise ValueError("Image uploads are not configured for the vLLM backend yet.")

        turns = self._history_to_turns(history)
        messages = self._build_messages(
            turns,
            user_text,
            tools_enabled=False,
            system_prompt_override=system_prompt_override,
        )

        def emit_assistant(text: str) -> None:
            if not text:
                return
            if on_event is not None:
                on_event(EngineEvent(type="assistant_delta", text=text, role="assistant"))
            if on_delta is not None:
                on_delta(text)

        assistant = self._generate_text(messages, on_visible=emit_assistant)
        return ChatTurnResult(assistant=assistant, visible_messages=[RuntimeMessage("assistant", assistant)])

    def _history_to_turns(self, history: Sequence[RuntimeMessage | dict[str, Any]]) -> list[tuple[str, str]]:
        turns: list[tuple[str, str]] = []
        pending_user: Optional[str] = None
        for item in history:
            role = str(item.role if isinstance(item, RuntimeMessage) else item.get("role") or "").strip().lower()
            content = str(item.content if isinstance(item, RuntimeMessage) else item.get("content") or "")
            if not content.strip():
                continue
            if role == "user":
                pending_user = sanitize_user_text(content)
                continue
            if role != "assistant" or pending_user is None:
                continue
            assistant = clean_assistant_text(content)
            if assistant:
                turns.append((pending_user, assistant))
            pending_user = None
        return turns

    def _build_messages(
        self,
        turns: Sequence[tuple[str, str]],
        user_text: str,
        *,
        tools_enabled: bool = False,
        system_prompt_override: str | None = None,
    ) -> list[dict[str, Any]]:
        del tools_enabled
        system_prompt = (system_prompt_override or "").strip() or self.system_prompt
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for user_turn, assistant_turn in turns:
            messages.append({"role": "user", "content": user_turn})
            messages.append({"role": "assistant", "content": assistant_turn})
        messages.append({"role": "user", "content": user_text.strip()})
        return messages

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    text = str(block.get("text") or "").strip()
                    if text:
                        chunks.append(text)
            return "\n".join(chunks)
        return str(content or "")

    def _ensure_tokenizer(self):
        if self._tokenizer is not None:
            return self._tokenizer
        with self._tokenizer_lock:
            if self._tokenizer is None:
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_dir, trust_remote_code=True)
        return self._tokenizer

    def _input_token_count(self, messages: list[dict[str, Any]]) -> int | None:
        max_context = self.max_context_tokens()
        if max_context <= 0:
            return None
        try:
            tokenizer = self._ensure_tokenizer()
            kwargs: dict[str, Any] = {"tokenize": True, "add_generation_prompt": True}
            if not self.enable_thinking:
                kwargs["enable_thinking"] = False
            encoded = tokenizer.apply_chat_template(messages, **kwargs)
            input_ids = encoded.get("input_ids") if hasattr(encoded, "get") else None
            if input_ids is None and hasattr(encoded, "__getitem__"):
                input_ids = encoded["input_ids"]
            if isinstance(input_ids, list):
                return len(input_ids)
        except Exception:
            return None
        return None

    def _resolved_max_tokens(self, messages: list[dict[str, Any]]) -> int:
        max_context = self.max_context_tokens()
        if max_context <= 0:
            return self.max_new_tokens
        input_tokens = self._input_token_count(messages)
        if input_tokens is None:
            return self.max_new_tokens
        available = max_context - input_tokens - 32
        if available < 1:
            raise RuntimeError(
                f"Prompt is too large for the active vLLM context window ({input_tokens} input tokens vs max context {max_context}). Clear chat or reduce retrieved course context."
            )
        return min(self.max_new_tokens, available)

    def _ensure_remote_model(self) -> str:
        if self.remote_model:
            self._request_json("GET", "/models")
            return self.remote_model
        payload = self._request_json("GET", "/models")
        if not isinstance(payload, dict):
            raise RuntimeError("vLLM /models response was invalid.")
        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("vLLM /models response did not contain a model list.")
        for item in data:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if model_id:
                self.remote_model = model_id
                return self.remote_model
        raise RuntimeError("No served model was reported by the vLLM /models endpoint.")

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        raw_payload = None if payload is None else json.dumps(payload).encode("utf-8")
        request = UrlRequest(url, data=raw_payload, method=method.upper())
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Accept", "application/json")
        if raw_payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", "ignore")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")
            raise RuntimeError(f"vLLM {path} failed with HTTP {exc.code}: {detail[:240]}") from exc
        except URLError as exc:
            raise RuntimeError(f"vLLM {path} failed: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise RuntimeError(f"vLLM {path} returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"vLLM {path} returned an unexpected payload.")
        return parsed

    def _stream_chat_completion(self, messages: list[dict[str, Any]], *, on_visible: Optional[Callable[[str], None]] = None) -> str:
        self.stop_event.clear()
        payload: dict[str, Any] = {
            "model": self._ensure_remote_model(),
            "messages": messages,
            "stream": True,
            "max_tokens": self._resolved_max_tokens(messages),
            "temperature": max(self.temperature, 0.0),
            "top_p": max(min(self.top_p, 1.0), 0.0),
        }
        if not self.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if self.temperature <= 0:
            payload["temperature"] = 0.0
            payload["top_p"] = 1.0
        if self.top_k > 0:
            payload["top_k"] = self.top_k
        if self.repetition_penalty > 0:
            payload["repetition_penalty"] = self.repetition_penalty

        request = UrlRequest(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Accept", "text/event-stream")
        request.add_header("Content-Type", "application/json")

        sanitizer = StreamSanitizer()
        pieces: list[str] = []
        response: Any | None = None
        try:
            response = urlopen(request, timeout=self.timeout_seconds)
            with self._active_response_lock:
                self._active_response = response
            while True:
                if self.stop_event.is_set():
                    break
                raw_line = response.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", "ignore").strip()
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except Exception:
                    continue
                delta = self._extract_delta_text(payload)
                if not delta:
                    continue
                visible = sanitizer.feed(delta)
                if not visible:
                    continue
                pieces.append(visible)
                if on_visible is not None:
                    on_visible(visible)
            tail = sanitizer.flush()
            if tail:
                pieces.append(tail)
                if on_visible is not None:
                    on_visible(tail)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")
            raise RuntimeError(f"vLLM chat completion failed with HTTP {exc.code}: {detail[:240]}") from exc
        except URLError as exc:
            raise RuntimeError(f"vLLM chat completion failed: {exc}") from exc
        finally:
            with self._active_response_lock:
                self._active_response = None
            self.stop_event.clear()
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

        return clean_assistant_text("".join(pieces))

    @staticmethod
    def _extract_delta_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        delta = first.get("delta")
        if not isinstance(delta, dict):
            return ""
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            pieces: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    item_text = str(item.get("text") or "").strip()
                    if item_text:
                        pieces.append(item_text)
            return "".join(pieces)
        return ""

    def _generate_text(self, messages: list[dict[str, Any]], *, on_visible: Optional[Callable[[str], None]] = None) -> str:
        return self._stream_chat_completion(messages, on_visible=on_visible)
