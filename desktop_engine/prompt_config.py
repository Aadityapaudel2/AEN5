from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PROMPT_TEXT = "You are Athena."

PROMPT_SECTION_SPECS: tuple[tuple[str, str], ...] = (
    ("boot_contract", "Boot contract:"),
    ("response_routing", "Response routing:"),
    ("tutoring_doctrine", "Tutoring doctrine:"),
    ("educator_protocol", "Educator protocol:"),
    ("memory_contract", "Memory contract:"),
    ("core_behavior", "Core behavior:"),
    ("math_response_protocol", "Math response protocol:"),
    ("academic_integrity", "Academic integrity:"),
    ("formatting_rules", "Formatting rules:"),
    ("default_mode", "Default mode:"),
)

PUBLIC_TUTOR_REQUIRED_SECTIONS: tuple[str, ...] = (
    "boot_contract",
    "response_routing",
    "tutoring_doctrine",
    "educator_protocol",
    "memory_contract",
    "core_behavior",
    "math_response_protocol",
    "formatting_rules",
    "default_mode",
)


class PromptConfigError(RuntimeError):
    """Raised when a strict prompt profile is missing, malformed, or incomplete."""


@dataclass(frozen=True)
class PromptDocument:
    text: str
    path: str
    prompt_format: str
    name: str
    version: str
    sha256: str
    validated: bool

    def public_metadata(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "version": self.version,
            "sha256": self.sha256,
            "validated": self.validated,
        }


def as_str_lines(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text:
            lines.append(text)
    return lines


def _as_text_block(value: object) -> str:
    return "\n".join(as_str_lines(value)).strip()


def render_system_prompt_from_json(cfg: dict[str, Any]) -> str:
    direct = cfg.get("system_prompt")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    persona = cfg.get("persona")
    if isinstance(persona, str) and persona.strip():
        chunks.append(persona.strip())

    for key, label in PROMPT_SECTION_SPECS:
        lines = as_str_lines(cfg.get(key))
        if lines:
            chunks.append(label + "\n" + "\n".join(f"- {line}" for line in lines))

    for key in ("identity_prompt", "creator_contract", "creator contract", "custom_constraints_line"):
        extra = _as_text_block(cfg.get(key))
        if extra:
            chunks.append(extra)

    return "\n\n".join(chunks).strip()


def validate_public_tutor_config(
    cfg: dict[str, Any],
    *,
    banned_markers: Iterable[str] = (),
) -> list[str]:
    errors: list[str] = []
    for field in ("version", "name", "persona"):
        if not isinstance(cfg.get(field), str) or not str(cfg.get(field) or "").strip():
            errors.append(f"missing non-empty {field!r}")

    if "system_prompt" in cfg:
        errors.append("public tutor profiles must use named sections, not a monolithic system_prompt field")

    for key in PUBLIC_TUTOR_REQUIRED_SECTIONS:
        if not as_str_lines(cfg.get(key)):
            errors.append(f"missing non-empty tutor section {key!r}")

    rendered = render_system_prompt_from_json(cfg)
    if len(rendered) < 1200:
        errors.append("rendered public tutor prompt is unexpectedly short")

    lowered = rendered.lower()
    for marker in banned_markers:
        probe = str(marker or "").strip().lower()
        if probe and probe in lowered:
            errors.append(f"rendered prompt contains banned marker {probe!r}")
    return errors


def _document(
    *,
    text: str,
    path: Path,
    prompt_format: str,
    name: str,
    version: str,
    validated: bool,
) -> PromptDocument:
    normalized = text.strip()
    return PromptDocument(
        text=normalized,
        path=str(path),
        prompt_format=prompt_format,
        name=name.strip() or "unnamed",
        version=version.strip() or "unknown",
        sha256=sha256(normalized.encode("utf-8")).hexdigest(),
        validated=validated,
    )


def load_prompt_document(
    path: Path,
    *,
    strict: bool = False,
    public_tutor: bool = False,
    banned_markers: Iterable[str] = (),
    fallback: str = DEFAULT_PROMPT_TEXT,
) -> PromptDocument:
    try:
        if path.suffix.lower() == ".json":
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, dict):
                raise PromptConfigError("prompt JSON root must be an object")
            errors = validate_public_tutor_config(raw, banned_markers=banned_markers) if public_tutor else []
            if errors:
                raise PromptConfigError("; ".join(errors))
            rendered = render_system_prompt_from_json(raw)
            if not rendered:
                raise PromptConfigError("prompt profile rendered to empty text")
            return _document(
                text=rendered,
                path=path,
                prompt_format="json",
                name=str(raw.get("name") or "json_prompt"),
                version=str(raw.get("version") or "unknown"),
                validated=public_tutor,
            )

        text = path.read_text(encoding="utf-8-sig").strip()
        if not text:
            raise PromptConfigError("prompt text file is empty")
        if public_tutor:
            raise PromptConfigError("public tutor prompt must be a validated JSON profile")
        return _document(
            text=text,
            path=path,
            prompt_format="text",
            name="text_prompt",
            version="unknown",
            validated=False,
        )
    except Exception as exc:
        if strict:
            if isinstance(exc, PromptConfigError):
                raise
            raise PromptConfigError(f"could not load prompt profile {path}: {exc}") from exc
        return _document(
            text=fallback or DEFAULT_PROMPT_TEXT,
            path=path,
            prompt_format="default",
            name="fallback",
            version="0",
            validated=False,
        )
