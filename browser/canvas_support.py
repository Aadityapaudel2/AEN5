from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_CANVAS_STATE_STALE_SECONDS = 15 * 60
DEFAULT_BUNDLE_CHUNK_LIMIT = 4
DEFAULT_PILOT_OVERRIDE_CHUNK_LIMIT = 4
_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "by",
    "do",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "the",
    "to",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "you",
    "your",
}
_EXAM_RE = re.compile(r"\b(exam|quiz|test|midterm|final)\b", re.IGNORECASE)
_SCHEDULE_RE = re.compile(
    r"\b(when|date|dates|due|deadline|deadlines|exam|quiz|test|midterm|final|office hours|schedule|semester|break|study day)\b",
    re.IGNORECASE,
)
_COURSE_OVERVIEW_RE = re.compile(r"\b(course|class)\b.*\b(about|overview|cover|studying)\b|\bwhat are we studying\b", re.IGNORECASE)
_DISCUSSION_RE = re.compile(r"\bdiscussion|reply|replies|forum|netiquette\b", re.IGNORECASE)


def _clean_text(value: object, *, limit: int = 400) -> str:
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(raw) <= limit:
        return raw
    if limit <= 3:
        return raw[:limit]
    return raw[: limit - 3].rstrip() + "..."


def _clean_list(values: object, *, limit: int = 24) -> list[str]:
    if values is None:
        return []
    source: Iterable[object]
    if isinstance(values, (list, tuple, set)):
        source = values
    else:
        source = [values]
    cleaned: list[str] = []
    for item in source:
        text = _clean_text(item, limit=180)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _clean_course_ids(values: object) -> tuple[str, ...]:
    ids = [_clean_text(value, limit=64) for value in _clean_list(values, limit=32)]
    return tuple(value for value in ids if value)


def _parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_or_empty(value: object) -> str:
    parsed = _parse_dt(value)
    return parsed.isoformat() if parsed else ""


def _future_sort_key(item: dict[str, Any], *keys: str) -> tuple[int, datetime]:
    now = datetime.now(timezone.utc)
    for key in keys:
        parsed = _parse_dt(item.get(key))
        if parsed is not None and parsed >= now:
            return (0, parsed)
    return (1, datetime.max.replace(tzinfo=timezone.utc))


def _tokenize_query(text: str) -> list[str]:
    tokens = []
    seen: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(token) < 2 or token in _QUERY_STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


@dataclass(frozen=True)
class InstitutionRecord:
    institution_key: str
    label: str
    canvas_domain: str
    oauth_client_id_env: str
    oauth_client_secret_env: str
    redirect_uri_env: str
    bundle_root: Path
    mapped_course_ids: tuple[str, ...] = field(default_factory=tuple)
    oauth_scopes: tuple[str, ...] = field(default_factory=tuple)
    default_selected: bool = False
    course_hints: tuple[str, ...] = field(default_factory=tuple)

    @property
    def oauth_client_name(self) -> str:
        return f"canvas_{self.institution_key}"

    @property
    def client_id(self) -> str:
        return (os.getenv(self.oauth_client_id_env) or "").strip()

    @property
    def client_secret(self) -> str:
        return (os.getenv(self.oauth_client_secret_env) or "").strip()

    @property
    def redirect_uri(self) -> str:
        return (os.getenv(self.redirect_uri_env) or "").strip()

    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    @property
    def authorize_url(self) -> str:
        return f"https://{self.canvas_domain}/login/oauth2/auth"

    @property
    def token_url(self) -> str:
        return f"https://{self.canvas_domain}/login/oauth2/token"

    @property
    def api_base_url(self) -> str:
        return f"https://{self.canvas_domain}/api/v1/"

    def public_dict(self) -> dict[str, Any]:
        return {
            "institution_key": self.institution_key,
            "label": self.label,
            "canvas_domain": self.canvas_domain,
            "mapped_course_ids": list(self.mapped_course_ids),
            "course_hints": list(self.course_hints),
            "default_selected": self.default_selected,
        }


