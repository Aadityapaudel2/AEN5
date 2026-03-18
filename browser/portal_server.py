#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
from contextlib import asynccontextmanager
import json
import mimetypes
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
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
    get_browser_config_dir,
    get_browser_root,
    get_default_chat_model_dir,
    get_log_root,
    get_path_prefix,
    get_portal_host,
    get_portal_port,
    get_portal_static_dir,
    get_portal_templates_dir,
    get_system_prompt_path,
    get_tools_enabled_default,
)
from browser.canvas_support import (
    DEFAULT_CANVAS_STATE_STALE_SECONDS,
    InstitutionRecord,
    InstitutionRegistry,
    build_canvas_summary_lines,
    build_pilot_bundle_query,
    build_pilot_override_summary_lines,
    canvas_state_has_content,
    canvas_state_is_stale,
    extract_relevant_course_ids,
    is_schedule_query,
    load_bundle_course_json,
    normalize_canvas_state,
    retrieve_pilot_override_chunks,
    retrieve_bundle_chunks,
)
from browser.render import render_transcript_html
from desktop_engine import DesktopEngine, EngineEvent, EngineSession

try:
    from authlib.integrations.starlette_client import OAuth
except Exception:  # pragma: no cover
    OAuth = None  # type: ignore[assignment]

ROOT = get_browser_root()
CONFIG_DIR = get_browser_config_dir()
PROJECT_ROOT = BOOTSTRAP_ROOT
TEMPLATES_DIR = get_portal_templates_dir()
STATIC_DIR = get_portal_static_dir()
INSTITUTIONS_CONFIG_PATH = CONFIG_DIR / "institutions.json"
DEFAULT_REDIRECT_URI = "https://portal.neohmlabs.com/AEN5/auth/callback"
LEGACY_PATH_PREFIX = "/AthenaV5"
ASSISTANT_LABEL = "Athena"
PORTAL_META_DESCRIPTION = (
    "AthenaV5 is part of NeohmLabs' Artificial Evaluation Network: a public reasoning and tutoring system "
    "built for mathematics, teaching quality, and institution-ready support."
)
PORTAL_WELCOME_TITLE = "Welcome to the portal"
PORTAL_HERO_KICKER = "Part of Artificial Evaluation Network"
PORTAL_HERO_TITLE = "AthenaV5 for mathematics, tutoring, and public reasoning"
PORTAL_HERO_BODY = (
    "AthenaV5 is the public learning surface inside AEN: built for strong mathematics help, coherent tutoring, and institution-ready explanation."
)
PORTAL_HERO_PROMISE = (
    "The front door should stay clean: enter the portal, or read about AEN, SWARM, and the mission before you do."
)
PORTAL_HOME_READING_LINKS = [
    {
        "kicker": "AEN",
        "title": "Read about AEN",
        "body": "See how Artificial Evaluation Network frames Athena as a public learning surface inside a wider reasoning system.",
        "href": "/aen",
    },
    {
        "kicker": "SWARM",
        "title": "Read about SWARM",
        "body": "Understand where orchestration, specialist workflows, and future multi-step institutional pipelines land.",
        "href": "/swarm",
    },
    {
        "kicker": "Mission",
        "title": "Read the mission",
        "body": "Read why NeohmLabs is building AEN with a public-benefit, mathematics-first, and institution-ready orientation.",
        "href": "/mission",
    },
]
PORTAL_SIGNAL_POINTS = [
    "Mathematics-first performance",
    "Teach how to teach",
    "Institution-ready reasoning"
]
PORTAL_CAPABILITY_CARDS = [
    {
        "kicker": "Mathematics",
        "title": "Performance where rigor matters",
        "body": "Athena is designed to explain, verify, and teach mathematics with structure, clarity, and unusually strong attention to correctness."
    },
    {
        "kicker": "Tutoring",
        "title": "Guided help that actually teaches",
        "body": "The goal is not just to answer. The goal is to diagnose level, scaffold the next step, and leave the learner stronger than before."
    },
    {
        "kicker": "Instruction",
        "title": "Support for teachers and tutors",
        "body": "Athena can help design worked examples, misconception checks, review sheets, quick assessments, and practical teaching flow."
    },
    {
        "kicker": "Operations",
        "title": "Built for institutional use",
        "body": "AEN is being shaped toward continuity, governance, accountability, and trusted deployment in schools, nonprofits, and public institutions."
    },
]
PORTAL_ARCHITECTURE_INTRO = (
    "AEN is not just one chatbot. Athena is the teaching interface. Evaluation keeps answers inspectable and aligned. SWARM is the orchestration layer for multi-step specialist workflows behind the interface."
)
PORTAL_ARCHITECTURE_CARDS = [
    {
        "kicker": "Athena",
        "title": "The learning interface",
        "body": "Athena is the public-facing tutor and reasoning partner inside AEN: warm, coherent, and designed to teach rather than simply output."
    },
    {
        "kicker": "Evaluation",
        "title": "The trust layer",
        "body": "Evaluation is where alignment, verification, curriculum discipline, and evidence-based checks live so outputs can be reviewed and trusted."
    },
    {
        "kicker": "SWARM",
        "title": "The orchestration layer",
        "body": "SWARM is where coordinated specialist workflows land: multi-pass reasoning, retrieval, tool use, and future institutional pipelines beyond a single response."
    },
]
PORTAL_MISSION_COPY = (
    "NeohmLabs is building AEN because intelligence should raise the floor of reasoning quality for students, teachers, nonprofits, and public institutions, not just generate impressive text."
)
PORTAL_MISSION_PARAGRAPHS = [
    "NeohmLabs is building AEN, the Artificial Evaluation Network, because the future of intelligence should serve learning, public reason, and institutional trust. AEN is designed as reasoning infrastructure rather than performance theater. Its purpose is to help people think with care, verify claims, improve decisions, and reach defensible conclusions where accuracy matters.",
    "This matters most where unequal access harms real people. Many students and teachers work without reliable tutoring, advanced coursework, or strong local support in mathematics and logic. NeohmLabs wants AEN to become part of that missing infrastructure so deep cognitive support can reach beyond wealth and geography.",
    "That is why the NeohmLabs mission has a nonprofit and public-benefit orientation. The goal is not to build a personality product and sell attention. The goal is to create durable reasoning support that schools, nonprofits, and public institutions can trust, inspect, and continue to use over time."
]
PORTAL_MISSION_POINTS = [
    "Expand access to deep educational support.",
    "Raise the floor of reasoning quality for students, teachers, nonprofits, and public institutions.",
    "Build systems that are transparent, verifiable, and durable enough to survive scrutiny.",
    "Treat intelligence as accountable infrastructure rather than spectacle."
]
PORTAL_INSTITUTION_COPY = (
    "Institution onboarding is the next layer of the system: .edu curation, SSO, curriculum memory, and later LMS-connected context for classrooms and academic programs."
)
PORTAL_INSTITUTION_POINTS = [
    "Institution sign-in is being staged for university and school rollout.",
    "Future .edu onboarding will support cleaner institutional identity and governance.",
    "Curriculum memory, course context, and LMS pathways can land here later without changing Athena's public teaching surface.",
    "The current portal is the release surface for tutoring, mathematics, and educator support."
]
PORTAL_PRIVACY_COPY = (
    "Your data is not sold. Bounded continuity memory and conversation data may be used to retrain models, improve Athena, and enhance user experience. You may request a copy of your data by emailing neohm@neohmlabs.com."
)
PORTAL_PRIVACY_POINTS = [
    "Data is not sold.",
    "Conversation data and bounded continuity memory may be used to retrain models and improve user experience.",
    "Per-user memory may retain recent turns, compact summaries, session focus, and relevant recall for continuity.",
    "You may request a copy of your stored data by emailing neohm@neohmlabs.com."
]
PORTAL_TERMS_COPY = (
    "Athena is an educational and productivity assistant offered through AEN. It can support coursework, planning, and institutional workflows, but it is not a substitute for instructor oversight, professional judgment, or independent verification in high-stakes settings."
)
PORTAL_TERMS_POINTS = [
    "By signing in, you agree to use the portal responsibly and to verify important outputs before acting on them.",
    "NeohmLabs is not liable for decisions, losses, or harm arising from misuse of the model or reliance on unverified output.",
    "Users remain responsible for compliance with course policy, institutional policy, law, and academic-integrity rules.",
    "Conversation data may be used for retraining, quality improvement, safety review, and user-experience enhancement.",
    "Future institutional integrations may provide additional curriculum context, but they do not remove user responsibility for review and verification."
]
PORTAL_SIGNIN_DISCLOSURE = "By signing in, you agree to the Terms and acknowledge the Privacy Notice."
PORTAL_INFO_PAGES: dict[str, dict[str, Any]] = {
    "aen": {
        "title": "AEN | Athena | NeohmLabs",
        "page_kicker": "AEN",
        "page_title": "Artificial Evaluation Network",
        "page_body": (
            "AEN is the larger reasoning architecture around Athena. It is designed so public-facing intelligence can be useful, inspectable, and durable in real educational settings."
        ),
        "page_paragraphs": [
            "Athena is not meant to stand alone as an isolated personality surface. She is part of AEN, where tutoring, explanation, and writing support sit inside a broader framework of evaluation, memory, and institutional trust.",
            "The purpose of AEN is to deliver unusually strong mathematics and tutoring performance while preserving reviewability. The ambition is not novelty for its own sake. The ambition is reasoning infrastructure that students, educators, nonprofits, and universities can actually use.",
            "That is why AEN emphasizes public benefit, mathematical seriousness, pedagogy, and the ability to grow into real institutional workflows over time.",
        ],
        "page_points": [
            "Athena is the conversational tutoring and explanation surface.",
            "Evaluation is the trust layer that keeps answers inspectable and reviewable.",
            "SWARM is the orchestration layer for multi-step and specialist workflows.",
            "The overall goal is durable public reasoning infrastructure, not disposable demo behavior.",
        ],
    },
    "swarm": {
        "title": "SWARM | Athena | NeohmLabs",
        "page_kicker": "SWARM",
        "page_title": "Where SWARM lands",
        "page_body": (
            "SWARM is the orchestration layer inside the larger architecture. It is where coordinated specialist workflows, multi-pass reasoning, and future tool-guided institutional pipelines belong."
        ),
        "page_paragraphs": [
            "Athena is the interface students and educators should feel. SWARM is what sits behind the interface when a task needs more than one direct response.",
            "In practice, SWARM is where multi-step decomposition, retrieval, evaluation passes, specialist coordination, and later institution-linked workflows can be staged cleanly.",
            "This separation matters because it keeps the public tutoring experience warm and simple while allowing the deeper system to scale in sophistication without cluttering the front door.",
        ],
        "page_points": [
            "SWARM is not the homepage experience; it is the backend orchestration layer.",
            "It supports multi-step reasoning and specialist coordination behind Athena.",
            "It creates a place for future retrieval, evaluation, and curriculum-connected flows.",
            "It helps keep the public portal simple while the architecture grows.",
        ],
    },
    "mission": {
        "title": "Mission | Athena | NeohmLabs",
        "page_kicker": "Mission",
        "page_title": "Why NeohmLabs is building AEN",
        "page_body": PORTAL_MISSION_COPY,
        "page_paragraphs": PORTAL_MISSION_PARAGRAPHS,
        "page_points": PORTAL_MISSION_POINTS,
    },
}
CHAT_RUNTIME_COPY = "Athena is ready for mathematics, tutoring, writing, and curriculum-aware support."
MIAMIOH_GOOGLE_DOMAIN = "miamioh.edu"
MIAMIOH_PILOT_INSTITUTION_KEY = "miamioh"
MIAMIOH_PILOT_COURSE_ID = "250433"
RECENT_TURN_PAIR_LIMIT = 8
SESSION_TURN_LOOKBACK = 4
SUMMARY_BATCH_TURNS = 6
SUMMARY_TIMEOUT_SECONDS = 180.0
SESSION_MEMORY_TIMEOUT_SECONDS = 90.0
EPISODIC_RECALL_LIMIT = 3
EPISODIC_RECALL_CANDIDATE_LIMIT = 120
MEMORY_SCHEMA_VERSION = "2.0"
MEMORY_STOPWORDS = {
    "about",
    "after",
    "also",
    "because",
    "been",
    "before",
    "being",
    "could",
    "from",
    "have",
    "into",
    "just",
    "more",
    "than",
    "that",
    "their",
    "them",
    "they",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}
MEMORY_IMPORTANCE_HINTS = (
    "prefer",
    "learn best",
    "step by step",
    "slowly",
    "example",
    "examples",
    "teacher",
    "student",
    "class",
    "course",
    "assignment",
    "exam",
    "institution",
    "goal",
    "working on",
    "remember",
    "help me understand",
    "misconception",
    "quiz",
    "review sheet",
)
PUBLIC_SUMMARY_SYSTEM_PROMPT = """You are a deterministic learner-profile summarizer for Athena, part of AEN.
Return JSON only. No markdown. No commentary.
Schema:
{
  \"summary\": \"short paragraph\",
  \"role\": \"student|educator|institutional_staff|general\",
  \"preferences\": [\"short item\"],
  \"goals\": [\"short item\"],
  \"institution_context\": [\"short item\"],
  \"teaching_preferences\": [\"short item\"],
  \"active_subjects\": [\"short item\"],
  \"active_courses\": [\"short item\"],
  \"misconceptions\": [\"short item\"],
  \"support_needs\": [\"short item\"],
  \"assessment_timeline\": [\"short item\"]
}
Rules:
- Keep only durable facts or preferences that help future educational assistance.
- Capture stable teaching or explanation preferences when the user shows them.
- Capture misconceptions or support needs only when they are recurring or educationally relevant.
- Do not invent.
- Omit highly sensitive, private, or one-off details unless the user clearly frames them as ongoing context.
- Keep the summary compact and useful.
"""
PUBLIC_SESSION_MEMORY_SYSTEM_PROMPT = """You are a deterministic session-memory updater for Athena, part of AEN.
Return JSON only. No markdown. No commentary.
Schema:
{
  \"current_focus\": \"short paragraph\",
  \"current_objective\": \"short paragraph\",
  \"teaching_preferences\": [\"short item\"],
  \"open_loops\": [\"short item\"],
  \"next_best_action\": \"short sentence\",
  \"recommended_assessment\": \"short sentence\"
}
Rules:
- Capture the active learning task, explanation style, and follow-up needs from the most recent turns.
- Keep it short-lived, compact, and directly useful for the next few prompts.
- Do not invent.
"""
CANVAS_API_TIMEOUT_SECONDS = 20.0
CANVAS_STATE_STALE_SECONDS = DEFAULT_CANVAS_STATE_STALE_SECONDS


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except Exception:
        return default
    return max(0, value)


