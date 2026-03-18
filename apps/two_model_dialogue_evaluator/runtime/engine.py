from __future__ import annotations

import json
import os
import re
import threading
import sys
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any, Callable, Optional, Sequence

import torch
from accelerate import Accelerator
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    GenerationConfig,
    StoppingCriteria,
    StoppingCriteriaList,
    TextIteratorStreamer,
)

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from paths import get_runtime_config, get_runtime_config_path, get_system_prompt_default_path, get_tools_enabled_default
from runtime.events import EngineEvent
from runtime import tools as runtime_tools

DEFAULT_SYSTEM_PROMPT = "You are a precise and concise assistant."
MAX_TOOL_STEPS = 3

CHATML_TOKEN_RE = re.compile(r"<\|im_(?:start|end)\|>")
THINK_BLOCK_RE = re.compile(r"<tool_call>.*?</tool_call>", re.IGNORECASE | re.DOTALL)
THINK_TAG_RE = re.compile(r"</?think>", re.IGNORECASE)
MARKDOWN_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)+")
MARKDOWN_DECORATION_RE = re.compile(r"^(?:\*\*|__|`)+")
PROMPT_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")

META_PREFIXES = tuple(
    item.lower()
    for item in (
        "thinking process",
        "analysis",
        "analyze the request",
        "determine the response style",
        "determine the core concept",
        "determine the response type",
        "determine content",
        "draft the response",
        "drafting the response",
        "drafting content",
        "review against constraints",
        "check constraints",
        "constraint check",
        "final polish",
        "final decision",
        "final version",
        "plan:",
        "draft:",
        "target:",
        "role:",
        "operator:",
        "rules:",
        "constraints:",
        "protocol:",
        "mode:",
        "steps:",
        "output:",
        "user input:",
        "the user is asking",
        "best approach",
        "checking against protocol",
        "checking against constraints",
        "wait, looking",
        "wait, checking",
        "actually, upon reflection",
        "self-correction",
    )
)


@dataclass(frozen=True)
class RuntimeMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatTurnResult:
    assistant: str
    visible_messages: list[RuntimeMessage]


class _StopOnEvent(StoppingCriteria):
    def __init__(self, stop_event: threading.Event):
        super().__init__()
        self._stop_event = stop_event

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:  # type: ignore[override]
        return self._stop_event.is_set()


class ThinkStripper:
    open_tag = "<think>"
    close_tag = "</think>"

    def __init__(self) -> None:
        self._pending = ""
        self._inside_think = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._pending += chunk
        out: list[str] = []
        while self._pending:
            if self._inside_think:
                close_idx = self._pending.lower().find(self.close_tag)
                if close_idx >= 0:
                    self._pending = self._pending[close_idx + len(self.close_tag) :]
                    self._inside_think = False
                    continue
                keep = len(self.close_tag) - 1
                if len(self._pending) > keep:
                    self._pending = self._pending[-keep:]
                break
            open_idx = self._pending.lower().find(self.open_tag)
            close_idx = self._pending.lower().find(self.close_tag)
            if close_idx >= 0 and (open_idx < 0 or close_idx < open_idx):
                self._pending = self._pending[close_idx + len(self.close_tag) :]
                continue
            if open_idx >= 0:
                if open_idx > 0:
                    out.append(self._pending[:open_idx])
                self._pending = self._pending[open_idx + len(self.open_tag) :]
                self._inside_think = True
                continue
            keep = len(self.open_tag) - 1
            if len(self._pending) > keep:
                out.append(self._pending[:-keep])
                self._pending = self._pending[-keep:]
            break
        return "".join(out)

    def flush(self) -> str:
        if self._inside_think:
            self._inside_think = False
            self._pending = ""
            return ""
        tail = self._pending
        self._pending = ""
        return THINK_TAG_RE.sub("", tail)