class InstitutionRegistry:
    def __init__(self, records: Sequence[InstitutionRecord]):
        normalized: list[InstitutionRecord] = []
        seen: set[str] = set()
        for record in records:
            key = record.institution_key.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(record)
        self._records = tuple(normalized)
        self._by_key = {record.institution_key: record for record in self._records}

    @classmethod
    def load(cls, config_path: Path, *, project_root: Path) -> "InstitutionRegistry":
        if not config_path.exists():
            return cls(())
        raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
        items = raw.get("institutions") if isinstance(raw, dict) else raw
        records: list[InstitutionRecord] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            key = _clean_text(item.get("institution_key"), limit=64).lower()
            label = _clean_text(item.get("label"), limit=120)
            canvas_domain = _clean_text(item.get("canvas_domain"), limit=180).lower()
            if not key or not label or not canvas_domain:
                continue
            bundle_value = _clean_text(item.get("bundle_root"), limit=260)
            bundle_root = Path(bundle_value) if bundle_value else project_root / key
            if not bundle_root.is_absolute():
                bundle_root = (project_root / bundle_root).resolve()
            scopes = tuple(
                part
                for part in [
                    _clean_text(scope, limit=200)
                    for scope in (
                        item.get("oauth_scopes")
                        if isinstance(item.get("oauth_scopes"), list)
                        else str(item.get("oauth_scopes") or "").split()
                    )
                ]
                if part
            )
            records.append(
                InstitutionRecord(
                    institution_key=key,
                    label=label,
                    canvas_domain=canvas_domain,
                    oauth_client_id_env=_clean_text(item.get("oauth_client_id_env"), limit=120),
                    oauth_client_secret_env=_clean_text(item.get("oauth_client_secret_env"), limit=120),
                    redirect_uri_env=_clean_text(item.get("redirect_uri_env"), limit=120),
                    bundle_root=bundle_root,
                    mapped_course_ids=_clean_course_ids(item.get("mapped_course_ids")),
                    oauth_scopes=scopes,
                    default_selected=bool(item.get("default_selected")),
                    course_hints=tuple(_clean_list(item.get("course_hints"), limit=12)),
                )
            )
        if records and not any(record.default_selected for record in records):
            first = records[0]
            records[0] = InstitutionRecord(
                institution_key=first.institution_key,
                label=first.label,
                canvas_domain=first.canvas_domain,
                oauth_client_id_env=first.oauth_client_id_env,
                oauth_client_secret_env=first.oauth_client_secret_env,
                redirect_uri_env=first.redirect_uri_env,
                bundle_root=first.bundle_root,
                mapped_course_ids=first.mapped_course_ids,
                oauth_scopes=first.oauth_scopes,
                default_selected=True,
                course_hints=first.course_hints,
            )
        return cls(records)

    def __bool__(self) -> bool:
        return bool(self._records)

    def all(self) -> tuple[InstitutionRecord, ...]:
        return self._records

    def get(self, institution_key: str | None) -> InstitutionRecord | None:
        key = str(institution_key or "").strip().lower()
        return self._by_key.get(key)

    def default(self) -> InstitutionRecord | None:
        for record in self._records:
            if record.default_selected:
                return record
        return self._records[0] if self._records else None

    def available(self) -> list[InstitutionRecord]:
        return [record for record in self._records if record.has_credentials()]

    def public_options(self) -> list[dict[str, Any]]:
        return [record.public_dict() for record in self._records]


def _normalize_course(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean_text(raw.get("id") or raw.get("course_id"), limit=64),
        "name": _clean_text(raw.get("name"), limit=180),
        "course_code": _clean_text(raw.get("course_code"), limit=120),
        "workflow_state": _clean_text(raw.get("workflow_state"), limit=40),
        "start_at": _iso_or_empty(raw.get("start_at")),
        "end_at": _iso_or_empty(raw.get("end_at") or raw.get("conclude_at")),
    }