def _load_env_file(file_path: Path) -> bool:
    if not file_path.exists():
        return False
    loaded = False
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        key = name.strip()
        if not key or key in os.environ:
            continue
        val = value.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        os.environ[key] = val
        loaded = True
    return loaded


def _bootstrap_portal_env() -> None:
    mode = (os.getenv("ATHENA_PORTAL_MODE") or "dev").strip().lower()
    auth_required = _env_bool("ATHENA_AUTH_REQUIRED", get_auth_required(mode))
    if not auth_required and mode != "prod":
        return
    candidates = [
        CONFIG_DIR / "portal_auth.env",
        PROJECT_ROOT / "portal_auth.env",
        ROOT / "portal_auth.env",
        CONFIG_DIR / ".env.portal",
        PROJECT_ROOT / ".env.portal",
        ROOT / ".env.portal",
        PROJECT_ROOT / ".env",
    ]
    for candidate in candidates:
        if _load_env_file(candidate):
            break


_bootstrap_portal_env()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_str_lines(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if text:
                items.append(text)
        return items
    return []


def _as_text_block(value: object) -> str:
    return "\n".join(_as_str_lines(value)).strip()


def _render_system_prompt_from_json(cfg_obj: dict[str, Any]) -> str:
    direct = cfg_obj.get("system_prompt")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    persona = cfg_obj.get("persona")
    if isinstance(persona, str) and persona.strip():
        chunks.append(persona.strip())

    for key, label in (
        ("core_behavior", "Core behavior:"),
        ("math_response_protocol", "Math response protocol:"),
        ("formatting_rules", "Formatting rules:"),
        ("default_mode", "Default mode:"),
    ):
        lines = _as_str_lines(cfg_obj.get(key))
        if not lines:
            continue
        chunks.append(label + "\n" + "\n".join(f"- {line}" for line in lines))

    for key in ("identity_prompt", "creator_contract", "creator contract", "custom_constraints_line"):
        extra = _as_text_block(cfg_obj.get(key))
        if extra:
            chunks.append(extra)

    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def _load_public_system_prompt_text() -> str:
    prompt_path = get_system_prompt_path(get_default_chat_model_dir())
    try:
        if prompt_path.suffix.lower() == ".json":
            raw = json.loads(prompt_path.read_text(encoding="utf-8-sig"))
            if isinstance(raw, dict):
                return _render_system_prompt_from_json(raw) or "You are Athena, part of AEN."
        text_value = prompt_path.read_text(encoding="utf-8-sig").strip()
        return text_value or "You are Athena, part of AEN."
    except Exception:
        return "You are Athena, part of AEN."


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    fallback: dict[str, Any] = {}
    string_patterns = {
        "summary": r'"?summar(?:y)?"?\s*:\s*"([^"]+)"',
        "role": r'"?role"?\s*:\s*"([^"]+)"',
        "current_focus": r'"?current(?:_| )?focus"?\s*:\s*"([^"]+)"',
        "current_objective": r'"?current(?:_| )?objective"?\s*:\s*"([^"]+)"',
        "next_best_action": r'"?next(?:_| )?best(?:_| )?action"?\s*:\s*"([^"]+)"',
        "recommended_assessment": r'"?recommended(?:_| )?assessment"?\s*:\s*"([^"]+)"',
    }
    list_patterns = {
        "preferences": r'"?preferences?"?\s*:?\s*\[([^\]]*)\]',
        "goals": r'"?goals?"?\s*:?\s*\[([^\]]*)\]',
        "institution_context": r'"?institution(?:_| )?context"?\s*:?\s*\[([^\]]*)\]',
        "teaching_preferences": r'"?teaching(?:_| )?preferences?"?\s*:?\s*\[([^\]]*)\]',
        "active_subjects": r'"?active(?:_| )?subjects?"?\s*:?\s*\[([^\]]*)\]',
        "active_courses": r'"?active(?:_| )?courses?"?\s*:?\s*\[([^\]]*)\]',
        "misconceptions": r'"?misconceptions?"?\s*:?\s*\[([^\]]*)\]',
        "support_needs": r'"?support(?:_| )?needs?"?\s*:?\s*\[([^\]]*)\]',
        "assessment_timeline": r'"?assessment(?:_| )?timeline"?\s*:?\s*\[([^\]]*)\]',
        "open_loops": r'"?open(?:_| )?loops?"?\s*:?\s*\[([^\]]*)\]',
    }

    for key, pattern in string_patterns.items():
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            fallback[key] = match.group(1).strip()
    for key, pattern in list_patterns.items():
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if not match:
            continue
        items = [_clean_summary_item(item) for item in match.group(1).split(",")]
        items = [item for item in items if item]
        if items:
            fallback[key] = items
    return fallback


def _clean_summary_item(value: object) -> str:
    text_value = str(value or "")
    text_value = text_value.replace(chr(92) + '"', '"')
    text_value = text_value.replace(chr(92), "")
    text_value = text_value.strip()
    text_value = text_value.strip('"')
    text_value = text_value.strip("'")
    return text_value


def _clean_summary_list(value: object, fallback: object = None) -> list[str]:
    source = value if value is not None else fallback
    items: list[str] = []
    for item in _as_str_lines(source):
        clean = _clean_summary_item(item)
        if clean and clean not in items:
            items.append(clean)
    return items[:8]


def _normalize_role(value: object, fallback: object = None) -> str:
    raw = str(value or fallback or "").strip().lower()
    allowed = {"student", "educator", "institutional_staff", "general"}
    return raw if raw in allowed else ""


def _clean_scalar_text(value: object, fallback: object = None, *, limit: int = 240) -> str:
    raw = str(value if value is not None else fallback or "")
    raw = raw.replace(chr(92) + '"', '"').replace(chr(92), "")
    compact = re.sub(r"\s+", " ", raw).strip().strip('"').strip("'")
    if len(compact) <= limit:
        return compact
    if limit <= 3:
        return compact[:limit]
    return compact[: limit - 3].rstrip() + "..."


def _normalize_curriculum_context(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "institution_name": _clean_scalar_text(raw.get("institution_name")),
        "role_context": _clean_scalar_text(raw.get("role_context")),
        "current_course": _clean_scalar_text(raw.get("current_course")),
        "current_unit": _clean_scalar_text(raw.get("current_unit")),
        "allowed_methods": _clean_summary_list(raw.get("allowed_methods")),
        "restricted_help": _clean_summary_list(raw.get("restricted_help")),
        "assessment_style": _clean_summary_list(raw.get("assessment_style")),
        "notes": _clean_summary_list(raw.get("notes")),
        "updated_at": _clean_scalar_text(raw.get("updated_at"), _utc_now_iso()),
    }


def _normalize_profile_record(raw: dict[str, Any] | None, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}
    return {
        "email": _clean_scalar_text(raw.get("email"), fallback.get("email"), limit=180),
        "name": _clean_scalar_text(raw.get("name"), fallback.get("name"), limit=180),
        "picture": _clean_scalar_text(raw.get("picture"), fallback.get("picture"), limit=400),
        "sub": _clean_scalar_text(raw.get("sub"), fallback.get("sub"), limit=200),
        "auth_source": _clean_scalar_text(raw.get("auth_source"), fallback.get("auth_source"), limit=80),
        "institution_key": _clean_scalar_text(raw.get("institution_key"), fallback.get("institution_key"), limit=64),
        "institution_name": _clean_scalar_text(raw.get("institution_name"), fallback.get("institution_name"), limit=180),
        "institution_role": _clean_scalar_text(raw.get("institution_role"), fallback.get("institution_role"), limit=120),
        "course_role": _clean_scalar_text(raw.get("course_role"), fallback.get("course_role"), limit=120),
        "role_source": _clean_scalar_text(raw.get("role_source"), fallback.get("role_source"), limit=120),
        "canvas_domain": _clean_scalar_text(raw.get("canvas_domain"), fallback.get("canvas_domain"), limit=180),
        "canvas_user_id": _clean_scalar_text(raw.get("canvas_user_id"), fallback.get("canvas_user_id"), limit=64),
        "last_canvas_sync_at": _clean_scalar_text(raw.get("last_canvas_sync_at"), fallback.get("last_canvas_sync_at"), limit=80),
        "created_at_utc": _clean_scalar_text(raw.get("created_at_utc"), fallback.get("created_at_utc") or _utc_now_iso(), limit=80),
        "updated_at_utc": _clean_scalar_text(raw.get("updated_at_utc"), fallback.get("updated_at_utc") or _utc_now_iso(), limit=80),
    }


def _normalize_canvas_token_record(raw: dict[str, Any] | None, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}
    return {
        "access_token": _clean_scalar_text(raw.get("access_token"), fallback.get("access_token"), limit=6000),
        "refresh_token": _clean_scalar_text(raw.get("refresh_token"), fallback.get("refresh_token"), limit=6000),
        "token_type": _clean_scalar_text(raw.get("token_type"), fallback.get("token_type"), limit=80),
        "scope": _clean_scalar_text(raw.get("scope"), fallback.get("scope"), limit=600),
        "expires_at": _clean_scalar_text(raw.get("expires_at"), fallback.get("expires_at"), limit=80),
        "updated_at": _clean_scalar_text(raw.get("updated_at"), fallback.get("updated_at") or _utc_now_iso(), limit=80),
    }


def _curriculum_has_content(record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return False
    return bool(
        record.get("institution_name")
        or record.get("role_context")
        or record.get("current_course")
        or record.get("current_unit")
        or record.get("allowed_methods")
        or record.get("restricted_help")
        or record.get("assessment_style")
        or record.get("notes")
    )


def _authenticated_profile_has_content(record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return False
    return bool(
        record.get("email")
        or record.get("name")
        or record.get("auth_source")
        or record.get("institution_name")
        or record.get("institution_role")
        or record.get("course_role")
    )


def _normalize_summary_record(
    raw: dict[str, Any] | None,
    *,
    fallback: dict[str, Any] | None = None,
    source_turn_count: int | None = None,
) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}
    summary = _clean_scalar_text(raw.get("summary"), fallback.get("summary"), limit=420)
    return {
        "summary": summary,
        "role": _normalize_role(raw.get("role"), fallback.get("role")),
        "preferences": _clean_summary_list(raw.get("preferences"), fallback.get("preferences")),
        "goals": _clean_summary_list(raw.get("goals"), fallback.get("goals")),
        "institution_context": _clean_summary_list(raw.get("institution_context"), fallback.get("institution_context")),
        "teaching_preferences": _clean_summary_list(raw.get("teaching_preferences"), fallback.get("teaching_preferences")),
        "active_subjects": _clean_summary_list(raw.get("active_subjects"), fallback.get("active_subjects")),
        "active_courses": _clean_summary_list(raw.get("active_courses"), fallback.get("active_courses")),
        "misconceptions": _clean_summary_list(raw.get("misconceptions"), fallback.get("misconceptions")),
        "support_needs": _clean_summary_list(raw.get("support_needs"), fallback.get("support_needs")),
        "assessment_timeline": _clean_summary_list(raw.get("assessment_timeline"), fallback.get("assessment_timeline")),
        "updated_at": _clean_scalar_text(raw.get("updated_at"), fallback.get("updated_at") or _utc_now_iso()),
        "source_turn_count": max(0, int(source_turn_count if source_turn_count is not None else raw.get("source_turn_count") or fallback.get("source_turn_count") or 0)),
    }


def _normalize_session_record(
    raw: dict[str, Any] | None,
    *,
    fallback: dict[str, Any] | None = None,
    source_turn_count: int | None = None,
) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}
    return {
        "current_focus": _clean_scalar_text(raw.get("current_focus"), fallback.get("current_focus"), limit=320),
        "current_objective": _clean_scalar_text(raw.get("current_objective"), fallback.get("current_objective"), limit=220),
        "teaching_preferences": _clean_summary_list(raw.get("teaching_preferences"), fallback.get("teaching_preferences")),
        "open_loops": _clean_summary_list(raw.get("open_loops"), fallback.get("open_loops")),
        "next_best_action": _clean_scalar_text(raw.get("next_best_action"), fallback.get("next_best_action"), limit=180),
        "recommended_assessment": _clean_scalar_text(raw.get("recommended_assessment"), fallback.get("recommended_assessment"), limit=180),
        "updated_at": _clean_scalar_text(raw.get("updated_at"), fallback.get("updated_at") or _utc_now_iso()),
        "source_turn_count": max(0, int(source_turn_count if source_turn_count is not None else raw.get("source_turn_count") or fallback.get("source_turn_count") or 0)),
    }


def _summary_has_content(record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return False
    return bool(
        str(record.get("summary") or "").strip()
        or record.get("role")
        or record.get("preferences")
        or record.get("goals")
        or record.get("institution_context")
        or record.get("teaching_preferences")
        or record.get("active_subjects")
        or record.get("active_courses")
        or record.get("misconceptions")
        or record.get("support_needs")
        or record.get("assessment_timeline")
    )


def _session_has_content(record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return False
    return bool(
        str(record.get("current_focus") or "").strip()
        or str(record.get("current_objective") or "").strip()
        or record.get("teaching_preferences")
        or record.get("open_loops")
        or str(record.get("next_best_action") or "").strip()
        or str(record.get("recommended_assessment") or "").strip()
    )


def _clip_memory_text(value: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(compact) <= limit:
        return compact
    if limit <= 3:
        return compact[:limit]
    return compact[: limit - 3].rstrip() + "..."


def _compose_memory_system_prompt(
    base_prompt: str,
    summary_record: dict[str, Any] | None,
    session_record: dict[str, Any] | None = None,
    recalled_turns: Sequence[dict[str, str]] | None = None,
    curriculum_context: dict[str, Any] | None = None,
    course_guide_lines: Sequence[str] | None = None,
    canvas_summary_lines: Sequence[str] | None = None,
    retrieved_chunks: Sequence[dict[str, Any]] | None = None,
    authenticated_profile: dict[str, Any] | None = None,
) -> str:
    recalled_turns = list(recalled_turns or [])
    course_guide_lines = [str(line).strip() for line in (course_guide_lines or []) if str(line).strip()]
    canvas_summary_lines = [str(line).strip() for line in (canvas_summary_lines or []) if str(line).strip()]
    retrieved_chunks = [chunk for chunk in (retrieved_chunks or []) if isinstance(chunk, dict)]
    authenticated_profile = _normalize_profile_record(authenticated_profile)
    if (
        not _summary_has_content(summary_record)
        and not _session_has_content(session_record)
        and not recalled_turns
        and not _curriculum_has_content(curriculum_context)
        and not course_guide_lines
        and not canvas_summary_lines
        and not retrieved_chunks
        and not _authenticated_profile_has_content(authenticated_profile)
    ):
        return base_prompt

    lines = [
        base_prompt.strip(),
        "",
        "Conversation continuity memory for this user.",
        "Use it only as helpful context. Do not mention memory unless it is directly relevant.",
        "When helpful, adapt explanation depth, pacing, examples, and formative checks to the user's remembered preferences and role.",
        "Do not restate authenticated identity facts, course metadata, or pilot notes unless the user asks for them or they are necessary to answer correctly.",
        "When the user asks about their own name or role, answer with the authenticated facts exactly as stored. Do not speculate, hedge, or mention spelling variation unless the stored facts disagree.",
        "When the course guide provides an exact assessment name or date, copy it exactly rather than paraphrasing it.",
    ]

    curriculum_context = _normalize_curriculum_context(curriculum_context)
    if _curriculum_has_content(curriculum_context):
        lines.append("Institutional or curriculum context:")
        if curriculum_context.get("institution_name"):
            lines.append(f"- Institution: {curriculum_context['institution_name']}")
        if curriculum_context.get("role_context"):
            lines.append(f"- Role context: {curriculum_context['role_context']}")
        if curriculum_context.get("current_course"):
            lines.append(f"- Current course: {curriculum_context['current_course']}")
        if curriculum_context.get("current_unit"):
            lines.append(f"- Current unit: {curriculum_context['current_unit']}")
        if curriculum_context.get("allowed_methods"):
            lines.append("- Allowed methods: " + "; ".join(curriculum_context["allowed_methods"]))
        if curriculum_context.get("restricted_help"):
            lines.append("- Restricted help: " + "; ".join(curriculum_context["restricted_help"]))
        if curriculum_context.get("assessment_style"):
            lines.append("- Assessment style: " + "; ".join(curriculum_context["assessment_style"]))
        if curriculum_context.get("notes"):
            lines.append("- Notes: " + "; ".join(curriculum_context["notes"]))

    if course_guide_lines:
        lines.append("Course guide context:")
        for line in course_guide_lines[:6]:
            lines.append(f"- {line}")

    if canvas_summary_lines:
        lines.append("Live Canvas context:")
        for line in canvas_summary_lines[:6]:
            lines.append(f"- {line}")

    if _authenticated_profile_has_content(authenticated_profile):
        lines.append("Authenticated session identity:")
        if authenticated_profile.get("name"):
            lines.append(f"- Display name: {authenticated_profile['name']}")
        if authenticated_profile.get("email"):
            lines.append(f"- Signed-in email: {authenticated_profile['email']}")
        if authenticated_profile.get("auth_source"):
            lines.append(f"- Auth source: {authenticated_profile['auth_source']}")
        if authenticated_profile.get("institution_name"):
            lines.append(f"- Institution: {authenticated_profile['institution_name']}")
        if authenticated_profile.get("institution_role"):
            lines.append(f"- Institution role: {authenticated_profile['institution_role']}")
        if authenticated_profile.get("course_role"):
            lines.append(f"- Current course role: {authenticated_profile['course_role']}")
        if authenticated_profile.get("role_source"):
            lines.append(f"- Role source: {authenticated_profile['role_source']}")
        lines.append("- Treat this authenticated identity context as reliable when the user asks about their own name or role in the current session.")

    summary_record = summary_record or {}
    if _summary_has_content(summary_record):
        lines.append("Durable learner profile:")
        role = str(summary_record.get("role") or "").strip()
        if role:
            lines.append(f"- Role: {role}")
        summary = str(summary_record.get("summary") or "").strip()
        if summary:
            lines.append(f"- Summary: {summary}")
        active_subjects = _clean_summary_list(summary_record.get("active_subjects"))
        if active_subjects:
            lines.append("- Active subjects: " + "; ".join(active_subjects))
        active_courses = _clean_summary_list(summary_record.get("active_courses"))
        if active_courses:
            lines.append("- Active courses: " + "; ".join(active_courses))
        goals = _clean_summary_list(summary_record.get("goals"))
        if goals:
            lines.append("- Goals: " + "; ".join(goals))
        support_needs = _clean_summary_list(summary_record.get("support_needs"))
        if support_needs:
            lines.append("- Support needs: " + "; ".join(support_needs))
        misconceptions = _clean_summary_list(summary_record.get("misconceptions"))
        if misconceptions:
            lines.append("- Misconceptions or sticking points: " + "; ".join(misconceptions))
        assessment_timeline = _clean_summary_list(summary_record.get("assessment_timeline"))
        if assessment_timeline:
            lines.append("- Assessment timeline: " + "; ".join(assessment_timeline))
        preferences = _clean_summary_list(summary_record.get("preferences"))
        if preferences:
            lines.append("- Preferences: " + "; ".join(preferences))
        institution_context = _clean_summary_list(summary_record.get("institution_context"))
        if institution_context:
            lines.append("- Institution context: " + "; ".join(institution_context))
        teaching_preferences = _clean_summary_list(summary_record.get("teaching_preferences"))
        if teaching_preferences:
            lines.append("- Teaching preferences: " + "; ".join(teaching_preferences))

    session_record = session_record or {}
    if _session_has_content(session_record):
        lines.append("Current session focus:")
        current_focus = str(session_record.get("current_focus") or "").strip()
        if current_focus:
            lines.append(f"- Current focus: {current_focus}")
        current_objective = str(session_record.get("current_objective") or "").strip()
        if current_objective:
            lines.append(f"- Current objective: {current_objective}")
        session_teaching = _clean_summary_list(session_record.get("teaching_preferences"))
        if session_teaching:
            lines.append("- Active teaching preferences: " + "; ".join(session_teaching))
        next_best_action = str(session_record.get("next_best_action") or "").strip()
        if next_best_action:
            lines.append(f"- Next best action: {next_best_action}")
        recommended_assessment = str(session_record.get("recommended_assessment") or "").strip()
        if recommended_assessment:
            lines.append(f"- Recommended assessment: {recommended_assessment}")
        open_loops = _clean_summary_list(session_record.get("open_loops"))
        if open_loops:
            lines.append("- Open loops: " + "; ".join(open_loops))

    if retrieved_chunks:
        lines.append("Relevant institution or course bundle excerpts:")
        for chunk in retrieved_chunks[:4]:
            title = _clean_scalar_text(chunk.get("title"), limit=140) or "Course content"
            source_type = _clean_scalar_text(chunk.get("source_type"), limit=80)
            excerpt = _clip_memory_text(_clean_scalar_text(chunk.get("text"), limit=900), 360)
            label = title if not source_type else f"{title} [{source_type}]"
            if excerpt:
                lines.append(f"- {label}: {excerpt}")

    if recalled_turns:
        lines.append("Relevant earlier conversation snippets for the current request:")
        for idx, turn in enumerate(recalled_turns, start=1):
            user_text = _clip_memory_text(str(turn.get("user") or ""), 220)
            assistant_text = _clip_memory_text(str(turn.get("assistant") or ""), 280)
            if user_text:
                lines.append(f"{idx}. User: {user_text}")
            if assistant_text:
                lines.append(f"   Assistant: {assistant_text}")

    return "\n".join(line for line in lines if line).strip()


def _history_messages_from_turns(turns: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for turn in turns:
        user_text = str(turn.get("user") or "").strip()
        assistant_text = str(turn.get("assistant") or "").strip()
        if not user_text or not assistant_text:
            continue
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": assistant_text})
    return messages


def _serialize_turns_for_summary(turns: Sequence[dict[str, str]]) -> str:
    chunks: list[str] = []
    for idx, turn in enumerate(turns, start=1):
        user_text = str(turn.get("user") or "").strip()
        assistant_text = str(turn.get("assistant") or "").strip()
        if not user_text and not assistant_text:
            continue
        chunks.append(f"Turn {idx}\nUser: {user_text}\nAssistant: {assistant_text}")
    return "\n\n".join(chunks).strip()


def _tokenize_memory_text(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9_-]{2,}", str(text or "").lower())
    return [token for token in tokens if token not in MEMORY_STOPWORDS]


def _importance_hint_score(text: str) -> float:
    lowered = str(text or "").lower()
    score = 0.0
    for hint in MEMORY_IMPORTANCE_HINTS:
        if hint in lowered:
            score += 0.2
    return min(score, 1.6)


def _run_memory_completion(
    engine_obj: DesktopEngine,
    prompt: str,
    *,
    system_prompt: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    session = engine_obj.create_session()
    terminal = Event()
    result: dict[str, str] = {"assistant": "", "error": ""}

    def on_event(event: EngineEvent) -> None:
        if event.type == "turn_done":
            result["assistant"] = event.assistant
            terminal.set()
        elif event.type == "turn_error":
            result["error"] = event.message
            terminal.set()

    try:
        session.submit_turn(prompt, listener=on_event, system_prompt_override=system_prompt)
        if not terminal.wait(timeout_seconds):
            return {}
    except Exception:
        return {}

    if result["error"]:
        return {}
    return _extract_json_object(result["assistant"])


def _extract_turn_context(prompt: str) -> dict[str, Any]:
    raw = str(prompt or "")
    lowered = raw.lower()
    course_codes = []
    for match in re.finditer(r"\b([A-Z]{2,6}\s?-?\d{3}[A-Z]?)\b", raw):
        code = re.sub(r"\s+", " ", match.group(1).strip())
        if code not in course_codes:
            course_codes.append(code)

    role = ""
    educator_signals = ("my students", "my class", "i teach", "lesson opener", "exit ticket", "review sheet", "as instructor", "professor")
    student_signals = ("i am learning", "help me understand", "my homework", "my exam", "i am studying", "teach me")
    if any(signal in lowered for signal in educator_signals):
        role = "educator"
    elif any(signal in lowered for signal in student_signals):
        role = "student"

    intent = ""
    if any(signal in lowered for signal in ("lesson opener", "exit ticket", "review sheet", "practice set", "quiz", "lesson plan")):
        intent = "educator_artifact"
    elif any(signal in lowered for signal in ("teach me", "help me understand", "hint", "step by step", "dont give the full answer", "don't give the full answer")):
        intent = "guided_tutoring"

    return {
        "course_codes": course_codes,
        "role": role,
        "intent": intent,
    }


def _compose_turn_context_block(prompt: str) -> str:
    ctx = _extract_turn_context(prompt)
    lines: list[str] = []
    if ctx.get("course_codes"):
        lines.append("Explicit current-turn context:")
        lines.append("- Preserve the exact course code(s) given by the user: " + "; ".join(ctx["course_codes"]))
        lines.append("- Do not speculate about alternate course codes or rename the course unless the user asks.")
    if ctx.get("role"):
        if not lines:
            lines.append("Explicit current-turn context:")
        lines.append(f"- The user is speaking as: {ctx['role']}")
    if ctx.get("intent"):
        if not lines:
            lines.append("Explicit current-turn context:")
        if ctx["intent"] == "educator_artifact":
            lines.append("- Treat this as an educator-facing artifact request. Keep the output classroom-ready, aligned to the stated course context, and immediately usable.")
        elif ctx["intent"] == "guided_tutoring":
            lines.append("- Treat this as guided tutoring. Favor scaffolding, a hint ladder, one worked example when useful, and a brief comprehension check near the end.")
    return "\n".join(lines).strip()


def _normalize_course_aliases(text: str, canonical_code: str) -> str:
    if not text or not canonical_code:
        return text
    prefix_match = re.match(r"^([A-Z]{2,6})\s?-?(\d{3}[A-Z]?)$", canonical_code)
    if not prefix_match:
        return text
    subject = prefix_match.group(1)
    normalized = text
    range_pattern = re.compile(rf"\b{re.escape(subject)}\s*\d{{3}}[A-Z]?\s*[\-\u2013]\s*\d{{3}}[A-Z]?\b")
    generic_pattern = re.compile(rf"\b{re.escape(subject)}\s*\dxx\b", flags=re.IGNORECASE)
    low_level_pattern = re.compile(rf"\b{re.escape(subject)}\s*0\d{{2}}[A-Z]?\b")
    normalized = range_pattern.sub(canonical_code, normalized)
    normalized = generic_pattern.sub(canonical_code, normalized)
    for match in list(low_level_pattern.finditer(normalized)):
        found = re.sub(r"\s+", " ", match.group(0).strip()).upper()
        if found != canonical_code.upper():
            normalized = re.sub(rf"\b{re.escape(match.group(0))}\b", canonical_code, normalized)
    return normalized


def _enforce_public_output_contract(prompt: str, assistant_text: str) -> str:
    text = str(assistant_text or "").strip()
    if not text:
        return text

    ctx = _extract_turn_context(prompt)
    course_codes = list(ctx.get("course_codes") or [])
    if len(course_codes) == 1:
        canonical_code = course_codes[0]
        detected = []
        for match in re.finditer(r"\b([A-Z]{2,6}\s?-?\d{3}[A-Z]?)\b", text):
            code = re.sub(r"\s+", " ", match.group(1).strip())
            if code not in detected:
                detected.append(code)
        mismatched = [code for code in detected if code != canonical_code]
        for code in mismatched:
            text = re.sub(rf"\b{re.escape(code)}\b", canonical_code, text)
        text = _normalize_course_aliases(text, canonical_code)
        text = re.sub(rf"{re.escape(canonical_code)}(?:\s*/\s*{re.escape(canonical_code.split()[-1])})+", canonical_code, text)
        if canonical_code not in text:
            text = f"Course context: {canonical_code}.\n\n{text}"

    lowered_prompt = str(prompt or "").lower()
    wants_exit_ticket = "exit ticket" in lowered_prompt
    asks_for_check = any(token in lowered_prompt for token in ("quick check", "check question", "check my understanding", "exit ticket"))
    if wants_exit_ticket and "exit ticket" not in text.lower():
        text = text.rstrip() + "\n\nExit ticket:\n1. What two integers would students test first when factoring a quadratic like x^2 + 7x + 12?\n2. How can they check whether their factorization is correct?\n3. What common sign mistake should they watch for when the middle term is negative?"
    elif asks_for_check:
        tail = text[-400:].lower()
        has_question_near_end = "?" in tail or "quick check" in tail or "exit ticket" in tail
        if not has_question_near_end:
            text = text.rstrip() + "\n\nQuick check: What would you try next on a similar problem, and why?"

    return text


def _parse_iso_datetime(value: object) -> datetime | None:
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


def _identity_query_flags(query: str) -> tuple[bool, bool]:
    lowered = str(query or "").strip().lower()
    asks_name = bool(
        re.search(r"\b(who am i|what(?:'s| is) my name|tell me my name|do you know my name)\b", lowered)
    )
    asks_role = bool(
        re.search(
            r"\b(what(?:'s| is) my (?:position|role)|am i (?:an|a) (?:instructor|teacher|student|ta|teaching assistant)|what is my position)\b",
            lowered,
        )
    )
    return asks_name, asks_role


def _pilot_context_for_user(user_email: str) -> tuple[dict[str, Any], InstitutionRecord | None, list[str], dict[str, Any], dict[str, Any]]:
    profile = logs.load_profile(user_email)
    institution = institutions.get(profile.get("institution_key"))
    canvas_state = logs.load_canvas_state(user_email)
    course_ids = extract_relevant_course_ids(canvas_state)
    if (
        not course_ids
        and institution is not None
        and profile.get("auth_source") == "google"
        and institution.institution_key == MIAMIOH_PILOT_INSTITUTION_KEY
    ):
        course_ids = list(institution.mapped_course_ids or (MIAMIOH_PILOT_COURSE_ID,))
    course_payload = load_bundle_course_json(institution, course_ids[0], "course.json") if institution is not None and course_ids else {}
    pilot_payload = load_bundle_course_json(institution, course_ids[0], "pilot_overrides.json") if institution is not None and course_ids else {}
    return profile, institution, course_ids, course_payload, pilot_payload


def _assessment_query_target(query: str) -> tuple[str, str] | None:
    lowered = str(query or "").lower()
    if not lowered.strip():
        return None
    if re.search(r"\b(next exam|next scheduled exam)\b", lowered):
        return ("next_exam", "")
    if re.search(r"\b(next quiz|next scheduled quiz)\b", lowered):
        return ("next_quiz", "")
    if "final" in lowered:
        return ("final", "")
    match = re.search(r"\b(quiz|exam|test|midterm)\s*#?\s*(\d{1,2})\b", lowered)
    if not match:
        return None
    kind = match.group(1)
    if kind == "test":
        kind = "exam"
    return (kind, match.group(2))


def _future_assessment_row(assessments: list[dict[str, Any]], *, want: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for item in assessments:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        if want == "next_exam" and not any(token in name for token in ("exam", "final", "midterm", "test")):
            continue
        if want == "next_quiz" and "quiz" not in name:
            continue
        parsed = _parse_iso_datetime(item.get("start_at")) or _parse_iso_datetime(item.get("end_at"))
        if parsed is None or parsed < now:
            continue
        candidates.append((parsed, item))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def _matching_assessment_for_query(pilot_payload: dict[str, Any], query: str) -> dict[str, Any] | None:
    assessments = [item for item in (pilot_payload.get("assessment_calendar") or []) if isinstance(item, dict)]
    target = _assessment_query_target(query)
    if target is None:
        return None
    kind, number = target
    if kind in {"next_exam", "next_quiz"}:
        return _future_assessment_row(assessments, want=kind)
    if kind == "final":
        return next((item for item in assessments if "final" in str(item.get("name") or "").lower()), None)
    for item in assessments:
        name = str(item.get("name") or "").strip().lower()
        if kind not in name:
            continue
        if re.search(rf"#\s*{re.escape(number)}\b", name) or re.search(rf"\b{re.escape(number)}\b", name):
            return item
    return None


def _grounded_identity_response(user_email: str, query: str) -> str | None:
    asks_name, asks_role = _identity_query_flags(query)
    if not asks_name and not asks_role:
        return None
    profile, _, _, _, _ = _pilot_context_for_user(user_email)
    name = str(profile.get("name") or "").strip()
    course_role = str(profile.get("course_role") or "").strip()
    institution_role = str(profile.get("institution_role") or "").strip()
    institution_name = str(profile.get("institution_name") or "").strip()
    lines: list[str] = []
    if asks_name and name:
        lines.append(f"Your name is {name}.")
    if asks_role:
        if course_role:
            lines.append(f"Your current role is {course_role}.")
        elif institution_role and institution_name:
            lines.append(f"Your current role is {institution_role} at {institution_name}.")
        elif institution_role:
            lines.append(f"Your current role is {institution_role}.")
    return "\n\n".join(lines).strip() or None


def _grounded_schedule_response(user_email: str, query: str) -> str | None:
    if not is_schedule_query(query):
        return None
    profile, institution, course_ids, course_payload, pilot_payload = _pilot_context_for_user(user_email)
    if institution is None or not course_ids or not isinstance(pilot_payload, dict) or not pilot_payload:
        return None
    matched = _matching_assessment_for_query(pilot_payload, query)
    if matched is None:
        return None
    course_name = str(course_payload.get("course_name") or pilot_payload.get("course_title") or "this course").strip()
    name = str(matched.get("name") or "Assessment").strip()
    date_text = str(matched.get("date_text") or "").strip()
    topics = str(matched.get("topics") or "").strip()
    if not date_text:
        return None
    lines = [f"According to the current course guide for {course_name}, {name} is on {date_text}."]
    if topics:
        lines.append(f"Topics: {topics}.")
    if "final" in name.lower():
        final_slot = str(pilot_payload.get("final_exam_slot") or "").strip()
        if final_slot and final_slot not in date_text:
            lines.append(final_slot)
    if str(profile.get("course_role") or "").strip().lower().startswith("instructor"):
        lines.append("If you want, I can turn that into a quick review sheet, instructor note, or lesson opener.")
    else:
        lines.append("If you want, I can help you study for it next.")
    return "\n\n".join(lines).strip()


def _maybe_grounded_public_response(user_email: str, query: str) -> str | None:
    identity = _grounded_identity_response(user_email, query)
    if identity:
        return identity
    schedule = _grounded_schedule_response(user_email, query)
    if schedule:
        return schedule
    return None


def _grounded_turn_payload(
    *,
    request_id: str,
    assistant: str,
    server_history: Sequence[dict[str, str]],
    user_content: str,
    user_label: str,
    model_loaded: bool,
) -> dict[str, Any]:
    normalized_assistant = str(assistant or "").strip()
    history = [dict(item) for item in server_history if isinstance(item, dict)]
    history.append({"role": "user", "content": user_content})
    history.append({"role": "assistant", "content": normalized_assistant})
    return {
        "type": "turn_done",
        "request_id": request_id,
        "assistant": normalized_assistant,
        "history": history,
        "visible_messages": history,
        "transcript_html": render_transcript_html(history, user_label=user_label),
        "model_loaded": model_loaded,
    }


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


def _provider_label(provider_key: str) -> str:
    key = (provider_key or "").strip().lower()
    institution = institutions.get(key) if "institutions" in globals() else None
    if institution is not None:
        return institution.label
    if key == "github":
        return "GitHub"
    if key == "google":
        return "Google"
    return key or "Institution"


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
    auth_provider: str
    default_institution_key: str
    guest_login_enabled: bool
    guest_prompt_limit: int
    google_client_id: str
    google_client_secret: str
    github_client_id: str
    github_client_secret: str
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
            auth_provider=((os.getenv("ATHENA_AUTH_PROVIDER") or "google").strip().lower() or "google"),
            default_institution_key=((os.getenv("ATHENA_DEFAULT_INSTITUTION") or "miamioh").strip().lower() or "miamioh"),
            guest_login_enabled=_env_bool("ATHENA_GUEST_LOGIN_ENABLED", True),
            guest_prompt_limit=_env_int("ATHENA_GUEST_PROMPT_LIMIT", 0),
            google_client_id=(os.getenv("ATHENA_GOOGLE_CLIENT_ID") or "").strip(),
            google_client_secret=(os.getenv("ATHENA_GOOGLE_CLIENT_SECRET") or "").strip(),
            github_client_id=(os.getenv("ATHENA_GITHUB_CLIENT_ID") or "").strip(),
            github_client_secret=(os.getenv("ATHENA_GITHUB_CLIENT_SECRET") or "").strip(),
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
    request_id: str = Field(default="", max_length=128)
    prompt: str = Field(default="", max_length=12000)
    history: list[ChatMessage] = Field(default_factory=list)
    images: list[ChatImage] = Field(default_factory=list)


class ChatControlRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)


class UserLogStore:
    def __init__(self, root: Path):
        self.root = root
        self._lock = Lock()
        self._memory_index_lock = Lock()
        self._memory_locks: dict[str, Lock] = {}

    def user_key(self, email: str) -> str:
        return _normalize_user_key(email)

    def _user_dir(self, email: str) -> Path:
        return self.root / self.user_key(email)

    def _session_dir(self, email: str) -> Path:
        return self._user_dir(email) / "sessions"

    def _error_dir(self, email: str) -> Path:
        return self._user_dir(email) / "errors"

    def _memory_dir(self, email: str) -> Path:
        return self._user_dir(email) / "memory"

    def _session_file(self, email: str) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._session_dir(email) / f"{day}.ndjson"

    def _error_file(self, email: str) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._error_dir(email) / f"{day}.ndjson"

    def _summary_file(self, email: str) -> Path:
        return self._memory_dir(email) / "summary.json"

    def _session_memory_file(self, email: str) -> Path:
        return self._memory_dir(email) / "session.json"

    def _curriculum_context_file(self, email: str) -> Path:
        return self._memory_dir(email) / "curriculum_context.json"

    def _canvas_state_file(self, email: str) -> Path:
        return self._memory_dir(email) / "canvas_state.json"

    def _canvas_token_file(self, email: str) -> Path:
        return self._memory_dir(email) / "canvas_tokens.json"

    def _profile_file(self, email: str) -> Path:
        return self._user_dir(email) / "profile.json"

    def _memory_guard(self, email: str) -> Lock:
        key = self.user_key(email)
        with self._memory_index_lock:
            guard = self._memory_locks.get(key)
            if guard is None:
                guard = Lock()
                self._memory_locks[key] = guard
            return guard

    def ensure_profile(self, user: dict[str, Any]) -> None:
        email = str(user.get("email") or "anonymous@dev")
        user_dir = self._user_dir(email)
        self._session_dir(email).mkdir(parents=True, exist_ok=True)
        self._error_dir(email).mkdir(parents=True, exist_ok=True)
        self._memory_dir(email).mkdir(parents=True, exist_ok=True)
        profile = self.load_profile(email)
        merged = _normalize_profile_record(
            {
                "email": user.get("email"),
                "name": user.get("name"),
                "picture": user.get("picture"),
                "sub": user.get("sub"),
                "auth_source": user.get("auth_source"),
                "institution_key": user.get("institution_key"),
                "institution_name": user.get("institution_name"),
                "institution_role": user.get("institution_role"),
                "course_role": user.get("course_role"),
                "role_source": user.get("role_source"),
                "canvas_domain": user.get("canvas_domain"),
                "canvas_user_id": user.get("canvas_user_id"),
                "last_canvas_sync_at": user.get("last_canvas_sync_at"),
                "created_at_utc": profile.get("created_at_utc") or _utc_now_iso(),
                "updated_at_utc": _utc_now_iso(),
            },
            fallback=profile,
        )
        self.save_profile(email, merged)
        if not self._curriculum_context_file(email).exists():
            self.save_curriculum_context(email, {})
        if not self._canvas_state_file(email).exists():
            self.save_canvas_state(email, {})

    def load_profile(self, user_email: str) -> dict[str, Any]:
        path = self._profile_file(user_email)
        if not path.exists():
            return _normalize_profile_record({})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _normalize_profile_record({})
        return _normalize_profile_record(raw)

    def save_profile(self, user_email: str, profile: dict[str, Any]) -> None:
        path = self._profile_file(user_email)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _normalize_profile_record(profile, fallback=self.load_profile(user_email) if path.exists() else {})
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def log_event(self, user_email: str, event: dict[str, Any], *, error_log: bool = False) -> None:
        with self._lock:
            target = self._error_file(user_email) if error_log else self._session_file(user_email)
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = dict(event)
            payload.setdefault("ts_utc", _utc_now_iso())
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def load_summary(self, user_email: str) -> dict[str, Any]:
        path = self._summary_file(user_email)
        if not path.exists():
            return _normalize_summary_record({}, source_turn_count=0)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _normalize_summary_record({}, source_turn_count=0)
        return _normalize_summary_record(raw)

    def save_summary(self, user_email: str, summary: dict[str, Any]) -> None:
        path = self._summary_file(user_email)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_normalize_summary_record(summary), ensure_ascii=False, indent=2), encoding="utf-8")

    def load_session_memory(self, user_email: str) -> dict[str, Any]:
        path = self._session_memory_file(user_email)
        if not path.exists():
            return _normalize_session_record({}, source_turn_count=0)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _normalize_session_record({}, source_turn_count=0)
        return _normalize_session_record(raw)

    def save_session_memory(self, user_email: str, session_memory: dict[str, Any]) -> None:
        path = self._session_memory_file(user_email)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_normalize_session_record(session_memory), ensure_ascii=False, indent=2), encoding="utf-8")

    def load_curriculum_context(self, user_email: str) -> dict[str, Any]:
        path = self._curriculum_context_file(user_email)
        if not path.exists():
            return _normalize_curriculum_context({})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _normalize_curriculum_context({})
        return _normalize_curriculum_context(raw)

    def save_curriculum_context(self, user_email: str, curriculum_context: dict[str, Any]) -> None:
        path = self._curriculum_context_file(user_email)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_normalize_curriculum_context(curriculum_context), ensure_ascii=False, indent=2), encoding="utf-8")

    def load_canvas_state(self, user_email: str) -> dict[str, Any]:
        path = self._canvas_state_file(user_email)
        if not path.exists():
            return normalize_canvas_state({})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return normalize_canvas_state({})
        return normalize_canvas_state(raw)

    def save_canvas_state(self, user_email: str, canvas_state: dict[str, Any]) -> None:
        path = self._canvas_state_file(user_email)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = normalize_canvas_state(canvas_state, fallback=self.load_canvas_state(user_email) if path.exists() else {})
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_canvas_tokens(self, user_email: str) -> dict[str, Any]:
        path = self._canvas_token_file(user_email)
        if not path.exists():
            return _normalize_canvas_token_record({})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _normalize_canvas_token_record({})
        return _normalize_canvas_token_record(raw)

    def save_canvas_tokens(self, user_email: str, token: dict[str, Any]) -> None:
        path = self._canvas_token_file(user_email)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _normalize_canvas_token_record(token, fallback=self.load_canvas_tokens(user_email) if path.exists() else {})
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear_conversation_state(self, user_email: str) -> None:
        with self._lock:
            session_dir = self._session_dir(user_email)
            if session_dir.exists():
                shutil.rmtree(session_dir, ignore_errors=True)
            session_dir.mkdir(parents=True, exist_ok=True)
            for path in (self._summary_file(user_email), self._session_memory_file(user_email)):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _iter_session_events(self, user_email: str) -> list[dict[str, Any]]:
        session_dir = self._session_dir(user_email)
        if not session_dir.exists():
            return []
        events: list[dict[str, Any]] = []
        for ndjson_path in sorted(session_dir.glob("*.ndjson")):
            try:
                lines = ndjson_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    events.append(payload)
        return events

    def completed_turns(self, user_email: str) -> list[dict[str, str]]:
        starts: dict[str, dict[str, Any]] = {}
        turns: list[dict[str, str]] = []
        for event in self._iter_session_events(user_email):
            request_id = str(event.get("request_id") or "").strip()
            event_type = str(event.get("event_type") or "").strip()
            if event_type == "request_start" and request_id:
                starts[request_id] = event
                continue
            if event_type != "request_done" or not request_id:
                continue
            start = starts.get(request_id) or {}
            prompt = str(start.get("prompt") or "").strip()
            assistant = str(event.get("assistant_final") or "").strip()
            if not prompt or not assistant:
                continue
            turns.append(
                {
                    "request_id": request_id,
                    "user": prompt,
                    "assistant": assistant,
                    "ts_utc": str(event.get("ts_utc") or start.get("ts_utc") or ""),
                }
            )
        return turns

    def recent_turns(self, user_email: str, *, max_pairs: int = RECENT_TURN_PAIR_LIMIT) -> list[dict[str, str]]:
        turns = self.completed_turns(user_email)
        return turns[-max_pairs:] if max_pairs > 0 else turns

    def load_recent_messages(self, user_email: str, *, max_pairs: int = RECENT_TURN_PAIR_LIMIT) -> list[dict[str, str]]:
        return _history_messages_from_turns(self.recent_turns(user_email, max_pairs=max_pairs))

    @staticmethod
    def _recall_score(query_terms: set[str], query_phrases: set[str], text: str, idx: int, total: int) -> float:
        lowered = str(text or "").lower()
        turn_terms = set(_tokenize_memory_text(text))
        overlap = len(query_terms & turn_terms)
        phrase_bonus = sum(1 for phrase in query_phrases if phrase and phrase in lowered)
        substring_bonus = sum(1 for term in query_terms if len(term) >= 6 and term in lowered)
        if overlap == 0 and phrase_bonus == 0 and substring_bonus == 0:
            return 0.0
        recency = 0.25 + 0.75 * ((idx + 1) / max(total, 1))
        importance = _importance_hint_score(lowered)
        return overlap * 2.0 + phrase_bonus * 1.5 + min(substring_bonus, 3) * 0.35 + recency + importance

    def relevant_recall_turns(self, user_email: str, query: str, *, max_pairs: int = EPISODIC_RECALL_LIMIT) -> list[dict[str, str]]:
        query_tokens = _tokenize_memory_text(query)
        if not query_tokens:
            return []
        turns = self.completed_turns(user_email)
        if len(turns) <= RECENT_TURN_PAIR_LIMIT:
            return []
        older_turns = turns[:-RECENT_TURN_PAIR_LIMIT]
        older_turns = older_turns[-EPISODIC_RECALL_CANDIDATE_LIMIT:]
        query_terms = set(query_tokens)
        query_phrases = {" ".join(query_tokens[idx : idx + 2]) for idx in range(len(query_tokens) - 1)}
        scored: list[tuple[float, int, dict[str, str]]] = []
        total = len(older_turns)
        for idx, turn in enumerate(older_turns):
            combined = f"{turn.get('user', '')}\n{turn.get('assistant', '')}"
            score = self._recall_score(query_terms, query_phrases, combined, idx, total)
            if score > 1.25:
                scored.append((score, idx, turn))
        if not scored:
            return []
        top = sorted(scored, key=lambda item: (-item[0], -item[1]))[:max_pairs]
        return [item[2] for item in sorted(top, key=lambda item: item[1])]

    def build_system_prompt_override(self, user_email: str, base_prompt: str, *, query: str = "") -> str | None:
        summary = self.load_summary(user_email)
        session_memory = self.load_session_memory(user_email)
        curriculum_context = self.load_curriculum_context(user_email)
        profile = self.load_profile(user_email)
        canvas_state = self.load_canvas_state(user_email)
        institution = institutions.get(profile.get("institution_key"))
        course_guide_lines: list[str] = []
        canvas_summary_lines = build_canvas_summary_lines(canvas_state)
        retrieved_chunks: list[dict[str, Any]] = []
        if institution is not None:
            relevant_course_ids = extract_relevant_course_ids(canvas_state)
            if (
                not relevant_course_ids
                and profile.get("auth_source") == "google"
                and institution.institution_key == MIAMIOH_PILOT_INSTITUTION_KEY
            ):
                relevant_course_ids = list(institution.mapped_course_ids)
            if relevant_course_ids:
                course_guide_lines = build_pilot_override_summary_lines(
                    institution,
                    course_ids=relevant_course_ids,
                    query=query,
                )
                if query:
                    override_limit = 4 if is_schedule_query(query) else 2
                    retrieved_chunks.extend(
                        retrieve_pilot_override_chunks(
                            institution,
                            query,
                            course_ids=relevant_course_ids,
                            limit=override_limit,
                        )
                    )
                bundle_query = build_pilot_bundle_query(
                    institution,
                    query,
                    course_ids=relevant_course_ids,
                ) if query else query
                study_intent = bool(query and re.search(r"\b(study|review|practice|prepare|help me)\b", query, re.IGNORECASE))
                bundle_limit = 4 if study_intent else (2 if query and is_schedule_query(query) else 4)
                retrieved_chunks.extend(
                    retrieve_bundle_chunks(
                        institution,
                        bundle_query,
                        course_ids=relevant_course_ids,
                        limit=bundle_limit,
                    )
                )
        unique_chunks: list[dict[str, Any]] = []
        seen_chunk_keys: set[tuple[str, str]] = set()
        for chunk in retrieved_chunks:
            key = (str(chunk.get("source_type") or ""), str(chunk.get("title") or ""))
            if key in seen_chunk_keys:
                continue
            seen_chunk_keys.add(key)
            unique_chunks.append(chunk)
        retrieved_chunks = unique_chunks[:6]
        recalled_turns = self.relevant_recall_turns(user_email, query, max_pairs=EPISODIC_RECALL_LIMIT)
        if (
            not _summary_has_content(summary)
            and not _session_has_content(session_memory)
            and not recalled_turns
            and not _curriculum_has_content(curriculum_context)
            and not course_guide_lines
            and not canvas_summary_lines
            and not retrieved_chunks
            and not _authenticated_profile_has_content(profile)
        ):
            return None
        return _compose_memory_system_prompt(
            base_prompt,
            summary,
            session_memory,
            recalled_turns,
            curriculum_context,
            course_guide_lines,
            canvas_summary_lines,
            retrieved_chunks,
            profile,
        )

    def schedule_memory_refresh(self, user_email: str, engine_obj: DesktopEngine) -> None:
        guard = self._memory_guard(user_email)
        if not guard.acquire(blocking=False):
            return
        Thread(
            target=self._refresh_memory_worker,
            args=(user_email, engine_obj, guard),
            daemon=True,
        ).start()

    def _refresh_memory_worker(self, user_email: str, engine_obj: DesktopEngine, guard: Lock) -> None:
        try:
            turns = self.completed_turns(user_email)
            target_count = max(0, len(turns) - RECENT_TURN_PAIR_LIMIT)
            current_summary = self.load_summary(user_email)
            cursor = min(max(int(current_summary.get("source_turn_count") or 0), 0), target_count)
            working_summary = _normalize_summary_record(current_summary, source_turn_count=cursor)

            while cursor < target_count:
                batch_end = min(target_count, cursor + SUMMARY_BATCH_TURNS)
                batch = turns[cursor:batch_end]
                summary_prompt = self._summary_update_prompt(working_summary, batch)
                refreshed = _run_memory_completion(
                    engine_obj,
                    summary_prompt,
                    system_prompt=PUBLIC_SUMMARY_SYSTEM_PROMPT,
                    timeout_seconds=SUMMARY_TIMEOUT_SECONDS,
                )
                if not refreshed:
                    break
                working_summary = _normalize_summary_record(refreshed, fallback=working_summary, source_turn_count=batch_end)
                cursor = batch_end

            if cursor > int(current_summary.get("source_turn_count") or 0):
                working_summary["updated_at"] = _utc_now_iso()
                self.save_summary(user_email, working_summary)

            recent_slice = turns[-SESSION_TURN_LOOKBACK:] if SESSION_TURN_LOOKBACK > 0 else turns
            if recent_slice:
                current_session = self.load_session_memory(user_email)
                session_prompt = self._session_update_prompt(current_session, recent_slice)
                refreshed_session = _run_memory_completion(
                    engine_obj,
                    session_prompt,
                    system_prompt=PUBLIC_SESSION_MEMORY_SYSTEM_PROMPT,
                    timeout_seconds=SESSION_MEMORY_TIMEOUT_SECONDS,
                )
                if refreshed_session:
                    session_record = _normalize_session_record(refreshed_session, fallback=current_session, source_turn_count=len(turns))
                    session_record["updated_at"] = _utc_now_iso()
                    self.save_session_memory(user_email, session_record)
        finally:
            guard.release()

    @staticmethod
    def _summary_update_prompt(current_summary: dict[str, Any], batch: Sequence[dict[str, str]]) -> str:
        prior = {
            "summary": str(current_summary.get("summary") or "").strip(),
            "role": str(current_summary.get("role") or "").strip(),
            "preferences": _clean_summary_list(current_summary.get("preferences")),
            "goals": _clean_summary_list(current_summary.get("goals")),
            "institution_context": _clean_summary_list(current_summary.get("institution_context")),
            "teaching_preferences": _clean_summary_list(current_summary.get("teaching_preferences")),
            "active_subjects": _clean_summary_list(current_summary.get("active_subjects")),
            "active_courses": _clean_summary_list(current_summary.get("active_courses")),
            "misconceptions": _clean_summary_list(current_summary.get("misconceptions")),
            "support_needs": _clean_summary_list(current_summary.get("support_needs")),
            "assessment_timeline": _clean_summary_list(current_summary.get("assessment_timeline")),
        }
        return (
            "Update the durable learner profile for a public educational assistant.\n"
            "Return strict JSON only using the required schema.\n\n"
            f"Current learner profile:\n{json.dumps(prior, ensure_ascii=False, indent=2)}\n\n"
            f"New completed turns:\n{_serialize_turns_for_summary(batch)}"
        )

    @staticmethod
    def _session_update_prompt(current_session: dict[str, Any], batch: Sequence[dict[str, str]]) -> str:
        prior = {
            "current_focus": str(current_session.get("current_focus") or "").strip(),
            "current_objective": str(current_session.get("current_objective") or "").strip(),
            "teaching_preferences": _clean_summary_list(current_session.get("teaching_preferences")),
            "open_loops": _clean_summary_list(current_session.get("open_loops")),
            "next_best_action": str(current_session.get("next_best_action") or "").strip(),
            "recommended_assessment": str(current_session.get("recommended_assessment") or "").strip(),
        }
        return (
            "Refresh the short-lived session memory for a public educational assistant.\n"
            "Return strict JSON only using the required schema.\n\n"
            f"Current session memory:\n{json.dumps(prior, ensure_ascii=False, indent=2)}\n\n"
            f"Recent completed turns:\n{_serialize_turns_for_summary(batch)}"
        )


class ActiveTurnRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, tuple[str, EngineSession]] = {}

    def register(self, request_id: str, user_email: str, session: EngineSession) -> None:
        if not request_id:
            return
        with self._lock:
            self._sessions[request_id] = (user_email, session)

    def release(self, request_id: str) -> None:
        if not request_id:
            return
        with self._lock:
            self._sessions.pop(request_id, None)

    def cancel(self, request_id: str, *, user_email: str) -> bool:
        with self._lock:
            record = self._sessions.get(request_id)
        if record is None:
            return False
        owner_email, session = record
        if owner_email != user_email:
            return False
        session.cancel_turn()
        return True

    def cancel_for_user(self, user_email: str) -> int:
        with self._lock:
            targets = [(request_id, session) for request_id, (owner_email, session) in self._sessions.items() if owner_email == user_email]
        for _, session in targets:
            session.cancel_turn()
        return len(targets)





cfg = PortalConfig.load()
institutions = InstitutionRegistry.load(INSTITUTIONS_CONFIG_PATH, project_root=PROJECT_ROOT)
logs = UserLogStore(cfg.log_root)
engine = DesktopEngine(tools_enabled=cfg.tools_enabled, load_model=cfg.load_model)
active_turns = ActiveTurnRegistry()
oauth: Any | None = None


