#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
from contextlib import asynccontextmanager
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

BOOTSTRAP_ROOT = Path(__file__).resolve().parent.parent
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from athena_paths import (
    get_auth_required,
    get_browser_root,
    get_log_root,
    get_path_prefix,
    get_portal_host,
    get_portal_port,
    get_portal_static_dir,
    get_portal_templates_dir,
    get_tools_enabled_default,
)
from browser.render import render_transcript_html
from desktop_engine import DesktopEngine, EngineEvent

try:
    from authlib.integrations.starlette_client import OAuth
except Exception:  # pragma: no cover
    OAuth = None  # type: ignore[assignment]

ROOT = get_browser_root()
PROJECT_ROOT = BOOTSTRAP_ROOT
TEMPLATES_DIR = get_portal_templates_dir()
STATIC_DIR = get_portal_static_dir()
DEFAULT_REDIRECT_URI = "https://portal.neohmlabs.com/AthenaV5/auth/callback"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _asset_version() -> str:
    try:
        js_mtime = (STATIC_DIR / "portal.js").stat().st_mtime_ns
        css_mtime = (STATIC_DIR / "portal.css").stat().st_mtime_ns
        return str(max(js_mtime, css_mtime))
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _normalize_user_key(email: str) -> str:
    safe = re.sub(r"[^a-z0-9._@-]+", "_", (email or "anonymous").lower())
    return safe.strip("_") or "anonymous"


def _client_meta(request: Request) -> dict[str, str]:
    return {
        "client_ip": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", ""),
    }


@dataclass(frozen=True)
class PortalConfig:
    mode: str
    host: str
    port: int
    path_prefix: str
    load_model: bool
    auth_required: bool
    tools_enabled: bool
    cookie_secure: bool
    google_client_id: str
    google_client_secret: str
    auth_redirect_uri: str
    session_secret: str
    log_root: Path

    @staticmethod
    def load() -> "PortalConfig":
        mode = (os.getenv("ATHENA_PORTAL_MODE") or "dev").strip().lower()
        if mode == "local":
            mode = "dev"
        if mode not in {"dev", "prod"}:
            mode = "dev"
        return PortalConfig(
            mode=mode,
            host=get_portal_host(mode),
            port=get_portal_port(),
            path_prefix=get_path_prefix(),
            load_model=_env_bool("ATHENA_WEB_LOAD_MODEL", True),
            auth_required=get_auth_required(mode),
            tools_enabled=_env_bool("ATHENA_TOOLS_ENABLED", get_tools_enabled_default()),
            cookie_secure=_env_bool("ATHENA_PORTAL_COOKIE_SECURE", mode == "prod"),
            google_client_id=(os.getenv("ATHENA_GOOGLE_CLIENT_ID") or "").strip(),
            google_client_secret=(os.getenv("ATHENA_GOOGLE_CLIENT_SECRET") or "").strip(),
            auth_redirect_uri=(os.getenv("ATHENA_AUTH_REDIRECT_URI") or DEFAULT_REDIRECT_URI).strip(),
            session_secret=(os.getenv("ATHENA_PORTAL_SESSION_SECRET") or "athena-browser-dev-session").strip(),
            log_root=get_log_root(),
        )


@dataclass(frozen=True)
class PreparedChatRequest:
    request_id: str
    user_email: str
    user_display_name: str
    prompt: str
    history: list[ChatMessage]
    meta: dict[str, str]
    model_image_paths: list[str]
    image_urls: list[str]
    user_content: str
    started_at: float


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=50000)


class ChatImage(BaseModel):
    name: str = Field(default="image.png", max_length=256)
    content_type: str = Field(default="image/png", max_length=128)
    data_url: str = Field(min_length=1, max_length=12_000_000)


class ChatRequest(BaseModel):
    prompt: str = Field(default="", max_length=12000)
    history: list[ChatMessage] = Field(default_factory=list)
    images: list[ChatImage] = Field(default_factory=list)