def _normalize_enrollment(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean_text(raw.get("id"), limit=64),
        "course_id": _clean_text(raw.get("course_id"), limit=64),
        "course_section_id": _clean_text(raw.get("course_section_id"), limit=64),
        "course_section_name": _clean_text(raw.get("course_section_name"), limit=180),
        "type": _clean_text(raw.get("type"), limit=80),
        "role": _clean_text(raw.get("role"), limit=80),
        "enrollment_state": _clean_text(raw.get("enrollment_state"), limit=80),
    }


def _normalize_assignment(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean_text(raw.get("id"), limit=64),
        "course_id": _clean_text(raw.get("course_id"), limit=64),
        "name": _clean_text(raw.get("name") or raw.get("title"), limit=220),
        "description": _clean_text(raw.get("description"), limit=400),
        "due_at": _iso_or_empty(raw.get("due_at")),
        "unlock_at": _iso_or_empty(raw.get("unlock_at")),
        "lock_at": _iso_or_empty(raw.get("lock_at")),
        "workflow_state": _clean_text(raw.get("workflow_state"), limit=40),
        "submission_types": _clean_list(raw.get("submission_types"), limit=8),
        "points_possible": _clean_text(raw.get("points_possible"), limit=40),
        "html_url": _clean_text(raw.get("html_url"), limit=260),
    }


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean_text(raw.get("id"), limit=64),
        "course_id": _clean_text(raw.get("course_id"), limit=64),
        "context_code": _clean_text(raw.get("context_code"), limit=80),
        "title": _clean_text(raw.get("title"), limit=220),
        "description": _clean_text(raw.get("description"), limit=400),
        "start_at": _iso_or_empty(raw.get("start_at")),
        "end_at": _iso_or_empty(raw.get("end_at")),
        "workflow_state": _clean_text(raw.get("workflow_state"), limit=40),
        "location_name": _clean_text(raw.get("location_name"), limit=180),
        "html_url": _clean_text(raw.get("html_url"), limit=260),
    }


def _normalize_module_item(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean_text(raw.get("id"), limit=64),
        "title": _clean_text(raw.get("title"), limit=220),
        "type": _clean_text(raw.get("type") or raw.get("content_type"), limit=80),
        "position": int(raw.get("position") or 0),
        "published": bool(raw.get("published", True)),
        "completion_requirement": raw.get("completion_requirement") if isinstance(raw.get("completion_requirement"), dict) else {},
    }


def _normalize_module(raw: dict[str, Any]) -> dict[str, Any]:
    items = raw.get("items") if isinstance(raw.get("items"), list) else []
    return {
        "id": _clean_text(raw.get("id"), limit=64),
        "course_id": _clean_text(raw.get("course_id"), limit=64),
        "name": _clean_text(raw.get("name") or raw.get("title"), limit=220),
        "position": int(raw.get("position") or 0),
        "published": bool(raw.get("published", True)),
        "unlock_at": _iso_or_empty(raw.get("unlock_at")),
        "state": _clean_text(raw.get("state") or raw.get("workflow_state"), limit=40),
        "items": [_normalize_module_item(item) for item in items if isinstance(item, dict)],
    }


def _derive_next(items: Sequence[dict[str, Any]], *date_keys: str) -> dict[str, Any] | None:
    candidates = [item for item in items if any(_parse_dt(item.get(key)) for key in date_keys)]
    if not candidates:
        return None
    chosen = min(candidates, key=lambda item: _future_sort_key(item, *date_keys))
    return dict(chosen)


def _derive_current_unit(modules: Sequence[dict[str, Any]]) -> str:
    ordered = sorted(
        [module for module in modules if module.get("name")],
        key=lambda module: (
            1 if module.get("state") in {"locked", "unpublished"} else 0,
            module.get("position") or 0,
            str(module.get("name") or "").lower(),
        ),
    )
    return _clean_text((ordered[0] if ordered else {}).get("name"), limit=220)