def _public_vllm_only() -> bool:
    return _env_bool("ATHENA_PUBLIC_VLLM_ONLY", False)


def _runtime_ready(snapshot: dict[str, Any]) -> bool:
    backend_ok = (snapshot.get("runtime_backend") == "vllm_openai") if _public_vllm_only() else True
    model_ok = (not cfg.load_model) or bool(snapshot.get("model_loaded"))
    return bool(backend_ok and model_ok)


def _assert_public_runtime_contract() -> None:
    if not _public_vllm_only():
        return
    snapshot = engine.runtime_snapshot()
    if snapshot.get("runtime_backend") != "vllm_openai":
        raise RuntimeError("Public Athena V5 requires the vLLM OpenAI-compatible runtime.")
    if cfg.load_model and not snapshot.get("model_loaded"):
        raise RuntimeError("Public Athena V5 requires a warmed vLLM-backed model before startup completes.")


def _available_institutions() -> list[InstitutionRecord]:
    return institutions.available()


def _signin_institutions() -> list[dict[str, Any]]:
    return [record.public_dict() for record in _available_institutions()]


def _public_institutions() -> list[dict[str, Any]]:
    return institutions.public_options()


def _preferred_institution() -> InstitutionRecord | None:
    preferred = institutions.get(cfg.default_institution_key)
    if preferred is not None:
        return preferred
    return institutions.default()