class UserLogStore:
    def __init__(self, root: Path):
        self.root = root
        self._lock = Lock()

    def user_key(self, email: str) -> str:
        return _normalize_user_key(email)

    def _session_file(self, email: str) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.root / self.user_key(email) / "sessions" / f"{day}.ndjson"

    def _error_file(self, email: str) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.root / self.user_key(email) / "errors" / f"{day}.ndjson"

    def ensure_profile(self, user: dict[str, Any]) -> None:
        email = str(user.get("email") or "anonymous@dev")
        user_dir = self.root / self.user_key(email)
        (user_dir / "sessions").mkdir(parents=True, exist_ok=True)
        (user_dir / "errors").mkdir(parents=True, exist_ok=True)
        profile_path = user_dir / "profile.json"
        if profile_path.exists():
            return
        profile = {
            "email": user.get("email"),
            "name": user.get("name"),
            "picture": user.get("picture"),
            "sub": user.get("sub"),
            "created_at_utc": _utc_now_iso(),
        }
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def log_event(self, user_email: str, event: dict[str, Any], *, error_log: bool = False) -> None:
        with self._lock:
            target = self._error_file(user_email) if error_log else self._session_file(user_email)
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = dict(event)
            payload.setdefault("ts_utc", _utc_now_iso())
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


cfg = PortalConfig.load()
logs = UserLogStore(cfg.log_root)
engine = DesktopEngine(tools_enabled=cfg.tools_enabled, load_model=cfg.load_model)
oauth: Any | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    global oauth
    cfg.log_root.mkdir(parents=True, exist_ok=True)
    if cfg.auth_required:
        missing = []
        if not cfg.google_client_id:
            missing.append("ATHENA_GOOGLE_CLIENT_ID")
        if not cfg.google_client_secret:
            missing.append("ATHENA_GOOGLE_CLIENT_SECRET")
        if not cfg.auth_redirect_uri:
            missing.append("ATHENA_AUTH_REDIRECT_URI")
        if not cfg.session_secret:
            missing.append("ATHENA_PORTAL_SESSION_SECRET")
        if missing:
            raise RuntimeError(f"Missing required auth env vars: {', '.join(missing)}")
        if OAuth is None:
            raise RuntimeError("Auth is required, but authlib is not installed.")
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=cfg.google_client_id,
            client_secret=cfg.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    if cfg.load_model:
        engine.warm_start()
    print(
        "[portal-startup] "
        f"mode={cfg.mode} auth_required={cfg.auth_required} tools_enabled={cfg.tools_enabled} "
        f"path_prefix={cfg.path_prefix} log_root={cfg.log_root} model_dir={engine.runtime_snapshot().get('model_dir')} "
        f"model_warmed={engine.runtime_snapshot().get('model_loaded')}"
    )
    yield