class PreludeFilter:
    def __init__(self) -> None:
        self._pending = ""
        self._started = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._pending += chunk
        out: list[str] = []
        while self._pending:
            if self._started:
                out.append(self._pending)
                self._pending = ""
                break
            newline_idx = self._pending.find("\n")
            if newline_idx < 0:
                probe = _normalize_meta_probe(self._pending)
                if not probe:
                    self._pending = ""
                    break
                if _looks_like_meta(probe):
                    break
                if len(self._pending) < 96 and not re.search(r"[.!?]\s*$", self._pending):
                    break
                self._started = True
                out.append(self._pending)
                self._pending = ""
                break
            line = self._pending[: newline_idx + 1]
            self._pending = self._pending[newline_idx + 1 :]
            probe = _normalize_meta_probe(line)
            if not probe:
                continue
            if _looks_like_meta(probe):
                continue
            self._started = True
            out.append(line)
        return "".join(out)

    def flush(self) -> str:
        if self._started:
            tail = self._pending
            self._pending = ""
            return tail
        probe = _normalize_meta_probe(self._pending)
        tail = "" if (not probe or _looks_like_meta(probe)) else self._pending
        self._pending = ""
        return tail


class StreamSanitizer:
    def __init__(self) -> None:
        self._think = ThinkStripper()
        self._prelude = PreludeFilter()

    def feed(self, chunk: str) -> str:
        return self._prelude.feed(self._think.feed(chunk))

    def flush(self) -> str:
        return self._prelude.feed(self._think.flush()) + self._prelude.flush()


def _normalize_meta_probe(text: str) -> str:
    probe = CHATML_TOKEN_RE.sub("", text or "")
    probe = THINK_BLOCK_RE.sub("", probe)
    probe = THINK_TAG_RE.sub("", probe).strip()
    if not probe:
        return ""
    probe = MARKDOWN_PREFIX_RE.sub("", probe)
    probe = MARKDOWN_DECORATION_RE.sub("", probe).strip()
    probe = probe.replace("*", " ").replace("_", " ")
    probe = re.sub(r"\s+", " ", probe)
    return probe.strip().lower()


def _looks_like_meta(probe: str) -> bool:
    return any(probe.startswith(prefix) for prefix in META_PREFIXES)


def _load_system_prompt() -> tuple[str, str, str]:
    path = get_system_prompt_default_path()
    prompt_format = "text"
    try:
        text = path.read_text(encoding="utf-8-sig").strip()
        return (text or DEFAULT_SYSTEM_PROMPT), str(path), prompt_format
    except FileNotFoundError:
        return DEFAULT_SYSTEM_PROMPT, str(path), "default"
    except Exception:
        return DEFAULT_SYSTEM_PROMPT, str(path), "default"


def clean_assistant_text(text: str) -> str:
    sanitizer = StreamSanitizer()
    visible = sanitizer.feed(text or "") + sanitizer.flush()
    visible = CHATML_TOKEN_RE.sub("", visible)
    visible = THINK_BLOCK_RE.sub("", visible)
    visible = THINK_TAG_RE.sub("", visible).strip()
    visible = re.sub(r"\n{3,}", "\n\n", visible)
    return visible


def sanitize_user_text(text: str) -> str:
    cleaned = PROMPT_IMAGE_RE.sub("", text or "")
    lines: list[str] = []
    for raw in cleaned.splitlines():
        if raw.strip().lower().startswith("[attached image"):
            continue
        lines.append(raw)
    return ("\n".join(lines).strip() or "Image attached.")


def _max_context_tokens_from_config(cfg: Any) -> int:
    direct = getattr(cfg, "max_position_embeddings", None)
    if isinstance(direct, int) and direct > 0:
        return int(direct)
    text_cfg = getattr(cfg, "text_config", None)
    nested = getattr(text_cfg, "max_position_embeddings", None) if text_cfg is not None else None
    if isinstance(nested, int) and nested > 0:
        return int(nested)
    if isinstance(cfg, dict):
        nested_cfg = cfg.get("text_config") if isinstance(cfg.get("text_config"), dict) else None
        direct_dict = cfg.get("max_position_embeddings")
        nested_dict = nested_cfg.get("max_position_embeddings") if nested_cfg else None
        if isinstance(direct_dict, int) and direct_dict > 0:
            return int(direct_dict)
        if isinstance(nested_dict, int) and nested_dict > 0:
            return int(nested_dict)
    return 0


