from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EngineEvent:
    type: str
    text: str = ""
    message: str = ""
    role: str = ""
    tool: str = ""
    language: str = ""
    provenance: str = ""
    ok: bool | None = None
    result_text: str = ""
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    assistant: str = ""
    visible_messages: list[dict[str, str]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    model_loaded: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