def _preferred_signin_institution() -> InstitutionRecord | None:
    preferred = _preferred_institution()
    if preferred is not None and preferred.has_credentials():
        return preferred
    available = _available_institutions()
    return available[0] if available else None


def _is_miamioh_google_email(email: str) -> bool:
    return str(email or "").strip().lower().endswith(f"@{MIAMIOH_GOOGLE_DOMAIN}")


def _is_miamioh_google_user(user: dict[str, Any] | None) -> bool:
    user = user if isinstance(user, dict) else {}
    return (
        str(user.get("auth_source") or "").strip().lower() == "google"
        and str(user.get("institution_key") or "").strip().lower() == MIAMIOH_PILOT_INSTITUTION_KEY
        and _is_miamioh_google_email(str(user.get("email") or ""))
    )


def _login_error_message(request: Request) -> str:
    code = (request.query_params.get("error") or "").strip().lower()
    if code == "institution_unavailable":
        if _provider_has_credentials("google"):
            return "Institution Canvas sign-in is not configured on this host yet. For the MiamiOH pilot, use your MiamiOH Google account."
        return "Institution sign-in is not configured on this host yet."
    return ""


def _canvas_api_get_json(
    institution: InstitutionRecord,
    endpoint: str,
    access_token: str,
    *,
    query_params: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    params = {str(key): str(value) for key, value in (query_params or {}).items() if value is not None and value != ""}
    base = institution.api_base_url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    request = UrlRequest(url)
    request.add_header("Authorization", f"Bearer {access_token}")
    request.add_header("Accept", "application/json")
    try:
        with urlopen(request, timeout=CANVAS_API_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", "ignore")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"Canvas API {endpoint} failed with HTTP {exc.code}: {detail[:200]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Canvas API {endpoint} failed: {exc}") from exc
    payload = json.loads(raw)
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return {}


def _canvas_api_get_list(
    institution: InstitutionRecord,
    endpoint: str,
    access_token: str,
    *,
    query_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = _canvas_api_get_json(institution, endpoint, access_token, query_params=query_params)
    return payload if isinstance(payload, list) else []


def _canvas_role_context(enrollments: list[dict[str, Any]]) -> str:
    lowered = " ".join(
        str(item.get("type") or item.get("role") or "").lower()
        for item in enrollments
        if isinstance(item, dict)
    )
    if "teacher" in lowered or "instructor" in lowered:
        return "Canvas instructor"
    if "ta" in lowered:
        return "Canvas teaching assistant"
    if "observer" in lowered:
        return "Canvas observer"
    if "designer" in lowered:
        return "Canvas course designer"
    if enrollments:
        return "Canvas student"
    return "Institution-linked user"


def _mapped_canvas_course_ids(institution: InstitutionRecord, enrollments: list[dict[str, Any]]) -> list[str]:
    if not institution.mapped_course_ids:
        seen: list[str] = []
        for item in enrollments:
            course_id = str(item.get("course_id") or "").strip()
            if course_id and course_id not in seen:
                seen.append(course_id)
        return seen
    mapped = set(institution.mapped_course_ids)
    return [course_id for course_id in mapped if any(str(item.get("course_id") or "").strip() == course_id for item in enrollments)]


def _normalize_person_name(value: object) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower())
    return re.sub(r"\s+", " ", lowered).strip()


def _person_name_tokens(value: object) -> set[str]:
    return {token for token in _normalize_person_name(value).split() if token}


def _names_likely_match(left: object, right: object) -> bool:
    normalized_left = _normalize_person_name(left)
    normalized_right = _normalize_person_name(right)
    if not normalized_left or not normalized_right:
        return False
    if normalized_left == normalized_right:
        return True
    left_tokens = _person_name_tokens(normalized_left)
    right_tokens = _person_name_tokens(normalized_right)
    if len(left_tokens) >= 2 and left_tokens == right_tokens:
        return True
    shared = left_tokens & right_tokens
    return len(shared) >= 2 and (shared == left_tokens or shared == right_tokens)


def _load_pilot_people(institution: InstitutionRecord, course_id: str) -> dict[str, Any]:
    payload = load_bundle_course_json(institution, course_id, "pilot_people.json")
    return payload if isinstance(payload, dict) else {}


def _resolve_google_pilot_role(
    institution: InstitutionRecord,
    user: dict[str, Any],
    *,
    course_ids: list[str],
) -> dict[str, str]:
    course_payload = load_bundle_course_json(institution, course_ids[0], "course.json") if course_ids else {}
    course_name = str(course_payload.get("course_name") or "the MiamiOH pilot course").strip()
    user_name = str(user.get("name") or "").strip()
    user_email = str(user.get("email") or "").strip().lower()

    matched_role = ""
    matched_name = ""
    matched_source = ""

    for course_id in course_ids:
        people_payload = _load_pilot_people(institution, course_id)
        for person in people_payload.get("people") or []:
            if not isinstance(person, dict):
                continue
            display_name = str(person.get("display_name") or person.get("name") or "").strip()
            emails = [str(item).strip().lower() for item in (person.get("emails") or []) if str(item).strip()]
            role = str(person.get("role") or "").strip().lower()
            if user_email and user_email in emails:
                matched_role = role
                matched_name = display_name
                matched_source = str(person.get("source") or "pilot_people.json").strip()
                break
            if user_name and display_name and _names_likely_match(user_name, display_name):
                matched_role = role
                matched_name = display_name
                matched_source = str(person.get("source") or "pilot_people.json").strip()
                break
        if matched_role:
            break

    if not matched_role and course_ids:
        pilot_overrides = load_bundle_course_json(institution, course_ids[0], "pilot_overrides.json")
        instructor_name = str((pilot_overrides or {}).get("instructor") or "").strip()
        if instructor_name and user_name and _names_likely_match(user_name, instructor_name):
            matched_role = "instructor"
            matched_name = instructor_name
            matched_source = "course at-a-glance guide"

    role_key = matched_role or "student"
    if role_key in {"teacher", "professor"}:
        role_key = "instructor"
    if role_key in {"ta", "teaching assistant"}:
        role_key = "teaching assistant"
    if role_key not in {"instructor", "teaching assistant", "student", "observer", "designer"}:
        role_key = "student"

    institution_role = {
        "instructor": "MiamiOH instructor",
        "teaching assistant": "MiamiOH teaching assistant",
        "observer": "MiamiOH observer",
        "designer": "MiamiOH course designer",
        "student": "MiamiOH student",
    }.get(role_key, "MiamiOH student")

    course_role = {
        "instructor": f"Instructor for {course_name}",
        "teaching assistant": f"Teaching assistant for {course_name}",
        "observer": f"Observer for {course_name}",
        "designer": f"Course designer for {course_name}",
        "student": f"Student in {course_name}",
    }.get(role_key, f"Student in {course_name}")

    role_context = {
        "instructor": f"Instructor for {course_name} via MiamiOH Google",
        "teaching assistant": f"Teaching assistant for {course_name} via MiamiOH Google",
        "observer": f"Observer for {course_name} via MiamiOH Google",
        "designer": f"Course designer for {course_name} via MiamiOH Google",
        "student": f"Student in {course_name} via MiamiOH Google",
    }.get(role_key, f"Student in {course_name} via MiamiOH Google")

    return {
        "institution_role": institution_role,
        "course_role": course_role,
        "role_context": role_context,
        "role_source": matched_source or "MiamiOH Google pilot default",
        "matched_name": matched_name or user_name,
    }


def _curriculum_context_from_canvas(
    institution: InstitutionRecord,
    canvas_state: dict[str, Any],
) -> dict[str, Any]:
    courses = canvas_state.get("courses") or []
    course_names = [str(item.get("name") or "").strip() for item in courses if str(item.get("name") or "").strip()]
    notes = build_canvas_summary_lines(canvas_state)
    if canvas_state.get("relevant_course_ids"):
        notes.append("Static course bundle retrieval is enabled for the mapped MiamiOH course context.")
    return {
        "institution_name": institution.label,
        "role_context": _canvas_role_context(canvas_state.get("enrollments") or []),
        "current_course": "; ".join(course_names[:3]),
        "current_unit": str(((canvas_state.get("derived") or {}).get("current_unit")) or "").strip(),
        "allowed_methods": [],
        "restricted_help": [],
        "assessment_style": [],
        "notes": notes[:6],
        "updated_at": _utc_now_iso(),
    }


def _curriculum_context_for_google_pilot(
    institution: InstitutionRecord,
    *,
    course_ids: list[str],
    role_info: dict[str, str] | None = None,
) -> dict[str, Any]:
    role_info = role_info if isinstance(role_info, dict) else {}
    course_payload = load_bundle_course_json(institution, course_ids[0], "course.json") if course_ids else {}
    pilot_notes = build_pilot_override_summary_lines(institution, course_ids=course_ids, query="")
    pilot_notes.append("Warm, course-aware support is allowed. Do not imply live Canvas sync or personal due-date access.")
    pilot_notes.append("For schedule questions, copy dates exactly as written in the course guide. Do not infer or restyle the year.")
    course_role = str(role_info.get("course_role") or "").strip().lower()
    allowed_methods = [
        "Warm tutoring and study support for the course",
        "Use the at-a-glance guide as the authoritative source for dates",
        "Use the Canvas export bundle for policy, module, and assignment context",
    ]
    assessment_style = [
        "Encouraging course-specific guidance",
        "Careful date answers grounded in course materials",
    ]
    if "instructor" in course_role or "teaching assistant" in course_role:
        allowed_methods.append("Support lesson planning, review design, worked examples, and course-material drafting")
        assessment_style.append("Instructor-aware support that distinguishes teaching tasks from student study tasks")
        pilot_notes.append("Authenticated pilot role resolves as instructional staff for this course.")
    return {
        "institution_name": institution.label,
        "role_context": str(role_info.get("role_context") or "MiamiOH student via Google").strip(),
        "current_course": str(course_payload.get("course_name") or "MTH025C pilot course").strip(),
        "current_unit": "",
        "allowed_methods": allowed_methods,
        "restricted_help": [
            "Do not claim live Canvas sync",
            "Do not invent dates or deadlines beyond the course guide and export bundle",
        ],
        "assessment_style": assessment_style,
        "notes": pilot_notes[:6],
        "updated_at": _utc_now_iso(),
    }


def _bootstrap_google_pilot_context(user: dict[str, Any]) -> None:
    if not _is_miamioh_google_user(user):
        return
    institution = institutions.get(MIAMIOH_PILOT_INSTITUTION_KEY)
    if institution is None:
        return
    email = str(user.get("email") or "").strip()
    if not email:
        return
    course_ids = list(institution.mapped_course_ids or (MIAMIOH_PILOT_COURSE_ID,))
    role_info = _resolve_google_pilot_role(institution, user, course_ids=course_ids)
    logs.save_canvas_state(
        email,
        {
            "institution_key": institution.institution_key,
            "institution_name": institution.label,
            "mapped_course_ids": course_ids,
            "relevant_course_ids": course_ids,
            "pilot_role": role_info.get("course_role"),
            "pilot_role_source": role_info.get("role_source"),
            "updated_at": _utc_now_iso(),
        },
    )
    logs.save_curriculum_context(
        email,
        _curriculum_context_for_google_pilot(institution, course_ids=course_ids, role_info=role_info),
    )
    logs.save_profile(
        email,
        {
            **logs.load_profile(email),
            "email": email,
            "name": user.get("name"),
            "picture": user.get("picture"),
            "sub": user.get("sub"),
            "auth_source": "google",
            "institution_key": institution.institution_key,
            "institution_name": institution.label,
            "institution_role": role_info.get("institution_role"),
            "course_role": role_info.get("course_role"),
            "role_source": role_info.get("role_source"),
            "updated_at_utc": _utc_now_iso(),
        },
    )


def _sync_canvas_state_for_user(
    user_email: str,
    institution: InstitutionRecord,
    token: dict[str, Any],
) -> dict[str, Any]:
    access_token = str(token.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Canvas access token is missing.")

    profile_payload = _canvas_api_get_json(institution, "/users/self/profile", access_token)
    if not isinstance(profile_payload, dict):
        raise RuntimeError("Canvas user profile response was invalid.")

    enrollments = _canvas_api_get_list(
        institution,
        "/users/self/enrollments",
        access_token,
        query_params={"state[]": "active", "per_page": 100},
    )
    relevant_course_ids = _mapped_canvas_course_ids(institution, enrollments)

    courses: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    modules: list[dict[str, Any]] = []
    for course_id in relevant_course_ids:
        course_payload = _canvas_api_get_json(institution, f"/courses/{course_id}", access_token, query_params={"include[]": "term"})
        if isinstance(course_payload, dict):
            courses.append(course_payload)
        assignments.extend(
            _canvas_api_get_list(
                institution,
                f"/courses/{course_id}/assignments",
                access_token,
                query_params={"per_page": 100, "include[]": "submission"},
            )
        )
        modules.extend(
            _canvas_api_get_list(
                institution,
                f"/courses/{course_id}/modules",
                access_token,
                query_params={"per_page": 100, "include[]": "items"},
            )
        )
        events.extend(
            _canvas_api_get_list(
                institution,
                "/calendar_events",
                access_token,
                query_params={"context_codes[]": f"course_{course_id}", "per_page": 100},
            )
        )

    canvas_state = normalize_canvas_state(
        {
            "institution_key": institution.institution_key,
            "institution_name": institution.label,
            "canvas_domain": institution.canvas_domain,
            "canvas_user_id": profile_payload.get("id"),
            "mapped_course_ids": list(institution.mapped_course_ids),
            "relevant_course_ids": relevant_course_ids,
            "courses": courses,
            "enrollments": enrollments,
            "assignments": assignments,
            "events": events,
            "modules": modules,
            "updated_at": _utc_now_iso(),
        }
    )
    logs.save_canvas_state(user_email, canvas_state)
    logs.save_curriculum_context(user_email, _curriculum_context_from_canvas(institution, canvas_state))
    logs.save_profile(
        user_email,
        {
            **logs.load_profile(user_email),
            "email": user_email,
            "name": profile_payload.get("name"),
            "picture": profile_payload.get("avatar_url"),
            "auth_source": "canvas",
            "institution_key": institution.institution_key,
            "institution_name": institution.label,
            "canvas_domain": institution.canvas_domain,
            "canvas_user_id": profile_payload.get("id"),
            "last_canvas_sync_at": canvas_state.get("updated_at"),
            "updated_at_utc": _utc_now_iso(),
        },
    )
    return canvas_state


def _maybe_refresh_canvas_context(request: Request, user: dict[str, Any] | None) -> None:
    user = user or {}
    if not user or _is_guest_user(user):
        return
    institution = institutions.get(user.get("institution_key"))
    if institution is None:
        return
    user_email = str(user.get("email") or "").strip()
    if not user_email:
        return
    current_state = logs.load_canvas_state(user_email)
    if not canvas_state_is_stale(current_state, max_age_seconds=CANVAS_STATE_STALE_SECONDS):
        return
    token = logs.load_canvas_tokens(user_email)
    if not token.get("access_token"):
        return
    try:
        refreshed = _sync_canvas_state_for_user(user_email, institution, token)
        request.session["user"] = {
            **user,
            "last_canvas_sync_at": refreshed.get("updated_at"),
            "canvas_user_id": refreshed.get("canvas_user_id"),
        }
    except Exception as exc:
        logs.log_event(
            user_email,
            {
                "event_type": "canvas_sync_error",
                "user_email": user_email,
                "institution_key": institution.institution_key,
                "error": str(exc),
            },
            error_log=True,
        )


def _provider_has_credentials(provider_key: str) -> bool:
    institution = institutions.get(provider_key)
    if institution is not None:
        return institution.has_credentials()
    if provider_key == "github":
        return bool(cfg.github_client_id and cfg.github_client_secret)
    return bool(cfg.google_client_id and cfg.google_client_secret)


def _available_auth_providers() -> list[str]:
    providers = [record.institution_key for record in _available_institutions()]
    for key in ("github", "google"):
        if _provider_has_credentials(key):
            providers.append(key)
    return providers


def _preferred_auth_provider() -> str:
    preferred_institution = _preferred_institution()
    if preferred_institution is not None and preferred_institution.has_credentials():
        return preferred_institution.institution_key
    preferred = "github" if cfg.auth_provider == "github" else "google"
    if _provider_has_credentials(preferred):
        return preferred
    available = _available_auth_providers()
    return available[0] if available else preferred


def _auth_provider_label(provider_key: str | None = None) -> str:
    return _provider_label(provider_key or _preferred_auth_provider())


def _marketing_page_context(request: Request) -> dict[str, Any]:
    preferred_institution = _preferred_institution()
    preferred_signin = _preferred_signin_institution()
    pilot_google_enabled = bool(
        _provider_has_credentials("google")
        and preferred_institution is not None
        and preferred_institution.institution_key == MIAMIOH_PILOT_INSTITUTION_KEY
    )
    return {
        "request": request,
        "path_prefix": cfg.path_prefix,
        "asset_version": _asset_version(),
        "assistant_label": ASSISTANT_LABEL,
        "meta_description": PORTAL_META_DESCRIPTION,
        "auth_required": cfg.auth_required,
        "auth_provider_label": _auth_provider_label(),
        "auth_providers": _available_auth_providers(),
        "institutions": _signin_institutions(),
        "default_institution_key": (
            preferred_signin.institution_key
            if preferred_signin
            else (preferred_institution.institution_key if preferred_institution else "")
        ),
        "pilot_google_enabled": pilot_google_enabled,
        "pilot_google_label": "Continue with Google",
        "guest_login_enabled": cfg.guest_login_enabled,
        "guest_prompt_limit": cfg.guest_prompt_limit,
        "login_error": _login_error_message(request),
        "welcome_title": PORTAL_WELCOME_TITLE,
        "hero_kicker": PORTAL_HERO_KICKER,
        "hero_title": PORTAL_HERO_TITLE,
        "hero_body": PORTAL_HERO_BODY,
        "hero_promise": PORTAL_HERO_PROMISE,
        "home_reading_links": PORTAL_HOME_READING_LINKS,
        "signal_points": PORTAL_SIGNAL_POINTS,
        "capability_cards": PORTAL_CAPABILITY_CARDS,
        "architecture_intro": PORTAL_ARCHITECTURE_INTRO,
        "architecture_cards": PORTAL_ARCHITECTURE_CARDS,
        "mission_copy": PORTAL_MISSION_COPY,
        "mission_paragraphs": PORTAL_MISSION_PARAGRAPHS,
        "mission_points": PORTAL_MISSION_POINTS,
        "institution_copy": PORTAL_INSTITUTION_COPY,
        "institution_points": PORTAL_INSTITUTION_POINTS,
        "privacy_copy": PORTAL_PRIVACY_COPY,
        "privacy_points": PORTAL_PRIVACY_POINTS,
        "terms_copy": PORTAL_TERMS_COPY,
        "terms_points": PORTAL_TERMS_POINTS,
        "signin_disclosure": PORTAL_SIGNIN_DISCLOSURE,
        "chat_runtime_copy": CHAT_RUNTIME_COPY,
        "institution_email_href": "mailto:neohm@neohmlabs.com?subject=Institution%20access%20for%20Athena",
    }


def _info_page_context(request: Request, *, slug: str) -> dict[str, Any]:
    base = _marketing_page_context(request)
    page = PORTAL_INFO_PAGES.get(slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found.")
    base.update(page)
    return base


def _legal_page_context(request: Request, *, kind: str) -> dict[str, Any]:
    base = _marketing_page_context(request)
    if kind == "privacy":
        base.update(
            {
                "title": "Privacy | Athena | AEN",
                "legal_kicker": "Privacy",
                "legal_title": "Privacy notice",
                "legal_body": PORTAL_PRIVACY_COPY,
                "legal_points": PORTAL_PRIVACY_POINTS,
            }
        )
        return base
    base.update(
        {
            "title": "Terms | Athena | AEN",
            "legal_kicker": "Terms",
            "legal_title": "Terms of use",
            "legal_body": PORTAL_TERMS_COPY,
            "legal_points": PORTAL_TERMS_POINTS,
        }
    )
    return base


def _oauth_client(provider_key: str) -> Any:
    if oauth is None:
        raise RuntimeError("OAuth is not initialized.")
    institution = institutions.get(provider_key)
    client_name = institution.oauth_client_name if institution is not None else provider_key
    return getattr(oauth, client_name)


def _response_json(response: Any) -> dict[str, Any] | list[dict[str, Any]]:
    try:
        payload = response.json()
    except Exception:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return {}


def _pick_github_email(payload: list[dict[str, Any]]) -> str:
    if not payload:
        return ""
    preferred = None
    for item in payload:
        if item.get("primary") and item.get("verified"):
            preferred = item
            break
    if preferred is None:
        for item in payload:
            if item.get("verified"):
                preferred = item
                break
    if preferred is None:
        for item in payload:
            if item.get("primary"):
                preferred = item
                break
    if preferred is None:
        preferred = payload[0]
    return str((preferred or {}).get("email") or "").strip()


async def _user_from_google_callback(request: Request) -> dict[str, str]:
    client = _oauth_client("google")
    token = await client.authorize_access_token(request)
    userinfo = token.get("userinfo") or await client.parse_id_token(request, token)
    email = str((userinfo or {}).get("email") or "").strip()
    email_verified = bool((userinfo or {}).get("email_verified"))
    hosted_domain = str((userinfo or {}).get("hd") or "").strip().lower()
    user = {
        "sub": str((userinfo or {}).get("sub") or ""),
        "email": email,
        "name": str((userinfo or {}).get("name") or ""),
        "picture": str((userinfo or {}).get("picture") or ""),
        "auth_source": "google",
        "issued_at": _utc_now_iso(),
    }
    if not user["email"]:
        raise ValueError("Google account did not return email.")
    if not email_verified:
        raise ValueError("Google account email is not verified.")
    if _is_miamioh_google_email(email):
        if hosted_domain and hosted_domain != MIAMIOH_GOOGLE_DOMAIN:
            raise ValueError("MiamiOH Google sign-in requires a miamioh.edu hosted domain.")
        user["institution_key"] = MIAMIOH_PILOT_INSTITUTION_KEY
        user["institution_name"] = "Miami University"
    return user


async def _user_from_github_callback(request: Request) -> dict[str, str]:
    client = _oauth_client("github")
    token = await client.authorize_access_token(request)
    profile_response = await client.get("user", token=token)
    profile = _response_json(profile_response)
    if not isinstance(profile, dict):
        raise ValueError("GitHub user profile response was invalid.")
    email = str(profile.get("email") or "").strip()
    if not email:
        emails_response = await client.get("user/emails", token=token)
        emails = _response_json(emails_response)
        email = _pick_github_email(emails if isinstance(emails, list) else [])
    if not email:
        raise ValueError("GitHub account did not return an email. Ensure the OAuth app requests user:email.")
    user = {
        "sub": str(profile.get("id") or profile.get("node_id") or profile.get("login") or ""),
        "email": email,
        "name": str(profile.get("name") or profile.get("login") or email),
        "picture": str(profile.get("avatar_url") or ""),
        "issued_at": _utc_now_iso(),
    }
    return user


async def _user_from_canvas_callback(request: Request, institution: InstitutionRecord) -> dict[str, Any]:
    client = _oauth_client(institution.institution_key)
    token = await client.authorize_access_token(request)
    return {
        "sub": "",
        "email": "",
        "name": "",
        "picture": "",
        "issued_at": _utc_now_iso(),
        "auth_source": "canvas",
        "institution_key": institution.institution_key,
        "institution_name": institution.label,
        "canvas_domain": institution.canvas_domain,
        "_canvas_token": token,
    }


async def _oauth_user_from_callback(request: Request) -> dict[str, Any]:
    institution_key = str(request.session.get("auth_institution_pending") or "").strip().lower()
    institution = institutions.get(institution_key)
    if institution is not None:
        return await _user_from_canvas_callback(request, institution)
    provider_key = "github" if request.session.get("auth_provider_pending") == "github" else "google"
    if provider_key == "github":
        return await _user_from_github_callback(request)
    return await _user_from_google_callback(request)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    global oauth
    cfg.log_root.mkdir(parents=True, exist_ok=True)
    if cfg.auth_required:
        missing = []
        available_providers = _available_auth_providers()
        if not available_providers and not cfg.guest_login_enabled:
            missing.append("institution Canvas OAuth env vars, GitHub/Google OAuth env vars, or enable ATHENA_GUEST_LOGIN_ENABLED")
        if available_providers and not cfg.auth_redirect_uri:
            missing.append("ATHENA_AUTH_REDIRECT_URI")
        if not cfg.session_secret:
            missing.append("ATHENA_PORTAL_SESSION_SECRET")
        if missing:
            raise RuntimeError(f"Missing required auth env vars: {', '.join(missing)}")
        if OAuth is None:
            raise RuntimeError("Auth is required, but authlib is not installed.")
        oauth = OAuth()
        for institution in _available_institutions():
            oauth.register(
                name=institution.oauth_client_name,
                client_id=institution.client_id,
                client_secret=institution.client_secret,
                authorize_url=institution.authorize_url,
                access_token_url=institution.token_url,
                api_base_url=institution.api_base_url,
                client_kwargs={"scope": " ".join(institution.oauth_scopes)} if institution.oauth_scopes else {},
            )
        if _provider_has_credentials("github"):
            oauth.register(
                name="github",
                client_id=cfg.github_client_id,
                client_secret=cfg.github_client_secret,
                access_token_url="https://github.com/login/oauth/access_token",
                authorize_url="https://github.com/login/oauth/authorize",
                api_base_url="https://api.github.com/",
                client_kwargs={"scope": "read:user user:email"},
            )
        if _provider_has_credentials("google"):
            oauth.register(
                name="google",
                client_id=cfg.google_client_id,
                client_secret=cfg.google_client_secret,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": "openid email profile"},
            )
    if cfg.load_model:
        engine.warm_start()
    _assert_public_runtime_contract()
    startup_snapshot = engine.runtime_snapshot()
    print(
        "[portal-startup] "
        f"mode={cfg.mode} auth_required={cfg.auth_required} auth_provider={_preferred_auth_provider()} auth_options={','.join(_available_auth_providers())} institutions={','.join(record.institution_key for record in _available_institutions())} tools_enabled={cfg.tools_enabled} "
        f"path_prefix={cfg.path_prefix} log_root={cfg.log_root} runtime_backend={startup_snapshot.get('runtime_backend')} "
        f"model_dir={startup_snapshot.get('model_dir')} model_label={startup_snapshot.get('model_label')} "
        f"model_warmed={startup_snapshot.get('model_loaded')} ready={_runtime_ready(startup_snapshot)}"
    )
    yield


app = FastAPI(title="AEN Portal", version="4.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=cfg.session_secret,
    same_site="lax",
    https_only=cfg.cookie_secure,
    session_cookie="athena_portal_session",
)
app.mount(f"{cfg.path_prefix}/static", StaticFiles(directory=str(STATIC_DIR)), name="portal-static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _redirect_with_query(target: str, request: Request, *, status_code: int = 307) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    if query:
        joiner = "&" if "?" in target else "?"
        target = f"{target}{joiner}{query}"
    return RedirectResponse(url=target, status_code=status_code)


def _session_user(request: Request) -> dict[str, Any] | None:
    try:
        raw = request.session.get("user")
    except AssertionError:
        return None
    return raw if isinstance(raw, dict) else None


def _is_guest_user(user: dict[str, Any] | None) -> bool:
    return bool((user or {}).get("is_guest"))


def _guest_prompt_count(request: Request) -> int:
    try:
        raw = request.session.get("guest_prompt_count", 0)
    except AssertionError:
        return 0
    try:
        return max(0, int(raw))
    except Exception:
        return 0


def _increment_guest_prompt_count(request: Request) -> int:
    count = _guest_prompt_count(request) + 1
    request.session["guest_prompt_count"] = count
    return count


def _build_guest_user() -> dict[str, Any]:
    guest_id = uuid4().hex[:12]
    return {
        "sub": f"guest:{guest_id}",
        "email": f"guest-{guest_id}@portal.local",
        "name": "Guest",
        "picture": "",
        "issued_at": _utc_now_iso(),
        "is_guest": True,
        "auth_source": "guest",
    }


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


PUBLIC_SYSTEM_PROMPT_TEXT = _load_public_system_prompt_text()


def _bootstrap_messages_for_user(user_email: str) -> list[dict[str, str]]:
    return logs.load_recent_messages(user_email, max_pairs=RECENT_TURN_PAIR_LIMIT)


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
    request_id = payload.request_id.strip() or str(uuid4())
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
    ready = _runtime_ready(snapshot)
    return {
        "ok": ready,
        "ready": ready,
        "mode": cfg.mode,
        "path_prefix": cfg.path_prefix,
        "auth_required": cfg.auth_required,
        "tools_enabled": cfg.tools_enabled,
        "smoke_mode": not cfg.load_model,
        "model_loaded": snapshot.get("model_loaded", False),
        "runtime_backend": snapshot.get("runtime_backend", ""),
        "runtime_backend_label": snapshot.get("runtime_backend_label", ""),
        "configured_model_label": snapshot.get("model_label", ""),
        "configured_model_dir": snapshot.get("model_dir", ""),
        "active_model_label": snapshot.get("model_label", ""),
        "active_model_dir": snapshot.get("model_dir", ""),
        "log_root": str(cfg.log_root),
    }


if LEGACY_PATH_PREFIX != cfg.path_prefix:
    @app.api_route(LEGACY_PATH_PREFIX, methods=["GET", "POST", "HEAD", "OPTIONS"], include_in_schema=False)
    def legacy_root_redirect(request: Request) -> RedirectResponse:
        return _redirect_with_query(cfg.path_prefix, request)


    @app.api_route(f"{LEGACY_PATH_PREFIX}/{{legacy_path:path}}", methods=["GET", "POST", "HEAD", "OPTIONS"], include_in_schema=False)
    def legacy_prefix_redirect(legacy_path: str, request: Request) -> RedirectResponse:
        suffix = legacy_path.lstrip("/")
        target = cfg.path_prefix if not suffix else f"{cfg.path_prefix}/{suffix}"
        return _redirect_with_query(target, request)


@app.get("/", include_in_schema=False)
def root_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(url=cfg.path_prefix)


@app.get(f"{cfg.path_prefix}/login", response_class=HTMLResponse)
def login_page(request: Request) -> Any:
    context = _marketing_page_context(request)
    context.update({"title": "Sign in | Athena | AEN"})
    return templates.TemplateResponse("login.html", context)


@app.get(f"{cfg.path_prefix}/auth/login")
async def auth_login(request: Request) -> Any:
    provider = _preferred_auth_provider()
    institution = institutions.get(provider)
    if institution is not None:
        return await auth_login_institution(provider, request)
    return await auth_login_provider(provider, request)


@app.get(f"{cfg.path_prefix}/auth/login/institution")
async def auth_login_institution_query(request: Request, institution_key: str = "") -> Any:
    target_key = institution_key.strip().lower() or ((_preferred_institution().institution_key) if _preferred_institution() else "")
    return await auth_login_institution(target_key, request)


@app.get(f"{cfg.path_prefix}/auth/login/institution/{{institution_key}}")
async def auth_login_institution(institution_key: str, request: Request) -> Any:
    if not cfg.auth_required:
        return RedirectResponse(url=cfg.path_prefix)
    user = _session_user(request)
    if user and not _is_guest_user(user):
        return RedirectResponse(url=cfg.path_prefix)
    institution = institutions.get(institution_key)
    if institution is None or not institution.has_credentials():
        return RedirectResponse(url=f"{cfg.path_prefix}/login?error=institution_unavailable", status_code=303)
    try:
        client = _oauth_client(institution.institution_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    request.session["auth_institution_pending"] = institution.institution_key
    request.session.pop("auth_provider_pending", None)
    redirect_uri = institution.redirect_uri or cfg.auth_redirect_uri
    return await client.authorize_redirect(request, redirect_uri)


@app.get(f"{cfg.path_prefix}/auth/login/{{provider_key}}")
async def auth_login_provider(provider_key: str, request: Request) -> Any:
    if not cfg.auth_required:
        return RedirectResponse(url=cfg.path_prefix)
    user = _session_user(request)
    if user and not _is_guest_user(user):
        return RedirectResponse(url=cfg.path_prefix)
    provider = provider_key.strip().lower()
    institution = institutions.get(provider)
    if institution is not None:
        return await auth_login_institution(provider, request)
    if provider not in {"github", "google"} or provider not in _available_auth_providers():
        raise HTTPException(status_code=404, detail="Authentication provider is not available.")
    try:
        client = _oauth_client(provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    request.session["auth_provider_pending"] = provider
    request.session.pop("auth_institution_pending", None)
    return await client.authorize_redirect(request, cfg.auth_redirect_uri)


@app.get(f"{cfg.path_prefix}/auth/guest")
def auth_guest(request: Request) -> Any:
    if not cfg.auth_required:
        return RedirectResponse(url=cfg.path_prefix)
    if not cfg.guest_login_enabled:
        raise HTTPException(status_code=403, detail="Guest sign-in is disabled.")
    user = _session_user(request)
    if user and not _is_guest_user(user):
        return RedirectResponse(url=cfg.path_prefix)
    guest = user if _is_guest_user(user) else _build_guest_user()
    request.session["user"] = guest
    request.session["guest_prompt_count"] = _guest_prompt_count(request) if _is_guest_user(user) else 0
    logs.ensure_profile(guest)
    logs.log_event(str(guest["email"]), {"event_type": "guest_login", "user_email": str(guest["email"])})
    return RedirectResponse(url=cfg.path_prefix)


@app.get(f"{cfg.path_prefix}/auth/callback")
async def auth_callback(request: Request) -> Any:
    pending_institution_key = str(request.session.get("auth_institution_pending") or "").strip().lower()
    pending_institution = institutions.get(pending_institution_key)
    provider_label = pending_institution.label if pending_institution is not None else _auth_provider_label("github" if request.session.get("auth_provider_pending") == "github" else "google")
    try:
        if oauth is None:
            raise HTTPException(status_code=500, detail="OAuth is not initialized.")
        user = await _oauth_user_from_callback(request)
        if pending_institution is not None:
            token = user.pop("_canvas_token", {}) if isinstance(user, dict) else {}
            access_token = str((token or {}).get("access_token") or "").strip()
            if not access_token:
                raise ValueError("Canvas login did not return an access token.")
            profile_payload = _canvas_api_get_json(pending_institution, "/users/self/profile", access_token)
            if not isinstance(profile_payload, dict):
                raise ValueError("Canvas user profile response was invalid.")
            email = str(
                profile_payload.get("primary_email")
                or profile_payload.get("email")
                or profile_payload.get("login_id")
                or ""
            ).strip()
            if not email:
                raise ValueError("Canvas account did not return an email address.")
            user = {
                "sub": f"canvas:{pending_institution.institution_key}:{profile_payload.get('id') or email}",
                "email": email,
                "name": str(profile_payload.get("name") or profile_payload.get("short_name") or email),
                "picture": str(profile_payload.get("avatar_url") or ""),
                "issued_at": _utc_now_iso(),
                "auth_source": "canvas",
                "institution_key": pending_institution.institution_key,
                "institution_name": pending_institution.label,
                "canvas_domain": pending_institution.canvas_domain,
                "canvas_user_id": str(profile_payload.get("id") or ""),
            }
            logs.ensure_profile(user)
            logs.save_canvas_tokens(
                email,
                {
                    "access_token": token.get("access_token"),
                    "refresh_token": token.get("refresh_token"),
                    "token_type": token.get("token_type"),
                    "scope": token.get("scope"),
                    "expires_at": token.get("expires_at"),
                    "updated_at": _utc_now_iso(),
                },
            )
            try:
                canvas_state = _sync_canvas_state_for_user(email, pending_institution, token)
                user["last_canvas_sync_at"] = canvas_state.get("updated_at")
                user["canvas_user_id"] = canvas_state.get("canvas_user_id") or user.get("canvas_user_id")
            except Exception as sync_exc:
                logs.log_event(
                    email,
                    {
                        "event_type": "canvas_sync_error",
                        "user_email": email,
                        "institution_key": pending_institution.institution_key,
                        "error": str(sync_exc),
                    },
                    error_log=True,
                )
        request.session.pop("auth_provider_pending", None)
        request.session.pop("auth_institution_pending", None)
        logs.ensure_profile(user)
        _bootstrap_google_pilot_context(user)
        request.session["user"] = {**logs.load_profile(str(user.get("email") or "")), **user} if user.get("email") else user
        logs.log_event(user["email"], {"event_type": "auth_login", "user_email": user["email"]})
        return RedirectResponse(url=cfg.path_prefix)
    except Exception as exc:
        request.session.pop("auth_provider_pending", None)
        request.session.pop("auth_institution_pending", None)
        return HTMLResponse(f"<h3>{provider_label} login failed</h3><pre>{str(exc)}</pre>", status_code=400)


@app.post(f"{cfg.path_prefix}/auth/logout")
def auth_logout(request: Request) -> dict[str, Any]:
    user = _session_user(request)
    if user and user.get("email"):
        logs.log_event(str(user["email"]), {"event_type": "auth_logout", "user_email": str(user["email"])})
    request.session.clear()
    return {"ok": True}


@app.post(f"{cfg.path_prefix}/api/chat/stop")
def api_chat_stop(payload: ChatControlRequest, request: Request) -> dict[str, Any]:
    _require_auth(request)
    user = _session_user(request) or {}
    user_email = str(user.get("email") or "anonymous@dev")
    stopped = active_turns.cancel(payload.request_id.strip(), user_email=user_email)
    if stopped:
        logs.log_event(
            user_email,
            {
                "event_type": "request_stop",
                "user_email": user_email,
                "request_id": payload.request_id.strip(),
            },
        )
    return {"ok": True, "stopped": stopped}


@app.post(f"{cfg.path_prefix}/api/chat/reset")
def api_chat_reset(request: Request) -> dict[str, Any]:
    _require_auth(request)
    user = _session_user(request) or {}
    user_email = str(user.get("email") or "anonymous@dev")
    canceled = active_turns.cancel_for_user(user_email)
    logs.clear_conversation_state(user_email)
    logs.log_event(
        user_email,
        {
            "event_type": "conversation_reset",
            "user_email": user_email,
            "cancelled_active_turns": canceled,
        },
    )
    return {"ok": True, "cancelled_active_turns": canceled}


@app.get(cfg.path_prefix, response_class=HTMLResponse)
def portal_index(request: Request) -> HTMLResponse:
    user = _session_user(request) or {}
    view_mode = (request.query_params.get("view") or "").strip().lower()
    authenticated = bool(user) or (not cfg.auth_required and view_mode == "chat")
    user_email = str(user.get("email") or "anonymous@dev")
    initial_history = _bootstrap_messages_for_user(user_email) if authenticated else []
    context = _marketing_page_context(request)
    context.update(
        {
            "title": "Athena | NeohmLabs AEN Portal",
            "desktop_shell": False,
            "authenticated": authenticated,
            "memory_mode": "recent+summary+session+recall",
            "recent_turn_pair_limit": RECENT_TURN_PAIR_LIMIT,
            "memory_schema_version": MEMORY_SCHEMA_VERSION,
            "curriculum_context_supported": True,
            "initial_history": initial_history,
            "initial_transcript_html": render_transcript_html(
                initial_history,
                user_label=_user_display_name(user),
            ) if authenticated else "",
        }
    )
    return templates.TemplateResponse("index.html", context)


@app.get(f"{cfg.path_prefix}/privacy", response_class=HTMLResponse)
def privacy_page(request: Request) -> HTMLResponse:
    context = _legal_page_context(request, kind="privacy")
    context.update({"desktop_shell": False})
    return templates.TemplateResponse("legal.html", context)


@app.get(f"{cfg.path_prefix}/aen", response_class=HTMLResponse)
def aen_page(request: Request) -> HTMLResponse:
    context = _info_page_context(request, slug="aen")
    context.update({"desktop_shell": False})
    return templates.TemplateResponse("document.html", context)


@app.get(f"{cfg.path_prefix}/swarm", response_class=HTMLResponse)
def swarm_page(request: Request) -> HTMLResponse:
    context = _info_page_context(request, slug="swarm")
    context.update({"desktop_shell": False})
    return templates.TemplateResponse("document.html", context)


@app.get(f"{cfg.path_prefix}/mission", response_class=HTMLResponse)
def mission_page(request: Request) -> HTMLResponse:
    context = _info_page_context(request, slug="mission")
    context.update({"desktop_shell": False})
    return templates.TemplateResponse("document.html", context)


@app.get(f"{cfg.path_prefix}/terms", response_class=HTMLResponse)
def terms_page(request: Request) -> HTMLResponse:
    context = _legal_page_context(request, kind="terms")
    context.update({"desktop_shell": False})
    return templates.TemplateResponse("legal.html", context)


@app.get(f"{cfg.path_prefix}/api/me")
def api_me(request: Request) -> dict[str, Any]:
    if not cfg.auth_required:
        return {"user": {"email": "anonymous@dev", "name": "Anonymous", "sub": "", "picture": "", "is_guest": False}}
    user = _session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return {"user": user}


@app.get(f"{cfg.path_prefix}/api/config")
def api_config(request: Request) -> dict[str, Any]:
    _require_auth(request)
    data = engine.runtime_snapshot()
    user = _session_user(request) or {}
    data.update(
        {
            "mode": cfg.mode,
            "path_prefix": cfg.path_prefix,
            "auth_required": cfg.auth_required,
            "auth_provider_label": _auth_provider_label(),
            "auth_providers": _available_auth_providers(),
            "institutions": _signin_institutions(),
            "default_institution_key": (_preferred_signin_institution().institution_key if _preferred_signin_institution() else ""),
            "guest_login_enabled": cfg.guest_login_enabled,
            "guest_prompt_limit": cfg.guest_prompt_limit,
            "guest_prompt_count": _guest_prompt_count(request) if _is_guest_user(user) else 0,
            "smoke_mode": not cfg.load_model,
            "assistant_label": ASSISTANT_LABEL,
            "memory_mode": "recent+summary+session+recall",
            "recent_turn_pair_limit": RECENT_TURN_PAIR_LIMIT,
            "memory_schema_version": MEMORY_SCHEMA_VERSION,
            "curriculum_context_supported": True,
            "ready": _runtime_ready(data),
            "public_vllm_only": _public_vllm_only(),
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
    user = _session_user(request) or {}
    if _is_guest_user(user) and cfg.guest_prompt_limit > 0 and _guest_prompt_count(request) >= cfg.guest_prompt_limit:
        labels = [item["label"] for item in _signin_institutions()]
        label_text = " your institution" if labels else "a full account"
        raise HTTPException(status_code=429, detail=f"Guest prompt limit reached ({cfg.guest_prompt_limit}). Sign in with{label_text} to continue.")
    _maybe_refresh_canvas_context(request, user)
    prepared = _prepare_chat_request(payload, request)
    if _is_guest_user(user):
        count = _increment_guest_prompt_count(request)
        prepared.meta["guest_prompt_count"] = str(count)
    _log_request_start(prepared)

    q: "Queue[dict[str, Any]]" = Queue()

    def worker() -> None:
        server_history = logs.load_recent_messages(prepared.user_email, max_pairs=RECENT_TURN_PAIR_LIMIT)
        grounded = _maybe_grounded_public_response(prepared.user_email, prepared.prompt)
        if grounded:
            grounded_payload = _grounded_turn_payload(
                request_id=prepared.request_id,
                assistant=_enforce_public_output_contract(prepared.prompt, grounded),
                server_history=server_history,
                user_content=prepared.user_content,
                user_label=prepared.user_display_name,
                model_loaded=bool(engine.runtime_snapshot().get("model_loaded")),
            )
            _log_request_done(prepared, str(grounded_payload.get("assistant") or ""))
            if cfg.load_model:
                logs.schedule_memory_refresh(prepared.user_email, engine)
            q.put(grounded_payload)
            q.put({"type": "eof"})
            return

        session = engine.create_session()
        memory_query = prepared.prompt or prepared.user_content
        system_prompt_override = logs.build_system_prompt_override(prepared.user_email, PUBLIC_SYSTEM_PROMPT_TEXT, query=memory_query)
        turn_context_block = _compose_turn_context_block(prepared.prompt)
        if turn_context_block:
            system_prompt_override = ((system_prompt_override or PUBLIC_SYSTEM_PROMPT_TEXT).rstrip() + "\n\n" + turn_context_block).strip()
        session.restore_history(server_history)
        active_turns.register(prepared.request_id, prepared.user_email, session)
        terminal = Event()

        def on_event(event: EngineEvent) -> None:
            data = event.to_dict()
            if event.type == "turn_done":
                normalized_assistant = _enforce_public_output_contract(prepared.prompt, event.assistant)
                normalized_visible_messages = list(event.visible_messages)
                if normalized_visible_messages and normalized_visible_messages[-1].get("role") == "assistant":
                    normalized_visible_messages[-1] = dict(normalized_visible_messages[-1])
                    normalized_visible_messages[-1]["content"] = normalized_assistant
                transcript_html = render_transcript_html(normalized_visible_messages, user_label=prepared.user_display_name)
                data["assistant"] = normalized_assistant
                data["history"] = normalized_visible_messages
                data["transcript_html"] = transcript_html
                _log_request_done(prepared, normalized_assistant)
                if cfg.load_model:
                    logs.schedule_memory_refresh(prepared.user_email, engine)
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
                system_prompt_override=system_prompt_override,
            )
            terminal.wait()
        except Exception as exc:
            _log_request_error(prepared, exc)
            q.put({"type": "turn_error", "message": str(exc)})
        finally:
            active_turns.release(prepared.request_id)
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


