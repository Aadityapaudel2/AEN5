#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import wrap
from qt_render import render_transcript_html

ROOT = Path(__file__).resolve().parent
PORTAL_DIR = ROOT / "portal"
TEMPLATES_DIR = PORTAL_DIR / "templates"
STATIC_DIR = PORTAL_DIR / "static"

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class PortalConfig:
    host: str
    port: int
    path_prefix: str
    load_model: bool

    @staticmethod
    def load() -> "PortalConfig":
        raw_prefix = os.getenv("ATHENA_PORTAL_PATH_PREFIX", "/AthenaV5").strip() or "/AthenaV5"
        path_prefix = raw_prefix if raw_prefix.startswith("/") else f"/{raw_prefix}"
        path_prefix = path_prefix.rstrip("/") or "/AthenaV5"
        return PortalConfig(
            host=os.getenv("ATHENA_PORTAL_HOST", "0.0.0.0"),
            port=int(os.getenv("ATHENA_PORTAL_PORT") or os.getenv("PORT") or "8000"),
            path_prefix=path_prefix,
            load_model=_env_bool("ATHENA_WEB_LOAD_MODEL", False),
        )


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=20000)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    history: list[ChatMessage] = Field(default_factory=list)
    enable_thinking: bool = False
    show_thoughts: bool = False


class ChatResponse(BaseModel):
    assistant: str
    history: list[ChatMessage]
    transcript_html: str
    smoke_mode: bool
    model_loaded: bool


class ChatEngine:
    def __init__(self, cfg: PortalConfig):
        self._cfg = cfg
        self._lock = Lock()
        self._streamer: Any | None = None
        self._model_load_error: str = ""
        self._system_prompt = wrap.load_system_prompt()

    @property
    def smoke_mode(self) -> bool:
        return not self._cfg.load_model

    @property
    def model_loaded(self) -> bool:
        return self._streamer is not None

    @property
    def model_load_error(self) -> str:
        return self._model_load_error

    def _ensure_loaded(self) -> None:
        if self._streamer is not None:
            return
        try:
            # Import heavy local-model stack lazily so smoke mode can run with
            # lightweight web dependencies (useful for Render/hosted deploys).
            from tk_chat import CONFIG_PATH, GuiSettings, LocalStreamer

            settings = GuiSettings.load(CONFIG_PATH)
            self._streamer = LocalStreamer(settings)
        except Exception as exc:
            self._model_load_error = str(exc)
            raise

    def _history_to_turns(self, history: list[ChatMessage]) -> list[tuple[str, str]]:
        turns: list[tuple[str, str]] = []
        pending_user: str | None = None
        for msg in history[-24:]:
            role = msg.role
            content = msg.content.strip()
            if not content:
                continue
            if role == "user":
                pending_user = content
                continue
            if role == "assistant" and pending_user is not None:
                turns.append((pending_user, content))
                pending_user = None
        return turns[-12:]

    def reply(
        self,
        prompt: str,
        history: list[ChatMessage],
        enable_thinking: bool,
        show_thoughts: bool,
    ) -> str:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            return "Please enter a prompt."
        if self.smoke_mode:
            return (
                "Smoke mode is active. Portal routing and UI are live, but model loading is disabled. "
                "Set ATHENA_WEB_LOAD_MODEL=1 to enable live inference."
            )

        with self._lock:
            self._ensure_loaded()
            assert self._streamer is not None  # for type checkers

            turns = self._history_to_turns(history)
            wrapped_prompt = wrap.build_prompt(
                self._streamer.tokenizer,
                turns,
                clean_prompt,
                system_prompt=self._system_prompt,
                max_turns=6,
                enable_thinking=enable_thinking,
            )
            think_stripper = wrap.ThinkStripper(enabled=not show_thoughts)
            chunks: list[str] = []

            def on_chunk(chunk: str) -> None:
                visible = think_stripper.feed(chunk)
                if visible:
                    chunks.append(visible)

            self._streamer.stream(wrapped_prompt, on_chunk)
            tail = think_stripper.flush()
            if tail:
                chunks.append(tail)
            return wrap.clean_assistant_text("".join(chunks))


def _build_initial_system_messages(cfg: PortalConfig, engine: ChatEngine) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                f"Athena V5 portal online at {cfg.path_prefix}. "
                f"Smoke mode={'on' if engine.smoke_mode else 'off'}."
            ),
        }
    ]


cfg = PortalConfig.load()
engine = ChatEngine(cfg)

app = FastAPI(title="Athena V5 Portal", version="1.0.0")
app.mount(f"{cfg.path_prefix}/static", StaticFiles(directory=str(STATIC_DIR)), name="portal-static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "path_prefix": cfg.path_prefix,
        "smoke_mode": engine.smoke_mode,
        "model_loaded": engine.model_loaded,
    }


@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url=cfg.path_prefix)


@app.get(cfg.path_prefix, response_class=HTMLResponse)
def portal_index(request: Request) -> HTMLResponse:
    initial_transcript_html = render_transcript_html(_build_initial_system_messages(cfg, engine))
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "path_prefix": cfg.path_prefix,
            "title": "Athena V5 Portal",
            "initial_transcript_html": initial_transcript_html,
        },
    )


@app.get(f"{cfg.path_prefix}/api/config")
def api_config() -> dict[str, Any]:
    return {
        "path_prefix": cfg.path_prefix,
        "smoke_mode": engine.smoke_mode,
        "model_loaded": engine.model_loaded,
        "model_load_error": engine.model_load_error,
    }


@app.post(f"{cfg.path_prefix}/api/chat", response_model=ChatResponse)
def api_chat(payload: ChatRequest) -> ChatResponse:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is empty.")

    assistant = engine.reply(
        prompt=prompt,
        history=payload.history,
        enable_thinking=payload.enable_thinking,
        show_thoughts=payload.show_thoughts,
    )
    next_history = list(payload.history)
    next_history.append(ChatMessage(role="user", content=prompt))
    next_history.append(ChatMessage(role="assistant", content=assistant))
    transcript_html = render_transcript_html([item.model_dump() for item in next_history])

    return ChatResponse(
        assistant=assistant,
        history=next_history,
        transcript_html=transcript_html,
        smoke_mode=engine.smoke_mode,
        model_loaded=engine.model_loaded,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("portal_server:app", host=cfg.host, port=cfg.port, reload=False)