app = FastAPI(title="Athena V5 Browser", version="4.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=cfg.session_secret,
    same_site="lax",
    https_only=cfg.cookie_secure,
    session_cookie="athena_portal_session",
)
app.mount(f"{cfg.path_prefix}/static", StaticFiles(directory=str(STATIC_DIR)), name="portal-static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _session_user(request: Request) -> dict[str, Any] | None:
    try:
        raw = request.session.get("user")
    except AssertionError:
        return None
    return raw if isinstance(raw, dict) else None


def _user_display_name(user: dict[str, Any] | None) -> str:
    raw = (user or {}).get("name") or (user or {}).get("email") or "User"
    return str(raw).strip() or "User"


def _decode_data_url_image(data_url: str) -> tuple[bytes, str]:
    match = re.match(r"^data:([a-zA-Z0-9.+/-]+);base64,(.+)$", data_url.strip(), re.DOTALL)
    if not match:
        raise ValueError("Invalid image data URL.")
    mime = match.group(1).strip().lower()
    payload = re.sub(r"\s+", "", match.group(2))
    try:
        blob = base64.b64decode(payload, validate=True)
    except binascii.Error as exc:
        raise ValueError("Invalid base64 image payload.") from exc
    if not blob:
        raise ValueError("Empty image payload.")
    return blob, mime


def _image_ext_from_mime(mime: str, fallback_name: str) -> str:
    ext = mimetypes.guess_extension(mime) or ""
    if not ext and "." in fallback_name:
        ext = "." + fallback_name.rsplit(".", 1)[-1].lower()
    return ext or ".png"


def _persist_request_images(payload_images: list[ChatImage], *, user_email: str, request_id: str) -> tuple[list[str], list[str]]:
    if not payload_images:
        return [], []
    user_key = logs.user_key(user_email)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    image_dir = cfg.log_root / user_key / "uploads" / day
    image_dir.mkdir(parents=True, exist_ok=True)
    model_paths: list[str] = []
    portal_urls: list[str] = []
    for idx, item in enumerate(payload_images, start=1):
        blob, mime = _decode_data_url_image(item.data_url)
        if len(blob) > 8 * 1024 * 1024:
            raise ValueError("Image exceeds 8MB limit.")
        if not mime.startswith("image/"):
            raise ValueError("Only image uploads are supported.")
        ext = _image_ext_from_mime(mime, item.name or "")
        fname = f"{request_id}_{idx:02d}{ext}"
        out_path = image_dir / fname
        out_path.write_bytes(blob)
        model_paths.append(str(out_path))
        rel = out_path.relative_to(cfg.log_root).as_posix()
        portal_urls.append(f"{cfg.path_prefix}/api/uploads/{rel}")
    return model_paths, portal_urls


def _format_user_message_content(prompt: str, image_urls: list[str]) -> str:
    clean_prompt = prompt.strip()
    parts: list[str] = []
    if clean_prompt:
        parts.append(clean_prompt)
    if image_urls:
        marker = f"[attached image {len(image_urls)}]" if len(image_urls) == 1 else f"[attached images: {len(image_urls)}]"
        parts.append(marker)
        for idx, url in enumerate(image_urls, start=1):
            parts.append(f"![attached image {idx}]({url})")
    return "\n\n".join(parts) if parts else "Image attached."


def _initial_messages() -> list[dict[str, str]]:
    return [{"role": "system", "content": "Welcome to the browser adapter."}]


def _require_auth(request: Request) -> None:
    if cfg.auth_required and _session_user(request) is None:
        raise HTTPException(status_code=401, detail="Authentication required.")


def _prepare_chat_request(payload: ChatRequest, request: Request) -> PreparedChatRequest:
    prompt = payload.prompt.strip()
    if not prompt and not payload.images:
        raise HTTPException(status_code=400, detail="Prompt is empty.")
    if len(payload.images) > 6:
        raise HTTPException(status_code=400, detail="Image limit exceeded.")

    user = _session_user(request) or {}
    user_email = str(user.get("email") or "anonymous@dev")
    request_id = str(uuid4())
    meta = _client_meta(request)
    try:
        model_image_paths, image_urls = _persist_request_images(payload.images, user_email=user_email, request_id=request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return PreparedChatRequest(
        request_id=request_id,
        user_email=user_email,
        user_display_name=_user_display_name(user),
        prompt=prompt,
        history=list(payload.history),
        meta=meta,
        model_image_paths=model_image_paths,
        image_urls=image_urls,
        user_content=_format_user_message_content(prompt, image_urls),
        started_at=perf_counter(),
    )


def _request_latency_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _log_request_start(prepared: PreparedChatRequest) -> None:
    logs.log_event(
        prepared.user_email,
        {
            "event_type": "request_start",
            "request_id": prepared.request_id,
            "user_email": prepared.user_email,
            "prompt": prepared.user_content,
            "image_count": len(prepared.model_image_paths),
            "tools_enabled": cfg.tools_enabled,
            **prepared.meta,
        },
    )


def _log_request_done(prepared: PreparedChatRequest, assistant: str) -> None:
    logs.log_event(
        prepared.user_email,
        {
            "event_type": "request_done",
            "request_id": prepared.request_id,
            "user_email": prepared.user_email,
            "assistant_final": assistant,
            "latency_ms": _request_latency_ms(prepared.started_at),
            "image_count": len(prepared.model_image_paths),
            "tools_enabled": cfg.tools_enabled,
            **prepared.meta,
        },
    )


def _log_request_error(prepared: PreparedChatRequest, error: Exception) -> None:
    logs.log_event(
        prepared.user_email,
        {
            "event_type": "request_error",
            "request_id": prepared.request_id,
            "user_email": prepared.user_email,
            "error": str(error),
            "latency_ms": _request_latency_ms(prepared.started_at),
            "image_count": len(prepared.model_image_paths),
            "tools_enabled": cfg.tools_enabled,
            **prepared.meta,
        },
        error_log=True,
    )


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    snapshot = engine.runtime_snapshot()
    return {
        "ok": True,
        "mode": cfg.mode,
        "path_prefix": cfg.path_prefix,
        "auth_required": cfg.auth_required,
        "tools_enabled": cfg.tools_enabled,
        "smoke_mode": not cfg.load_model,
        "model_loaded": snapshot.get("model_loaded", False),
        "configured_model_dir": snapshot.get("model_dir", ""),
        "active_model_dir": snapshot.get("model_dir", ""),
        "log_root": str(cfg.log_root),
    }


@app.get("/", include_in_schema=False)
def root_redirect(request: Request) -> RedirectResponse:
    if cfg.auth_required and _session_user(request) is None:
        return RedirectResponse(url=f"{cfg.path_prefix}/login")
    return RedirectResponse(url=cfg.path_prefix)


@app.get(f"{cfg.path_prefix}/login", response_class=HTMLResponse)
def login_page(request: Request) -> Any:
    if not cfg.auth_required:
        return RedirectResponse(url=cfg.path_prefix)
    if _session_user(request):
        return RedirectResponse(url=cfg.path_prefix)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "path_prefix": cfg.path_prefix,
            "title": "Athena V5 Login",
            "asset_version": _asset_version(),
        },
    )