def _derive_sections(enrollments: Sequence[dict[str, Any]]) -> list[str]:
    sections: list[str] = []
    for enrollment in enrollments:
        section_name = _clean_text(enrollment.get("course_section_name"), limit=180)
        if section_name and section_name not in sections:
            sections.append(section_name)
    return sections


def normalize_canvas_state(raw: dict[str, Any] | None, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}
    courses = [_normalize_course(item) for item in raw.get("courses", fallback.get("courses", [])) if isinstance(item, dict)]
    enrollments = [_normalize_enrollment(item) for item in raw.get("enrollments", fallback.get("enrollments", [])) if isinstance(item, dict)]
    assignments = [_normalize_assignment(item) for item in raw.get("assignments", fallback.get("assignments", [])) if isinstance(item, dict)]
    events = [_normalize_event(item) for item in raw.get("events", fallback.get("events", [])) if isinstance(item, dict)]
    modules = [_normalize_module(item) for item in raw.get("modules", fallback.get("modules", [])) if isinstance(item, dict)]
    mapped_course_ids = _clean_course_ids(raw.get("mapped_course_ids") or fallback.get("mapped_course_ids"))
    relevant_course_ids = _clean_course_ids(raw.get("relevant_course_ids") or fallback.get("relevant_course_ids") or mapped_course_ids)
    next_due = _derive_next(assignments, "due_at")
    exam_like = [item for item in assignments if _EXAM_RE.search(str(item.get("name") or ""))]
    exam_events = [item for item in events if _EXAM_RE.search(str(item.get("title") or ""))]
    next_exam = _derive_next(exam_like, "due_at") or _derive_next(exam_events, "start_at")
    next_event = _derive_next(events, "start_at", "end_at")
    derived = {
        "next_due": next_due,
        "next_exam": next_exam,
        "next_event": next_event,
        "course_sections": _derive_sections(enrollments),
        "current_unit": _clean_text(raw.get("derived", {}).get("current_unit") if isinstance(raw.get("derived"), dict) else "", limit=220) or _derive_current_unit(modules),
    }
    return {
        "institution_key": _clean_text(raw.get("institution_key"), limit=64) or _clean_text(fallback.get("institution_key"), limit=64),
        "institution_name": _clean_text(raw.get("institution_name"), limit=180) or _clean_text(fallback.get("institution_name"), limit=180),
        "canvas_domain": _clean_text(raw.get("canvas_domain"), limit=180) or _clean_text(fallback.get("canvas_domain"), limit=180),
        "canvas_user_id": _clean_text(raw.get("canvas_user_id"), limit=64) or _clean_text(fallback.get("canvas_user_id"), limit=64),
        "mapped_course_ids": list(mapped_course_ids),
        "relevant_course_ids": list(relevant_course_ids),
        "courses": courses,
        "enrollments": enrollments,
        "assignments": assignments,
        "events": events,
        "modules": modules,
        "derived": derived,
        "updated_at": _iso_or_empty(raw.get("updated_at")) or _iso_or_empty(fallback.get("updated_at")) or datetime.now(timezone.utc).isoformat(),
    }


def canvas_state_has_content(state: dict[str, Any] | None) -> bool:
    if not isinstance(state, dict):
        return False
    return bool(
        state.get("canvas_user_id")
        or state.get("courses")
        or state.get("enrollments")
        or state.get("assignments")
        or state.get("events")
        or state.get("modules")
        or state.get("derived")
    )


def canvas_state_is_stale(state: dict[str, Any] | None, *, max_age_seconds: int = DEFAULT_CANVAS_STATE_STALE_SECONDS) -> bool:
    if not canvas_state_has_content(state):
        return True
    updated_at = _parse_dt((state or {}).get("updated_at"))
    if updated_at is None:
        return True
    return (datetime.now(timezone.utc) - updated_at).total_seconds() >= max_age_seconds


