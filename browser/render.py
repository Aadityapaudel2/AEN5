from __future__ import annotations

import base64
import html
import re
from typing import Iterable

from markdown_it import MarkdownIt


ASSISTANT_LABEL = "Athena"


def _new_markdown_renderer() -> MarkdownIt:
    md = MarkdownIt(
        "commonmark",
        {
            "html": False,
            "linkify": True,
            "typographer": False,
            "breaks": True,
        },
    )
    default_validate_link = md.validateLink
    md.validateLink = lambda url: url.lower().startswith("file://") or default_validate_link(url)  # type: ignore[assignment]
    return md


MARKDOWN = _new_markdown_renderer()
_TEX_DELIM_RE = re.compile(r"(?<!\\)\\([()\[\]])")
_MATH_SPAN_RE = re.compile(
    r"(?<!\\)\$\$[\s\S]+?(?<!\\)\$\$"
    r"|(?<!\\)\\\[[\s\S]+?(?<!\\)\\\]"
    r"|(?<!\\)\\\([\s\S]+?(?<!\\)\\\)"
    r"|(?<!\\)\$(?!\s)(?:\\.|[^$\\\n])+?(?<!\s)(?<!\\)\$"
)


def _preserve_tex_delimiters(text: str) -> str:
    return _TEX_DELIM_RE.sub(lambda match: "\\" + match.group(0), text)


def _normalize_math_segment(segment: str) -> str:
    if segment.startswith("$$") and segment.endswith("$$"):
        return r"\[" + segment[2:-2].strip() + r"\]"
    if segment.startswith("$") and segment.endswith("$"):
        return r"\(" + segment[1:-1].strip() + r"\)"
    return segment


def _extract_math_segments(text: str) -> tuple[str, list[str]]:
    segments: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = f"ATHENA_MATH_TOKEN_{len(segments)}"
        segments.append(_normalize_math_segment(match.group(0)))
        return token

    return _MATH_SPAN_RE.sub(replace, text), segments


def _restore_math_segments(rendered_html: str, segments: list[str]) -> str:
    result = rendered_html
    for idx, segment in enumerate(segments):
        result = result.replace(f"ATHENA_MATH_TOKEN_{idx}", html.escape(segment, quote=False))
    return result


def _role_label(role: str, user_label: str | None = None) -> str:
    if role == "user":
        label = (user_label or "").strip()
        return label or "User"
    if role == "assistant":
        return ASSISTANT_LABEL
    if role == "system":
        return "Portal"
    return role.capitalize()


def _role_icon(role: str) -> str:
    if role == "user":
        return "\U0001F9D1"
    if role == "assistant":
        return "\U0001F9E0"
    if role == "system":
        return "\u2699\ufe0f"
    return "\U0001F4AC"


def render_message_body_html(content: str) -> str:
    protected_text, math_segments = _extract_math_segments(content or "")
    rendered = MARKDOWN.render(_preserve_tex_delimiters(protected_text))
    return _restore_math_segments(rendered, math_segments)


def render_transcript_html(messages: Iterable[dict[str, str]], user_label: str | None = None) -> str:
    chunks: list[str] = []
    for msg in messages:
        role = (msg.get("role") or "assistant").strip().lower()
        raw_content = msg.get("content") or ""
        raw_b64 = base64.b64encode(raw_content.encode("utf-8")).decode("ascii")
        body = render_message_body_html(raw_content)
        chunks.append(
            (
                f'<article class="msg {html.escape(role)}">'
                f'<aside class="avatar" aria-hidden="true">{html.escape(_role_icon(role))}</aside>'
                '<div class="bubble">'
                '<div class="bubble-head">'
                f'<span class="role-pill"><span class="role-icon">{html.escape(_role_icon(role))}</span>{html.escape(_role_label(role, user_label=user_label))}</span>'
                '<button class="copy-msg-btn" type="button" title="Copy raw message" aria-label="Copy raw message">Copy</button>'
                "</div>"
                f'<section class="msg-body" data-raw-b64="{html.escape(raw_b64)}">{body}</section>'
                "</div>"
                "</article>"
            )
        )
    return "\n".join(chunks)