class LocalModelRuntime:
    def __init__(
        self,
        *,
        model_dir: Optional[Path | str] = None,
        tools_enabled: Optional[bool] = None,
        generation_overrides: Optional[dict[str, Any]] = None,
    ):
        self.accelerator = Accelerator()
        self.device = self.accelerator.device
        if model_dir is None:
            raise ValueError("A model directory is required for the standalone evaluator runtime.")
        self.model_dir = Path(model_dir).expanduser().resolve()
        if not self.model_dir.is_dir():
            raise FileNotFoundError(f"Model directory not found: {self.model_dir}")

        self.model_label = self.model_dir.name
        self.tools_enabled = get_tools_enabled_default() if tools_enabled is None else bool(tools_enabled)
        self.system_prompt, self.system_prompt_path, self.system_prompt_format = _load_system_prompt()
        self.stop_event = threading.Event()
        self.gui_config = get_runtime_config()
        if generation_overrides:
            self.gui_config.update({key: value for key, value in generation_overrides.items() if value is not None})
        self.gui_config_path = get_runtime_config_path()
        self.temperature = float(self.gui_config["temperature"])
        self.max_new_tokens = int(self.gui_config["max_new_tokens"])
        self.top_p = float(self.gui_config["top_p"])
        self.top_k = int(self.gui_config["top_k"])
        self.repetition_penalty = float(self.gui_config["repetition_penalty"])

        self._cfg = AutoConfig.from_pretrained(str(self.model_dir), trust_remote_code=False)
        self.supports_vision = bool(getattr(self._cfg, "vision_config", None))
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), trust_remote_code=False)
        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token_id is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.processor: Any | None = None
        self.image_support_error = ""
        self.model = self._load_model()
        self.model.eval()

    def runtime_config(self) -> dict[str, Any]:
        return {
            "model_dir": str(self.model_dir),
            "model_label": self.model_label,
            "device": str(self.device),
            "dtype": "float16",
            "temperature": self.temperature,
            "max_new_tokens": self.max_new_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "tools_enabled": self.tools_enabled,
            "supports_vision": self.supports_vision,
            "image_processor_loaded": self.processor is not None,
            "image_support_error": self.image_support_error,
            "sampling_enabled": self.temperature > 0.0,
            "max_context_tokens": self.max_context_tokens(),
            "gui_config_path": str(self.gui_config_path),
            "system_prompt_path": self.system_prompt_path,
            "system_prompt_format": self.system_prompt_format,
        }

    def warm_start(self) -> None:
        return None

    def cancel(self) -> None:
        self.stop_event.set()

    def max_context_tokens(self) -> int:
        return _max_context_tokens_from_config(self._cfg)

    def estimate_turn_tokens(
        self,
        *,
        prompt: str,
        history: Sequence[RuntimeMessage | dict[str, Any]],
        image_paths: Optional[Sequence[str]] = None,
        tools_enabled: bool = False,
        system_prompt_override: str | None = None,
    ) -> dict[str, Any]:
        user_text = (prompt or "").strip()
        if not user_text and not image_paths:
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
            image_paths=image_paths,
            tools_enabled=tools_enabled,
            system_prompt_override=system_prompt_override,
        )
        input_tokens = self._count_message_tokens(messages)
        max_context = self.max_context_tokens()
        remaining = max(max_context - input_tokens, 0) if max_context > 0 else None
        remaining_after_output_cap = (
            max(max_context - input_tokens - self.max_new_tokens, 0) if max_context > 0 else None
        )
        usage_ratio = (float(input_tokens) / float(max_context)) if max_context > 0 else None
        return {
            "available": True,
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

        turns = self._history_to_turns(history)

        def emit_assistant(text: str) -> None:
            if not text:
                return
            if on_event is not None:
                on_event(EngineEvent(type="assistant_delta", text=text, role="assistant"))
            if on_delta is not None:
                on_delta(text)

        if self.tools_enabled and not image_paths:
            direct_call = runtime_tools.infer_direct_calculator_call(user_text)
            if direct_call is not None:
                return self._run_direct_tool_turn(direct_call, "runtime", emit_assistant, on_delta, on_event)

            embedded_call = runtime_tools.infer_embedded_calculator_call(user_text)
            if embedded_call is not None:
                return self._run_tool_turn(turns, user_text, embedded_call, "runtime", emit_assistant, on_delta, on_event)

            if runtime_tools.is_tool_candidate(user_text):
                probe_messages = self._build_messages(
                    turns,
                    user_text,
                    tools_enabled=True,
                    system_prompt_override=system_prompt_override,
                )
                hidden = self._generate_text(probe_messages)
                tool_call = runtime_tools.extract_tool_call(hidden)
                if tool_call is not None:
                    return self._run_tool_turn(
                        turns,
                        user_text,
                        tool_call,
                        "model",
                        emit_assistant,
                        on_delta,
                        on_event,
                        system_prompt_override=system_prompt_override,
                    )
                if hidden:
                    emit_assistant(hidden)
                    return ChatTurnResult(assistant=hidden, visible_messages=[RuntimeMessage("assistant", hidden)])

        messages = self._build_messages(
            turns,
            user_text,
            image_paths=image_paths,
            tools_enabled=False,
            system_prompt_override=system_prompt_override,
        )
        assistant = self._generate_text(messages, on_visible=emit_assistant)
        return ChatTurnResult(assistant=assistant, visible_messages=[RuntimeMessage("assistant", assistant)])

    def _load_model(self) -> Any:
        model_loader = AutoModelForCausalLM
        if self.supports_vision:
            try:
                from transformers import AutoModelForImageTextToText, AutoProcessor

                self.processor = AutoProcessor.from_pretrained(str(self.model_dir), trust_remote_code=False)
                model_loader = AutoModelForImageTextToText
            except Exception as exc:
                self.image_support_error = str(exc)
                self.processor = None

        try:
            model = model_loader.from_pretrained(
                str(self.model_dir),
                dtype=torch.float16,
                low_cpu_mem_usage=True,
            ).to(self.device)
        except Exception as exc:
            if model_loader is AutoModelForCausalLM:
                raise
            self.image_support_error = f"{self.image_support_error}; vision fallback: {exc}".strip("; ")
            self.processor = None
            model = AutoModelForCausalLM.from_pretrained(
                str(self.model_dir),
                dtype=torch.float16,
                low_cpu_mem_usage=True,
            ).to(self.device)
        return model

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
        image_paths: Optional[Sequence[str]] = None,
        tools_enabled: bool = False,
        system_prompt_override: str | None = None,
    ) -> list[dict[str, Any]]:
        base_system_prompt = (system_prompt_override or "").strip() or self.system_prompt
        system_prompt = runtime_tools.append_tool_protocol(base_system_prompt) if tools_enabled else base_system_prompt
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for user_turn, assistant_turn in turns:
            messages.append({"role": "user", "content": user_turn})
            messages.append({"role": "assistant", "content": assistant_turn})
        if image_paths:
            blocks = [{"type": "image", "image": str(path)} for path in image_paths]
            blocks.append({"type": "text", "text": user_text.strip() or "Describe this image."})
            messages.append({"role": "user", "content": blocks})
        else:
            messages.append({"role": "user", "content": user_text.strip()})
        return messages

    def _messages_have_images(self, messages: Sequence[dict[str, Any]]) -> bool:
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "image":
                    return True
        return False

    def _normalize_mm_messages(self, messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for msg in messages:
            role = str(msg.get("role") or "user")
            content = msg.get("content")
            if isinstance(content, list):
                blocks: list[dict[str, Any]] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    kind = str(block.get("type") or "")
                    if kind == "text":
                        blocks.append({"type": "text", "text": str(block.get("text") or "")})
                    elif kind == "image":
                        blocks.append({"type": "image", "image": block.get("image")})
                normalized.append({"role": role, "content": blocks})
                continue
            normalized.append({"role": role, "content": [{"type": "text", "text": str(content or "")}]})
        return normalized

    def _prepare_inputs(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if not self._messages_have_images(messages):
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            inputs = self.tokenizer(prompt, return_tensors="pt")
            return {name: value.to(self.device) if isinstance(value, torch.Tensor) else value for name, value in inputs.items()}

        if self.processor is None:
            text_only: list[dict[str, str]] = []
            for msg in messages:
                content = msg.get("content")
                if not isinstance(content, list):
                    text_only.append({"role": str(msg.get("role") or "user"), "content": str(content or "")})
                    continue
                text = "\n".join(
                    str(block.get("text") or "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
                text_only.append({"role": str(msg.get("role") or "user"), "content": text})
            prompt = self.tokenizer.apply_chat_template(
                text_only,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            inputs = self.tokenizer(prompt, return_tensors="pt")
            return {name: value.to(self.device) if isinstance(value, torch.Tensor) else value for name, value in inputs.items()}

        mm_messages = self._normalize_mm_messages(messages)
        kwargs: dict[str, Any] = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_dict": True,
            "return_tensors": "pt",
            "enable_thinking": False,
        }
        try:
            inputs = self.processor.apply_chat_template(mm_messages, **kwargs)
        except TypeError:
            kwargs.pop("enable_thinking", None)
            kwargs["chat_template_kwargs"] = {"enable_thinking": False}
            inputs = self.processor.apply_chat_template(mm_messages, **kwargs)
        return {name: value.to(self.device) if isinstance(value, torch.Tensor) else value for name, value in inputs.items()}

    def _count_message_tokens(self, messages: list[dict[str, Any]]) -> int:
        if not self._messages_have_images(messages):
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            encoded = self.tokenizer(prompt, add_special_tokens=False, return_attention_mask=False)
            input_ids = encoded.get("input_ids") or []
            return len(input_ids)
        inputs = self._prepare_inputs(messages)
        input_ids = inputs.get("input_ids")
        if isinstance(input_ids, torch.Tensor):
            return int(input_ids.shape[-1])
        if isinstance(input_ids, list):
            if input_ids and isinstance(input_ids[0], list):
                return len(input_ids[0])
            return len(input_ids)
        return 0

    def _generation_config(self) -> GenerationConfig:
        if self.temperature <= 0:
            return GenerationConfig(
                max_new_tokens=self.max_new_tokens,
                top_p=1.0,
                top_k=0,
                do_sample=False,
                repetition_penalty=self.repetition_penalty,
                eos_token_id=self._eos_token_ids(),
                pad_token_id=self.tokenizer.pad_token_id,
            )
        return GenerationConfig(
            temperature=self.temperature,
            max_new_tokens=self.max_new_tokens,
            top_p=self.top_p,
            top_k=self.top_k,
            do_sample=True,
            repetition_penalty=self.repetition_penalty,
            eos_token_id=self._eos_token_ids(),
            pad_token_id=self.tokenizer.pad_token_id,
        )

    def _eos_token_ids(self) -> Optional[list[int] | int]:
        eos_ids: list[int] = []
        if self.tokenizer.eos_token_id is not None:
            eos_ids.append(int(self.tokenizer.eos_token_id))
        try:
            im_end_id = self.tokenizer.convert_tokens_to_ids("<|im_end|>")
            unk_id = getattr(self.tokenizer, "unk_token_id", None)
            if im_end_id is not None and im_end_id >= 0 and im_end_id not in eos_ids and (unk_id is None or im_end_id != unk_id):
                eos_ids.append(int(im_end_id))
        except Exception:
            pass
        if not eos_ids:
            return None
        return eos_ids[0] if len(eos_ids) == 1 else eos_ids

    def _stream_generate(self, messages: list[dict[str, Any]], callback: Callable[[str], None]) -> None:
        inputs = self._prepare_inputs(messages)
        streamer = TextIteratorStreamer(self.tokenizer, skip_special_tokens=True, skip_prompt=True, timeout=300.0)
        stopping = StoppingCriteriaList([_StopOnEvent(self.stop_event)])

        def generate() -> None:
            with torch.no_grad(), self.accelerator.autocast():
                self.model.generate(
                    **inputs,
                    generation_config=self._generation_config(),
                    streamer=streamer,
                    stopping_criteria=stopping,
                )

        thread = threading.Thread(target=generate, daemon=True)
        thread.start()
        try:
            for chunk in streamer:
                if chunk:
                    callback(chunk)
        except Empty:
            pass
        finally:
            self.stop_event.clear()

    def _generate_text(self, messages: list[dict[str, Any]], *, on_visible: Optional[Callable[[str], None]] = None) -> str:
        sanitizer = StreamSanitizer()
        pieces: list[str] = []

        def handle_chunk(chunk: str) -> None:
            visible = sanitizer.feed(chunk)
            if not visible:
                return
            pieces.append(visible)
            if on_visible is not None:
                on_visible(visible)

        self._stream_generate(messages, handle_chunk)
        tail = sanitizer.flush()
        if tail:
            pieces.append(tail)
            if on_visible is not None:
                on_visible(tail)
        return clean_assistant_text("".join(pieces))

    def _emit_tool_request(
        self,
        call: runtime_tools.ToolCall,
        provenance: str,
        on_delta: Optional[Callable[[str], None]],
        on_event: Optional[Callable[[EngineEvent], None]],
    ) -> str:
        request_text = runtime_tools.format_tool_request(call, provenance=provenance)
        if on_event is not None:
            on_event(
                EngineEvent(
                    type="tool_request",
                    text=request_text,
                    role="system",
                    tool=call.tool,
                    language="json",
                    provenance=provenance,
                )
            )
        if on_delta is not None:
            on_delta(request_text + "\n\n")
        return request_text

    def _emit_tool_result(
        self,
        result: runtime_tools.ToolResult,
        provenance: str,
        on_delta: Optional[Callable[[str], None]],
        on_event: Optional[Callable[[EngineEvent], None]],
    ) -> str:
        result_text = runtime_tools.format_tool_result(result)
        if on_event is not None:
            on_event(
                EngineEvent(
                    type="tool_result",
                    text=result_text,
                    role="system",
                    tool=result.tool,
                    language="text",
                    provenance=provenance,
                    ok=result.ok,
                    result_text=result.result_text,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration_ms=result.duration_ms,
                )
            )
        if on_delta is not None:
            on_delta(result_text + "\n\n")
        return result_text

    def _run_tool_turn(
        self,
        turns: Sequence[tuple[str, str]],
        user_text: str,
        call: runtime_tools.ToolCall,
        call_provenance: str,
        emit_assistant: Callable[[str], None],
        on_delta: Optional[Callable[[str], None]],
        on_event: Optional[Callable[[EngineEvent], None]],
        system_prompt_override: str | None = None,
    ) -> ChatTurnResult:
        visible_messages: list[RuntimeMessage] = []
        followup = self._build_messages(
            turns,
            user_text,
            tools_enabled=True,
            system_prompt_override=system_prompt_override,
        )
        current_call = call
        current_provenance = call_provenance

        for _ in range(MAX_TOOL_STEPS):
            request_text = self._emit_tool_request(current_call, current_provenance, on_delta, on_event)
            visible_messages.append(RuntimeMessage("system", request_text))

            result = runtime_tools.execute_tool(current_call, cwd=self.model_dir.parent)
            result_text = self._emit_tool_result(result, current_provenance, on_delta, on_event)
            visible_messages.append(RuntimeMessage("system", result_text))

            followup.append({"role": "assistant", "content": current_call.raw})
            followup.append({"role": "user", "content": runtime_tools.build_tool_followup_message(result)})

            hidden = self._generate_text(followup)
            next_call = runtime_tools.extract_tool_call(hidden)
            if next_call is None:
                assistant = hidden or self._direct_tool_answer(result)
                emit_assistant(assistant)
                visible_messages.append(RuntimeMessage("assistant", assistant))
                return ChatTurnResult(assistant=assistant, visible_messages=visible_messages)
            current_call = next_call
            current_provenance = "model"

        final_instruction = (
            "You have already used the tool enough times for this turn. "
            "Answer directly from the tool results now without another tool call."
        )
        followup.append({"role": "user", "content": final_instruction})
        assistant = self._generate_text(followup, on_visible=emit_assistant)
        visible_messages.append(RuntimeMessage("assistant", assistant))
        return ChatTurnResult(assistant=assistant, visible_messages=visible_messages)

    def _run_direct_tool_turn(
        self,
        call: runtime_tools.ToolCall,
        provenance: str,
        emit_assistant: Callable[[str], None],
        on_delta: Optional[Callable[[str], None]],
        on_event: Optional[Callable[[EngineEvent], None]],
    ) -> ChatTurnResult:
        request_text = self._emit_tool_request(call, provenance, on_delta, on_event)
        result = runtime_tools.execute_tool(call, cwd=self.model_dir.parent)
        result_text = self._emit_tool_result(result, provenance, on_delta, on_event)
        assistant = self._direct_tool_answer(result)
        emit_assistant(assistant)
        return ChatTurnResult(
            assistant=assistant,
            visible_messages=[
                RuntimeMessage("system", request_text),
                RuntimeMessage("system", result_text),
                RuntimeMessage("assistant", assistant),
            ],
        )

    @staticmethod
    def _direct_tool_answer(result: runtime_tools.ToolResult) -> str:
        if result.result_text:
            return result.result_text
        if result.stdout:
            return result.stdout.strip()
        if result.stderr:
            return f"Tool error: {result.stderr.strip()}"
        return "Tool completed with no output."