def extract_relevant_course_ids(state: dict[str, Any] | None) -> list[str]:
    if not isinstance(state, dict):
        return []
    raw = state.get("relevant_course_ids") or state.get("mapped_course_ids") or []
    return [value for value in _clean_course_ids(raw)]


def build_canvas_summary_lines(state: dict[str, Any] | None) -> list[str]:
    if not canvas_state_has_content(state):
        return []
    normalized = normalize_canvas_state(state)
    lines: list[str] = []
    sections = normalized.get("derived", {}).get("course_sections") or []
    if sections:
        lines.append("Current course sections: " + "; ".join(_clean_list(sections, limit=8)))
    next_due = normalized.get("derived", {}).get("next_due") or {}
    if next_due:
        lines.append(
            "Next due assignment: "
            + _clean_text(next_due.get("name"), limit=180)
            + (" | due " + _clean_text(next_due.get("due_at"), limit=80) if next_due.get("due_at") else "")
        )
    next_exam = normalized.get("derived", {}).get("next_exam") or {}
    if next_exam:
        exam_name = next_exam.get("name") or next_exam.get("title")
        exam_time = next_exam.get("due_at") or next_exam.get("start_at")
        lines.append(
            "Next exam or quiz: "
            + _clean_text(exam_name, limit=180)
            + (" | " + _clean_text(exam_time, limit=80) if exam_time else "")
        )
    next_event = normalized.get("derived", {}).get("next_event") or {}
    if next_event:
        lines.append(
            "Next scheduled event: "
            + _clean_text(next_event.get("title"), limit=180)
            + (" | starts " + _clean_text(next_event.get("start_at"), limit=80) if next_event.get("start_at") else "")
        )
    current_unit = _clean_text(normalized.get("derived", {}).get("current_unit"), limit=180)
    if current_unit:
        lines.append("Current unit or module: " + current_unit)
    return lines[:6]


def bundle_course_dir(institution: InstitutionRecord, course_id: str) -> Path:
    return institution.bundle_root / "courses" / str(course_id)


def bundle_course_derived_dir(institution: InstitutionRecord, course_id: str) -> Path:
    return bundle_course_dir(institution, course_id) / "derived"


def bundle_course_pilot_dir(institution: InstitutionRecord, course_id: str) -> Path:
    return bundle_course_dir(institution, course_id) / "pilot"


def bundle_course_file_path(institution: InstitutionRecord, course_id: str, filename: str) -> Path:
    course_root = bundle_course_dir(institution, course_id)
    if filename in {"pilot_overrides.json", "pilot_people.json"}:
        ordered = [
            bundle_course_pilot_dir(institution, course_id) / filename,
            course_root / filename,
        ]
    elif filename in {
        "course.json",
        "modules.json",
        "assignments.json",
        "events.json",
        "pages.json",
        "files_manifest.json",
        "content_chunks.jsonl",
    }:
        ordered = [
            bundle_course_derived_dir(institution, course_id) / filename,
            course_root / filename,
        ]
    else:
        ordered = [
            bundle_course_derived_dir(institution, course_id) / filename,
            bundle_course_pilot_dir(institution, course_id) / filename,
            course_root / filename,
        ]
    for candidate in ordered:
        if candidate.exists():
            return candidate
    return ordered[0]


def load_bundle_course_json(institution: InstitutionRecord, course_id: str, filename: str) -> dict[str, Any]:
    target = bundle_course_file_path(institution, course_id, filename)
    if not target.exists():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_pilot_overrides(institution: InstitutionRecord, course_id: str) -> dict[str, Any]:
    return load_bundle_course_json(institution, course_id, "pilot_overrides.json")


def is_schedule_query(query: str) -> bool:
    if not str(query or "").strip():
        return False
    if _SCHEDULE_RE.search(query):
        return True
    tokens = set(_tokenize_query(query))
    return bool(tokens & {"exam", "quiz", "final", "due", "date", "schedule"})