@app.get(f"{cfg.path_prefix}/auth/login")
async def auth_login(request: Request) -> Any:
    if not cfg.auth_required:
        return RedirectResponse(url=cfg.path_prefix)
    if _session_user(request):
        return RedirectResponse(url=cfg.path_prefix)
    if oauth is None:
        raise HTTPException(status_code=500, detail="OAuth is not initialized.")
    return await oauth.google.authorize_redirect(request, cfg.auth_redirect_uri)


@app.get(f"{cfg.path_prefix}/auth/callback")
async def auth_callback(request: Request) -> Any:
    if oauth is None:
        raise HTTPException(status_code=500, detail="OAuth is not initialized.")
    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo") or await oauth.google.parse_id_token(request, token)
        user = {
            "sub": str((userinfo or {}).get("sub") or ""),
            "email": str((userinfo or {}).get("email") or ""),
            "name": str((userinfo or {}).get("name") or ""),
            "picture": str((userinfo or {}).get("picture") or ""),
            "issued_at": _utc_now_iso(),
        }
        if not user["email"]:
            raise ValueError("Google account did not return email.")
        request.session["user"] = user
        logs.ensure_profile(user)
        logs.log_event(user["email"], {"event_type": "auth_login", "user_email": user["email"]})
        return RedirectResponse(url=cfg.path_prefix)
    except Exception as exc:
        return HTMLResponse(f"<h3>Google login failed</h3><pre>{str(exc)}</pre>", status_code=400)


@app.post(f"{cfg.path_prefix}/auth/logout")
def auth_logout(request: Request) -> dict[str, Any]:
    user = _session_user(request)
    if user and user.get("email"):
        logs.log_event(str(user["email"]), {"event_type": "auth_logout", "user_email": str(user["email"])})
    request.session.clear()
    return {"ok": True}


