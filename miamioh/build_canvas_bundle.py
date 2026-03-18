from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parent
INSTITUTION_ROOT = REPO_ROOT / "institutions" / "miamioh"
LEGACY_EXPORT_PATH = SCRIPT_ROOT / "mth025-h-c-export.imscc"
EXPORT_PATH = INSTITUTION_ROOT / "raw" / "canvas_export" / "mth025-h-c-export.imscc"
AT_A_GLANCE_PATH = Path(r"N:\MiamiOH\MTH025C\at_a_glance\spring_2026_at_a_glance.tex")
NS = {"c": "http://canvas.instructure.com/xsd/cccv1p0"}
IMS_NS = {
    "ims": "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1",
    "lomimscc": "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest",
}
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(node: ET.Element | None, path: str, *, ns: dict[str, str] | None = None) -> str:
    if node is None:
        return ""
    found = node.find(path, ns or NS)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p\s*>", "\n\n", cleaned)
    cleaned = re.sub(r"(?i)</li\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _chunk_text(text: str, *, max_chars: int = 700) -> list[str]:
    compact = text.strip()
    if not compact:
        return []
    pieces = [piece.strip() for piece in re.split(r"\n\s*\n", compact) if piece.strip()]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}".strip() if current else piece
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = piece
            continue
        if len(piece) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(piece):
                chunks.append(piece[start : start + max_chars].strip())
                start += max_chars
            continue
        current = candidate
    if current:
        chunks.append(current)
    return chunks


def _xml_root(zf: zipfile.ZipFile, path: str) -> ET.Element:
    return ET.fromstring(zf.read(path))


def _manifest_metadata(zf: zipfile.ZipFile) -> dict[str, str]:
    root = _xml_root(zf, "imsmanifest.xml")
    return {
        "title": _text(root, ".//lomimscc:title/lomimscc:string", ns=IMS_NS),
        "exported_at": _text(root, ".//lomimscc:lifeCycle/lomimscc:contribute/lomimscc:date/lomimscc:dateTime", ns=IMS_NS),
    }


def _parse_context(zf: zipfile.ZipFile) -> dict[str, str]:
    root = _xml_root(zf, "course_settings/context.xml")
    return {
        "course_id": _text(root, "c:course_id"),
        "course_name": _text(root, "c:course_name"),
        "root_account_name": _text(root, "c:root_account_name"),
        "canvas_domain": _text(root, "c:canvas_domain"),
    }


def _parse_course_settings(zf: zipfile.ZipFile) -> dict[str, str]:
    root = _xml_root(zf, "course_settings/course_settings.xml")
    return {
        "title": _text(root, "c:title"),
        "course_code": _text(root, "c:course_code"),
        "start_at": _text(root, "c:start_at"),
        "conclude_at": _text(root, "c:conclude_at"),
        "syllabus_body": _strip_html(_text(root, "c:syllabus_body")),
    }


def _parse_events(zf: zipfile.ZipFile) -> list[dict[str, Any]]:
    root = _xml_root(zf, "course_settings/events.xml")
    rows: list[dict[str, Any]] = []
    for event in root.findall("c:event", NS):
        rows.append(
            {
                "id": event.get("identifier", "").strip(),
                "title": _text(event, "c:title"),
                "description": _strip_html(_text(event, "c:description")),
                "start_at": _text(event, "c:start_at"),
                "end_at": _text(event, "c:end_at"),
                "rrule": _text(event, "c:rrule"),
            }
        )
    return rows