def _is_course_overview_query(query: str) -> bool:
    text = str(query or "").strip()
    if not text:
        return False
    if _COURSE_OVERVIEW_RE.search(text):
        return True
    lowered = text.lower()
    return "what is this course about" in lowered or "what is this class about" in lowered


def _is_discussion_query(query: str) -> bool:
    return bool(_DISCUSSION_RE.search(str(query or "")))


def _pilot_chunks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("chunks")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _next_future_entry(rows: Sequence[dict[str, Any]], *keys: str) -> dict[str, Any] | None:
    candidates = [item for item in rows if isinstance(item, dict) and any(_parse_dt(item.get(key)) for key in keys)]
    if not candidates:
        return None
    return min(candidates, key=lambda item: _future_sort_key(item, *keys))


def _assessment_query_target(query: str) -> tuple[str, str] | None:
    lowered = str(query or "").lower()
    if not lowered.strip():
        return None
    if "final" in lowered:
        return ("final", "")
    match = re.search(r"\b(quiz|exam|test|midterm)\s*#?\s*(\d{1,2})\b", lowered)
    if not match:
        return None
    kind = match.group(1)
    if kind == "test":
        kind = "exam"
    return (kind, match.group(2))


def _matching_assessment_row(assessments: Sequence[dict[str, Any]], query: str) -> dict[str, Any] | None:
    target = _assessment_query_target(query)
    if target is None:
        return None
    kind, number = target
    for item in assessments:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        lowered = name.lower()
        if kind == "final":
            if "final" in lowered:
                return item
            continue
        if kind not in lowered:
            continue
        if re.search(rf"#\s*{re.escape(number)}\b", lowered) or re.search(rf"\b{re.escape(number)}\b", lowered):
            return item
    return None


def build_pilot_bundle_query(
    institution: InstitutionRecord,
    query: str,
    *,
    course_ids: Sequence[str] | None = None,
) -> str:
    selected_course_ids = [str(value) for value in (course_ids or institution.mapped_course_ids)]
    if not selected_course_ids:
        return query
    payload = load_pilot_overrides(institution, selected_course_ids[0])
    if not payload:
        return query
    assessments = payload.get("assessment_calendar") if isinstance(payload.get("assessment_calendar"), list) else []
    matched = _matching_assessment_row([item for item in assessments if isinstance(item, dict)], query)
    if matched is None:
        return query
    extras = [
        _clean_text(matched.get("name"), limit=120),
        _clean_text(matched.get("topics"), limit=260),
    ]
    joined = " ".join(part for part in extras if part)
    if not joined:
        return query
    return f"{query}\n{joined}".strip()


