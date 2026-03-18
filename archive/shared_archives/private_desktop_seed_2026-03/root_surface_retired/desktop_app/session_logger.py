from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in {'1', 'true', 'yes', 'on'}


class DesktopSessionLogger:
    def __init__(self, root: Path | str, *, enabled: bool | None = None, channel: str = 'desktop') -> None:
        self.root = Path(root).expanduser().resolve()
        self.enabled = _env_bool('ATHENA_DESKTOP_NDJSON_LOG', False) if enabled is None else bool(enabled)
        self.channel = channel
        self.scope = (os.getenv('ATHENA_RUNTIME_SCOPE') or '').strip() or ('private' if _env_bool('ATHENA_PRIVATE_MODE', False) else 'public')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.session_id = f'{stamp}_{uuid4().hex[:10]}'
        self.path = self.root / self.channel / f'{self.session_id}.ndjson'
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, **payload: Any) -> None:
        if not self.enabled:
            return
        event = {
            'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'session_id': self.session_id,
            'scope': self.scope,
            'event_type': str(event_type or '').strip() or 'unknown',
            **payload,
        }
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')