def _parse_modules(zf: zipfile.ZipFile) -> list[dict[str, Any]]:
    root = _xml_root(zf, "course_settings/module_meta.xml")
    rows: list[dict[str, Any]] = []
    for module in root.findall("c:module", NS):
        items: list[dict[str, Any]] = []
        items_root = module.find("c:items", NS)
        if items_root is not None:
            for item in items_root.findall("c:item", NS):
                items.append(
                    {
                        "id": item.get("identifier", "").strip(),
                        "title": _text(item, "c:title"),
                        "content_type": _text(item, "c:content_type"),
                        "identifierref": _text(item, "c:identifierref"),
                        "url": _text(item, "c:url"),
                        "position": _text(item, "c:position"),
                        "workflow_state": _text(item, "c:workflow_state"),
                        "indent": _text(item, "c:indent"),
                    }
                )
        rows.append(
            {
                "id": module.get("identifier", "").strip(),
                "title": _text(module, "c:title"),
                "workflow_state": _text(module, "c:workflow_state"),
                "position": _text(module, "c:position"),
                "locked": _text(module, "c:locked"),
                "require_sequential_progress": _text(module, "c:require_sequential_progress"),
                "items": items,
            }
        )
    return rows


def _parse_assignments(zf: zipfile.ZipFile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in sorted(path for path in zf.namelist() if path.endswith("assignment_settings.xml")):
        root = _xml_root(zf, name)
        rows.append(
            {
                "id": root.get("identifier", "").strip(),
                "source_path": name,
                "title": _text(root, "c:title"),
                "due_at": _text(root, "c:due_at"),
                "unlock_at": _text(root, "c:unlock_at"),
                "lock_at": _text(root, "c:lock_at"),
                "all_day_date": _text(root, "c:all_day_date"),
                "assignment_group_identifierref": _text(root, "c:assignment_group_identifierref"),
                "workflow_state": _text(root, "c:workflow_state"),
                "points_possible": _text(root, "c:points_possible"),
                "grading_type": _text(root, "c:grading_type"),
                "submission_types": _text(root, "c:submission_types"),
                "position": _text(root, "c:position"),
                "external_tool_url": _text(root, "c:external_tool_url"),
                "external_tool_new_tab": _text(root, "c:external_tool_new_tab"),
                "description": _strip_html(_text(root, "c:description")),
            }
        )
    return rows


def _parse_files(zf: zipfile.ZipFile) -> list[dict[str, str]]:
    root = _xml_root(zf, "course_settings/files_meta.xml")
    rows: list[dict[str, str]] = []
    files_root = root.find("c:files", NS)
    if files_root is None:
        return rows
    for file_node in files_root.findall("c:file", NS):
        rows.append(
            {
                "id": file_node.get("identifier", "").strip(),
                "display_name": _text(file_node, "c:display_name"),
                "category": _text(file_node, "c:category"),
            }
        )
    return rows


def _parse_pages(zf: zipfile.ZipFile) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in sorted(path for path in zf.namelist() if path.startswith("wiki_content/") and path.endswith(".html")):
        raw_html = zf.read(name).decode("utf-8", "ignore")
        title_match = re.search(r"<title>(.*?)</title>", raw_html, flags=re.IGNORECASE | re.DOTALL)
        id_match = re.search(r'<meta name="identifier" content="(.*?)"', raw_html, flags=re.IGNORECASE)
        workflow_match = re.search(r'<meta name="workflow_state" content="(.*?)"', raw_html, flags=re.IGNORECASE)
        rows.append(
            {
                "id": id_match.group(1).strip() if id_match else "",
                "source_path": name,
                "title": _strip_html(title_match.group(1)) if title_match else Path(name).stem,
                "workflow_state": workflow_match.group(1).strip() if workflow_match else "",
                "text": _strip_html(raw_html),
            }
        )
    return rows


def _latex_to_text(value: str) -> str:
    text = str(value or "")
    text = text.replace(r"\#", "#")
    text = text.replace(r"\,", ", ")
    text = text.replace(r"\,", ", ")
    text = text.replace(r"\&", "&")
    text = text.replace("\\ ", " ")
    text = re.sub(r"\\textbf\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\textit\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\underline\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"~+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" .", ".")
    return text.strip()


def _month_number(token: str) -> int | None:
    compact = str(token or "").strip().lower().rstrip(".")
    if len(compact) < 3:
        return None
    return MONTHS.get(compact[:3])


def _date_range_from_text(text: str) -> dict[str, str]:
    raw = _latex_to_text(text)
    cleaned = raw.replace("--", " -- ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    if not cleaned:
        return {"raw": "", "start_at": "", "end_at": ""}

    full_single = re.match(
        r"^(?:[A-Za-z]{3},\s*)?(?P<mon>[A-Za-z]{3,9})\s+(?P<day>\d{1,2}),\s*(?P<year>\d{4})$",
        cleaned,
    )
    if full_single:
        month = _month_number(full_single.group("mon"))
        year = int(full_single.group("year"))
        day = int(full_single.group("day"))
        if month is not None:
            start = datetime(year, month, day, tzinfo=timezone.utc)
            return {"raw": raw, "start_at": start.isoformat(), "end_at": start.isoformat()}

    month_range = re.match(
        r"^(?P<mon>[A-Za-z]{3,9})\s+(?P<start>\d{1,2})\s*--\s*(?P<end>\d{1,2}),\s*(?P<year>\d{4})$",
        cleaned,
    )
    if month_range:
        month = _month_number(month_range.group("mon"))
        year = int(month_range.group("year"))
        start_day = int(month_range.group("start"))
        end_day = int(month_range.group("end"))
        if month is not None:
            start = datetime(year, month, start_day, tzinfo=timezone.utc)
            end = datetime(year, month, end_day, tzinfo=timezone.utc)
            return {"raw": raw, "start_at": start.isoformat(), "end_at": end.isoformat()}

    full_range = re.match(
        r"^(?:[A-Za-z]{3},\s*)?(?P<mon1>[A-Za-z]{3,9})\s+(?P<day1>\d{1,2})\s*--\s*(?:[A-Za-z]{3},\s*)?(?P<mon2>[A-Za-z]{3,9})\s+(?P<day2>\d{1,2}),\s*(?P<year>\d{4})$",
        cleaned,
    )
    if full_range:
        month1 = _month_number(full_range.group("mon1"))
        month2 = _month_number(full_range.group("mon2"))
        year = int(full_range.group("year"))
        day1 = int(full_range.group("day1"))
        day2 = int(full_range.group("day2"))
        if month1 is not None and month2 is not None:
            start = datetime(year, month1, day1, tzinfo=timezone.utc)
            end = datetime(year, month2, day2, tzinfo=timezone.utc)
            return {"raw": raw, "start_at": start.isoformat(), "end_at": end.isoformat()}

    return {"raw": raw, "start_at": "", "end_at": ""}


def _parse_table_rows(section_text: str, expected_cols: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("\\") or "&" not in line or not line.endswith(r"\\"):
            continue
        parts = [_latex_to_text(part).strip() for part in line[:-2].split("&")]
        if len(parts) != expected_cols:
            continue
        rows.append(parts)
    return rows


def _parse_at_a_glance() -> dict[str, Any]:
    if not AT_A_GLANCE_PATH.exists():
        return {}
    raw_text = AT_A_GLANCE_PATH.read_text(encoding="utf-8")

    title = ""
    title_match = re.search(r"\\LARGE\s+\\textbf\{([^{}]+)\}", raw_text)
    if title_match:
        title = _latex_to_text(title_match.group(1))

    subtitle_match = re.search(
        r"Spring\s+(?P<year>\d{4}).*?Instructor:\s*(?P<instructor>[^|]+)\|.*?Updated:\s*(?P<updated>[A-Za-z]+\s+\d{1,2},\s+\d{4})",
        _latex_to_text(raw_text),
    )
    term = f"Spring {subtitle_match.group('year')}" if subtitle_match else ""
    instructor = subtitle_match.group("instructor").strip(" ,") if subtitle_match else ""
    updated_text = subtitle_match.group("updated").strip() if subtitle_match else ""
    updated_range = _date_range_from_text(updated_text)

    theme_match = re.search(r"\\section\*\{Course Theme\}(.*?)(?=\\section\*\{Assessment Calendar\})", raw_text, flags=re.DOTALL)
    theme = _latex_to_text(theme_match.group(1)).strip() if theme_match else ""

    assessment_section = re.search(
        r"\\section\*\{Assessment Calendar\}.*?\\midrule(?P<body>.*?)\\bottomrule",
        raw_text,
        flags=re.DOTALL,
    )
    assessment_rows = _parse_table_rows(assessment_section.group("body"), 3) if assessment_section else []
    assessments: list[dict[str, Any]] = []
    for name, date_text, topics in assessment_rows:
        parsed_date = _date_range_from_text(date_text)
        assessments.append(
            {
                "name": name,
                "date_text": date_text,
                "topics": topics,
                "start_at": parsed_date["start_at"],
                "end_at": parsed_date["end_at"],
            }
        )

    policy_section = re.search(
        r"\\section\*\{Policies to Remember\}.*?\\begin\{itemize\}(?P<body>.*?)\\end\{itemize\}",
        raw_text,
        flags=re.DOTALL,
    )
    policies: list[str] = []
    if policy_section:
        for item in re.findall(r"\\item\s+(.*)", policy_section.group("body")):
            clean = _latex_to_text(item).strip()
            if clean:
                policies.append(clean)

    key_dates_section = re.search(
        r"\\section\*\{Key Semester Dates\}.*?\\midrule(?P<body>.*?)\\bottomrule",
        raw_text,
        flags=re.DOTALL,
    )
    key_date_rows = _parse_table_rows(key_dates_section.group("body"), 2) if key_dates_section else []
    key_dates: list[dict[str, Any]] = []
    for label, date_text in key_date_rows:
        parsed_date = _date_range_from_text(date_text)
        key_dates.append(
            {
                "label": label,
                "date_text": date_text,
                "start_at": parsed_date["start_at"],
                "end_at": parsed_date["end_at"],
            }
        )

    final_slot_match = re.search(r"\\textbf\{Final Exam Slot:\}\s*(.*)", raw_text)
    final_slot = _latex_to_text(final_slot_match.group(1)).strip() if final_slot_match else ""

    return {
        "source_path": str(AT_A_GLANCE_PATH),
        "course_title": title,
        "term": term,
        "instructor": instructor,
        "source_updated_text": updated_text,
        "source_updated_at": updated_range["start_at"],
        "course_theme": theme,
        "assessment_calendar": assessments,
        "policy_reminders": policies,
        "key_semester_dates": key_dates,
        "final_exam_slot": final_slot,
    }


def _content_chunks(
    *,
    course_id: str,
    course_name: str,
    syllabus: str,
    modules: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    events: list[dict[str, Any]],
    files: list[dict[str, str]],
    pages: list[dict[str, str]],
) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []

    def add_chunk(source_type: str, title: str, text: str, source_path: str) -> None:
        for idx, piece in enumerate(_chunk_text(text), start=1):
            chunks.append(
                {
                    "course_id": course_id,
                    "course_name": course_name,
                    "source_type": source_type,
                    "source_path": source_path,
                    "title": title if idx == 1 else f"{title} (part {idx})",
                    "text": piece,
                }
            )

    if syllabus:
        add_chunk("syllabus", "Course syllabus", syllabus, "course_settings/course_settings.xml")

    for module in modules:
        item_titles = [item.get("title", "").strip() for item in module.get("items", []) if item.get("title")]
        module_text = "\n".join(
            [
                f"Module: {module.get('title', '').strip()}",
                f"Workflow state: {module.get('workflow_state', '').strip()}",
                f"Position: {module.get('position', '').strip()}",
                "Items:",
                *[f"- {title}" for title in item_titles],
            ]
        ).strip()
        add_chunk("module", str(module.get("title") or "Module"), module_text, "course_settings/module_meta.xml")

    for assignment in assignments:
        summary_lines = [
            f"Assignment: {assignment.get('title', '').strip()}",
            f"Workflow state: {assignment.get('workflow_state', '').strip()}",
        ]
        if assignment.get("due_at"):
            summary_lines.append(f"Due at: {assignment['due_at']}")
        if assignment.get("unlock_at"):
            summary_lines.append(f"Unlocks at: {assignment['unlock_at']}")
        if assignment.get("points_possible"):
            summary_lines.append(f"Points possible: {assignment['points_possible']}")
        if assignment.get("submission_types"):
            summary_lines.append(f"Submission type: {assignment['submission_types']}")
        if assignment.get("description"):
            summary_lines.append(assignment["description"])
        add_chunk("assignment", str(assignment.get("title") or "Assignment"), "\n".join(summary_lines), str(assignment.get("source_path") or ""))

    for event in events:
        summary_lines = [f"Event: {event.get('title', '').strip()}"]
        if event.get("start_at"):
            summary_lines.append(f"Starts at: {event['start_at']}")
        if event.get("end_at"):
            summary_lines.append(f"Ends at: {event['end_at']}")
        if event.get("description"):
            summary_lines.append(event["description"])
        add_chunk("event", str(event.get("title") or "Event"), "\n".join(summary_lines), "course_settings/events.xml")

    for file_row in files:
        title = file_row.get("display_name", "").strip()
        if not title:
            continue
        add_chunk("file_manifest", title, f"Course file or handout listed in the export: {title}. Category: {file_row.get('category', '').strip() or 'uncategorized'}.", "course_settings/files_meta.xml")

    for page in pages:
        add_chunk("page", str(page.get("title") or "Page"), str(page.get("text") or ""), str(page.get("source_path") or ""))

    return chunks


def _module_sort_key(module: dict[str, Any]) -> tuple[int, str]:
    position_text = str(module.get("position") or "").strip()
    try:
        return (int(position_text), str(module.get("title") or ""))
    except Exception:
        return (10**9, str(module.get("title") or ""))


def _pilot_module_roadmap(modules: list[dict[str, Any]]) -> dict[str, Any]:
    sequence: list[dict[str, str]] = []
    for module in sorted(modules, key=_module_sort_key):
        title = str(module.get("title") or "").strip()
        match = re.match(r"^Module\s+(\d+)\s*:\s*(.+)$", title, re.IGNORECASE)
        if not match:
            continue
        sequence.append(
            {
                "module_number": match.group(1).strip(),
                "title": title,
                "short_title": match.group(2).strip(),
                "workflow_state": str(module.get("workflow_state") or "").strip() or "unknown",
                "position": str(module.get("position") or "").strip(),
            }
        )
    if not sequence:
        return {}

    published = [row["short_title"] for row in sequence if row.get("workflow_state") == "active"]
    upcoming = [row["short_title"] for row in sequence if row.get("workflow_state") != "active"]
    roadmap_lines = [
        "Module sequence:",
        *[f"{idx}. {row['short_title']}" for idx, row in enumerate(sequence, start=1) if row.get("short_title")],
    ]
    if published:
        roadmap_lines.extend(["", "Published now: " + ", ".join(published)])
    if upcoming:
        roadmap_lines.extend(["", "Coming later: " + ", ".join(upcoming)])
    return {
        "module_sequence": sequence,
        "published_module_titles": published,
        "upcoming_module_titles": upcoming,
        "course_roadmap_text": "\n".join(roadmap_lines),
    }


def _pilot_override_chunks(
    *,
    course_id: str,
    course_name: str,
    pilot_payload: dict[str, Any],
) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []

    def add_chunk(source_type: str, title: str, text: str) -> None:
        for idx, piece in enumerate(_chunk_text(text, max_chars=520), start=1):
            chunks.append(
                {
                    "course_id": course_id,
                    "course_name": course_name,
                    "source_type": source_type,
                    "source_path": str(AT_A_GLANCE_PATH),
                    "title": title if idx == 1 else f"{title} (part {idx})",
                    "text": piece,
                }
            )

    title = str(pilot_payload.get("course_title") or course_name or "Course guide").strip()
    updated = str(pilot_payload.get("source_updated_text") or "").strip()
    term = str(pilot_payload.get("term") or "").strip()
    intro_lines = [title]
    if term:
        intro_lines.append(f"Term: {term}")
    if updated:
        intro_lines.append(f"Updated: {updated}")
    if pilot_payload.get("course_theme"):
        intro_lines.append(str(pilot_payload["course_theme"]).strip())
    add_chunk("pilot_overview", "Course at-a-glance", "\n".join(line for line in intro_lines if line))

    roadmap_text = str(pilot_payload.get("course_roadmap_text") or "").strip()
    if roadmap_text:
        add_chunk("pilot_roadmap", "Course roadmap", roadmap_text)

    for assessment in pilot_payload.get("assessment_calendar") or []:
        name = str(assessment.get("name") or "Assessment").strip()
        lines = [f"Assessment: {name}"]
        if assessment.get("date_text"):
            lines.append(f"Date: {assessment['date_text']}")
        if assessment.get("topics"):
            lines.append(f"Topics: {assessment['topics']}")
        add_chunk("pilot_assessment", name, "\n".join(lines))

    if pilot_payload.get("policy_reminders"):
        add_chunk(
            "pilot_policy",
            "Policies to remember",
            "\n".join(f"- {item}" for item in pilot_payload["policy_reminders"]),
        )

    for date_row in pilot_payload.get("key_semester_dates") or []:
        label = str(date_row.get("label") or "Semester date").strip()
        text = f"{label}: {date_row.get('date_text', '').strip()}".strip(": ")
        add_chunk("pilot_semester_date", label, text)

    if pilot_payload.get("final_exam_slot"):
        add_chunk("pilot_final", "Final exam slot", str(pilot_payload["final_exam_slot"]).strip())

    return chunks


def _pilot_people_payload(*, course_id: str, pilot_payload: dict[str, Any]) -> dict[str, Any]:
    instructor = re.sub(r"\s+", " ", str(pilot_payload.get("instructor") or "").strip())
    people: list[dict[str, Any]] = []
    if instructor:
        people.append(
            {
                "role": "instructor",
                "display_name": instructor,
                "emails": [],
                "source": "course at-a-glance guide",
            }
        )
    return {
        "course_id": course_id,
        "generated_at_utc": _utc_now_iso(),
        "people": people,
        "notes": [
            "This pilot people file is intentionally small.",
            "Add roster or staff records here later when a verified course roster is available.",
        ],
    }


def build_bundle() -> dict[str, Any]:
    export_path = EXPORT_PATH if EXPORT_PATH.exists() else LEGACY_EXPORT_PATH
    if not export_path.exists():
        raise FileNotFoundError(f"Missing IMSCC export: {EXPORT_PATH}")
    INSTITUTION_ROOT.mkdir(parents=True, exist_ok=True)
    (INSTITUTION_ROOT / "raw" / "canvas_export").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(export_path) as zf:
        manifest = _manifest_metadata(zf)
        context = _parse_context(zf)
        course_settings = _parse_course_settings(zf)
        events = _parse_events(zf)
        modules = _parse_modules(zf)
        assignments = _parse_assignments(zf)
        files = _parse_files(zf)
        pages = _parse_pages(zf)

    pilot_overrides = _parse_at_a_glance()
    module_roadmap = _pilot_module_roadmap(modules)

    course_id = context["course_id"]
    course_name = course_settings["title"] or context["course_name"]
    institution_label = context["root_account_name"] or "Miami University"
    course_root = INSTITUTION_ROOT / "courses" / course_id
    derived_root = course_root / "derived"
    pilot_root = course_root / "pilot"
    derived_root.mkdir(parents=True, exist_ok=True)
    pilot_root.mkdir(parents=True, exist_ok=True)

    institution_payload = {
        "institution_key": "miamioh",
        "label": institution_label,
        "canvas_domain": context["canvas_domain"],
        "source_export": export_path.name,
        "generated_at_utc": _utc_now_iso(),
        "courses": [
            {
                "course_id": course_id,
                "course_name": course_name,
                "course_code": course_settings["course_code"],
            }
        ],
    }
    course_payload = {
        "course_id": course_id,
        "course_name": course_name,
        "course_code": course_settings["course_code"],
        "start_at": course_settings["start_at"],
        "conclude_at": course_settings["conclude_at"],
        "institution_name": institution_label,
        "canvas_domain": context["canvas_domain"],
        "source_export": export_path.name,
        "exported_at": manifest["exported_at"],
        "generated_at_utc": _utc_now_iso(),
    }
    modules_payload = {"course_id": course_id, "generated_at_utc": _utc_now_iso(), "modules": modules}
    assignments_payload = {"course_id": course_id, "generated_at_utc": _utc_now_iso(), "assignments": assignments}
    events_payload = {"course_id": course_id, "generated_at_utc": _utc_now_iso(), "events": events}
    pages_payload = {"course_id": course_id, "generated_at_utc": _utc_now_iso(), "pages": pages}
    files_payload = {"course_id": course_id, "generated_at_utc": _utc_now_iso(), "files": files}
    chunks = _content_chunks(
        course_id=course_id,
        course_name=course_name,
        syllabus=course_settings["syllabus_body"],
        modules=modules,
        assignments=assignments,
        events=events,
        files=files,
        pages=pages,
    )

    pilot_payload: dict[str, Any] = {}
    pilot_people_payload: dict[str, Any] = {}
    if pilot_overrides:
        pilot_seed_payload = {
            **pilot_overrides,
            **module_roadmap,
        }
        pilot_chunks = _pilot_override_chunks(
            course_id=course_id,
            course_name=pilot_overrides.get("course_title") or course_name,
            pilot_payload=pilot_seed_payload,
        )
        pilot_payload = {
            "course_id": course_id,
            "course_name": pilot_overrides.get("course_title") or course_name,
            "generated_at_utc": _utc_now_iso(),
            "authoritative_for": [
                "quizzes",
                "exams",
                "final",
                "semester_dates",
                "policy_reminders",
            ],
            **pilot_seed_payload,
            "chunks": pilot_chunks,
        }
        pilot_people_payload = _pilot_people_payload(course_id=course_id, pilot_payload=pilot_seed_payload)

    (INSTITUTION_ROOT / "institution.json").write_text(json.dumps(institution_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (derived_root / "course.json").write_text(json.dumps(course_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (derived_root / "modules.json").write_text(json.dumps(modules_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (derived_root / "assignments.json").write_text(json.dumps(assignments_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (derived_root / "events.json").write_text(json.dumps(events_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (derived_root / "pages.json").write_text(json.dumps(pages_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (derived_root / "files_manifest.json").write_text(json.dumps(files_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if pilot_payload:
        (pilot_root / "pilot_overrides.json").write_text(json.dumps(pilot_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if pilot_people_payload:
        (pilot_root / "pilot_people.json").write_text(json.dumps(pilot_people_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (derived_root / "content_chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    return {
        "institution": institution_payload,
        "course": course_payload,
        "counts": {
            "modules": len(modules),
            "assignments": len(assignments),
            "events": len(events),
            "pages": len(pages),
            "files": len(files),
            "chunks": len(chunks),
            "pilot_chunks": len(pilot_payload.get("chunks") or []),
            "pilot_people": len(pilot_people_payload.get("people") or []),
        },
        "pilot_overrides_written": bool(pilot_payload),
        "pilot_people_written": bool(pilot_people_payload),
    }


if __name__ == "__main__":
    payload = build_bundle()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