@app.get(cfg.path_prefix, response_class=HTMLResponse)
def portal_index(request: Request) -> HTMLResponse:
    if cfg.auth_required and _session_user(request) is None:
        return RedirectResponse(url=f"{cfg.path_prefix}/login")
    user = _session_user(request) or {}
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "path_prefix": cfg.path_prefix,
            "title": "Athena V5 Browser",
            "asset_version": _asset_version(),
            "desktop_shell": False,
            "initial_transcript_html": render_transcript_html(
                _initial_messages(),
                user_label=_user_display_name(user),
            ),
        },
    )


@app.get(f"{cfg.path_prefix}/api/me")
def api_me(request: Request) -> dict[str, Any]:
    if not cfg.auth_required:
        return {"user": {"email": "anonymous@dev", "name": "Anonymous", "sub": "", "picture": ""}}
    user = _session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return {"user": user}


@app.get(f"{cfg.path_prefix}/api/config")
def api_config(request: Request) -> dict[str, Any]:
    _require_auth(request)
    data = engine.runtime_snapshot()
    data.update(
        {
            "mode": cfg.mode,
            "path_prefix": cfg.path_prefix,
            "auth_required": cfg.auth_required,
            "smoke_mode": not cfg.load_model,
            "configured_model_label": data.get("model_label") or Path(str(data.get("model_dir") or "")).name,
            "configured_model_dir": data.get("model_dir") or "",
            "active_model_label": data.get("model_label") or "",
            "active_model_dir": data.get("model_dir") or "",
        }
    )
    return data


@app.get(f"{cfg.path_prefix}/api/uploads/{{relative_path:path}}")
def api_upload_file(relative_path: str, request: Request) -> FileResponse:
    _require_auth(request)
    rel = relative_path.strip().lstrip("/")
    if not rel or ".." in rel.replace("\\", "/"):
        raise HTTPException(status_code=400, detail="Invalid path.")
    target = (cfg.log_root / rel).resolve()
    if not str(target).startswith(str(cfg.log_root.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden.")
    if cfg.auth_required:
        user = _session_user(request) or {}
        expected_prefix = str((cfg.log_root / logs.user_key(str(user.get("email") or "anonymous@dev"))).resolve())
        if not str(target).startswith(expected_prefix):
            raise HTTPException(status_code=403, detail="Forbidden.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path=str(target))


@app.post(f"{cfg.path_prefix}/api/chat/stream")
def api_chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    _require_auth(request)
    prepared = _prepare_chat_request(payload, request)
    _log_request_start(prepared)

    q: "Queue[dict[str, Any]]" = Queue()

    def worker() -> None:
        session = engine.create_session()
        session.restore_history([{"role": item.role, "content": item.content} for item in prepared.history])
        terminal = Event()

        def on_event(event: EngineEvent) -> None:
            data = event.to_dict()
            if event.type == "turn_done":
                transcript_html = render_transcript_html(event.visible_messages, user_label=prepared.user_display_name)
                data["history"] = event.visible_messages
                data["transcript_html"] = transcript_html
                _log_request_done(prepared, event.assistant)
            elif event.type == "turn_error":
                _log_request_error(prepared, RuntimeError(event.message))
            if event.type in {"turn_done", "turn_error"}:
                terminal.set()
            q.put(data)

        try:
            session.submit_turn(
                prepared.prompt,
                image_paths=prepared.model_image_paths,
                display_user_content=prepared.user_content,
                listener=on_event,
            )
            terminal.wait()
        except Exception as exc:
            _log_request_error(prepared, exc)
            q.put({"type": "turn_error", "message": str(exc)})
        finally:
            q.put({"type": "eof"})

    Thread(target=worker, daemon=True).start()

    def iter_events() -> Any:
        while True:
            item = q.get()
            if item.get("type") == "eof":
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        iter_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("browser.portal_server:app", host=cfg.host, port=cfg.port, reload=False)