def build_pilot_override_summary_lines(
    institution: InstitutionRecord,
    *,
    course_ids: Sequence[str] | None = None,
    query: str = "",
) -> list[str]:
    selected_course_ids = [str(value) for value in (course_ids or institution.mapped_course_ids)]
    if not selected_course_ids:
        return []
    payload = load_pilot_overrides(institution, selected_course_ids[0])
    if not payload:
        return []
    lines: list[str] = []
    overview_query = _is_course_overview_query(query)
    discussion_query = _is_discussion_query(query)
    course_title = _clean_text(payload.get("course_title") or payload.get("course_name"), limit=220)
    if course_title:
        lines.append("Pilot course context: " + course_title)
    if overview_query:
        course_theme = _clean_text(payload.get("course_theme"), limit=220)
        if course_theme:
            lines.append("Course theme and framing: " + course_theme)
        published_modules = _clean_list(payload.get("published_module_titles"), limit=6)
        if published_modules:
            lines.append("Students work through: " + ", ".join(published_modules))
        upcoming_modules = _clean_list(payload.get("upcoming_module_titles"), limit=5)
        if upcoming_modules:
            lines.append("Later in the term: " + ", ".join(upcoming_modules))
    updated = _clean_text(payload.get("source_updated_text"), limit=120)
    if updated:
        lines.append("Date-sensitive answers should come from the course at-a-glance guide updated " + updated + ".")
    if query and is_schedule_query(query):
        lines.append("For schedule questions, copy the assessment name and date exactly as written in the guide. Do not infer or rewrite the year.")
    assessments = payload.get("assessment_calendar") if isinstance(payload.get("assessment_calendar"), list) else []
    requested_assessment = _matching_assessment_row([item for item in assessments if isinstance(item, dict)], query)
    if requested_assessment is not None:
        requested_name = _clean_text(requested_assessment.get("name"), limit=180)
        requested_date = _clean_text(requested_assessment.get("date_text"), limit=120)
        requested_topics = _clean_text(requested_assessment.get("topics"), limit=240)
        if requested_name and requested_date:
            lines.append(f"Requested assessment: {requested_name} | {requested_date}")
        if requested_topics:
            lines.append("Requested assessment topics: " + requested_topics)
    next_assessment = _next_future_entry([item for item in assessments if isinstance(item, dict)], "start_at", "end_at")
    if not overview_query and not discussion_query and requested_assessment is None and next_assessment is not None:
        name = _clean_text(next_assessment.get("name"), limit=180)
        date_text = _clean_text(next_assessment.get("date_text"), limit=120)
        if name and date_text:
            lines.append(f"Next scheduled assessment: {name} | {date_text}")
    if query and "final" in str(query).lower():
        final_row = next(
            (item for item in assessments if isinstance(item, dict) and "final" in str(item.get("name") or "").lower()),
            None,
        )
        if final_row is not None:
            final_text = _clean_text(final_row.get("date_text"), limit=120)
            if final_text:
                lines.append("Final exam window: " + final_text)
    if query and "discussion" in str(query).lower():
        policies = payload.get("policy_reminders") if isinstance(payload.get("policy_reminders"), list) else []
        discussion_policy = next((item for item in policies if "discussion" in str(item).lower()), "")
        if discussion_policy:
            lines.append("Discussion policy: " + _clean_text(discussion_policy, limit=220))
    lines.append("This pilot does not use live Canvas sync or personal gradebook data.")
    return lines[:6]


def retrieve_pilot_override_chunks(
    institution: InstitutionRecord,
    query: str,
    *,
    course_ids: Sequence[str] | None = None,
    limit: int = DEFAULT_PILOT_OVERRIDE_CHUNK_LIMIT,
) -> list[dict[str, Any]]:
    tokens = _tokenize_query(query)
    if not tokens:
        return []
    overview_query = _is_course_overview_query(query)
    discussion_query = _is_discussion_query(query)
    selected_course_ids = [str(value) for value in (course_ids or institution.mapped_course_ids)]
    if not selected_course_ids:
        return []
    scored: list[tuple[float, dict[str, Any]]] = []
    for course_id in selected_course_ids:
        payload = load_pilot_overrides(institution, course_id)
        if not payload:
            continue
        assessments = payload.get("assessment_calendar") if isinstance(payload.get("assessment_calendar"), list) else []
        requested_assessment = _matching_assessment_row([item for item in assessments if isinstance(item, dict)], query)
        requested_title = _clean_text((requested_assessment or {}).get("name"), limit=200).lower()
        for chunk in _pilot_chunks(payload):
            haystack = f"{chunk.get('title', '')}\n{chunk.get('text', '')}".lower()
            if not haystack.strip():
                continue
            title = str(chunk.get("title") or "").lower()
            source_type = str(chunk.get("source_type") or "").lower()
            if discussion_query and source_type in {"pilot_assessment", "pilot_semester_date", "pilot_final"}:
                continue
            if requested_title:
                if source_type == "pilot_assessment" and title != requested_title:
                    continue
                if source_type == "pilot_semester_date" and "final" not in requested_title:
                    continue
                if source_type == "pilot_final" and "final" not in requested_title:
                    continue
                if source_type == "pilot_policy":
                    continue
            score = 0.0
            for token in tokens:
                if token in title:
                    score += 3.5
                hits = haystack.count(token)
                if hits:
                    score += min(hits, 5) * 1.2
            if overview_query and source_type == "pilot_overview":
                score += 8.0
            if overview_query and source_type == "pilot_roadmap":
                score += 7.0
            if overview_query and source_type in {"pilot_assessment", "pilot_semester_date", "pilot_final"}:
                score -= 2.5
            if requested_title and title == requested_title:
                score += 12.0
            if source_type.startswith("pilot_assessment") or source_type.startswith("pilot_semester_date"):
                score += 1.0
            if source_type.startswith("pilot_policy"):
                score += 0.5
            if discussion_query and source_type == "pilot_policy":
                score += 4.0
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "course_id": str(chunk.get("course_id") or course_id),
                        "source_type": _clean_text(chunk.get("source_type"), limit=80),
                        "source_path": _clean_text(chunk.get("source_path"), limit=260),
                        "title": _clean_text(chunk.get("title"), limit=200),
                        "text": _clean_text(chunk.get("text"), limit=720),
                    },
                )
            )
    top = sorted(scored, key=lambda item: (-item[0], item[1].get("title") or ""))[: max(0, limit)]
    return [item[1] for item in top]


def retrieve_bundle_chunks(
    institution: InstitutionRecord,
    query: str,
    *,
    course_ids: Sequence[str] | None = None,
    limit: int = DEFAULT_BUNDLE_CHUNK_LIMIT,
) -> list[dict[str, Any]]:
    tokens = _tokenize_query(query)
    if not tokens:
        return []
    overview_query = _is_course_overview_query(query)
    discussion_query = _is_discussion_query(query)
    selected_course_ids = [str(value) for value in (course_ids or institution.mapped_course_ids)]
    if not selected_course_ids:
        selected_course_ids = [path.name for path in (institution.bundle_root / "courses").glob("*") if path.is_dir()]
    scored: list[tuple[float, dict[str, Any]]] = []
    for course_id in selected_course_ids:
        path = bundle_course_file_path(institution, course_id, "content_chunks.jsonl")
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for raw_line in lines:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                chunk = json.loads(raw_line)
            except Exception:
                continue
            if not isinstance(chunk, dict):
                continue
            title_text = str(chunk.get("title") or "")
            source_type = str(chunk.get("source_type") or "")
            haystack = f"{chunk.get('title', '')}\n{chunk.get('text', '')}".lower()
            if not haystack.strip():
                continue
            lowered_title = title_text.lower()
            if any(marker in lowered_title for marker in ("do not publish", "author notes", "information for instructor", "faculty note", "instructor needs to review")):
                continue
            if discussion_query and any(marker in haystack for marker in ("academic integrity", "academic dishonesty", "student handbook 1.5.a")):
                continue
            score = 0.0
            title = lowered_title
            for token in tokens:
                if token in title:
                    score += 3.0
                hits = haystack.count(token)
                if hits:
                    score += min(hits, 5) * 1.0
            if source_type in {"assignment", "module", "page", "syllabus"}:
                score += 0.25
            if overview_query and source_type == "syllabus":
                score += 6.0
            if overview_query and any(marker in title for marker in ("welcome", "course information", "course overview", "syllabus")):
                score += 2.5
            if discussion_query and any(marker in title for marker in ("discussion", "replies reminder", "netiquette", "rules of engagement")):
                score += 5.0
            if discussion_query and "academic integrity" in title:
                score -= 3.0
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "course_id": str(chunk.get("course_id") or course_id),
                        "source_type": _clean_text(source_type, limit=80),
                        "source_path": _clean_text(chunk.get("source_path"), limit=260),
                        "title": _clean_text(title_text, limit=200),
                        "text": _clean_text(chunk.get("text"), limit=720),
                    },
                )
            )
    top = sorted(scored, key=lambda item: (-item[0], item[1].get("title") or ""))[: max(0, limit)]
    return [item[1] for item in top]
