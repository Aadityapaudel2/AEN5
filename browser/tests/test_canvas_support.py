from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from browser.canvas_support import (
    InstitutionRegistry,
    build_pilot_bundle_query,
    build_canvas_summary_lines,
    build_pilot_override_summary_lines,
    extract_relevant_course_ids,
    is_schedule_query,
    load_pilot_overrides,
    normalize_canvas_state,
    retrieve_pilot_override_chunks,
    retrieve_bundle_chunks,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class CanvasSupportTests(unittest.TestCase):
    def test_registry_loads_miamioh_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "institutions.json"
            cfg_path.write_text(
                json.dumps(
                    [
                        {
                            "institution_key": "miamioh",
                            "label": "Miami University (Canvas)",
                            "canvas_domain": "miamioh.instructure.com",
                            "oauth_client_id_env": "ATHENA_CANVAS_MIAMIOH_CLIENT_ID",
                            "oauth_client_secret_env": "ATHENA_CANVAS_MIAMIOH_CLIENT_SECRET",
                            "redirect_uri_env": "ATHENA_CANVAS_MIAMIOH_REDIRECT_URI",
                            "bundle_root": "institutions/miamioh",
                            "mapped_course_ids": ["250433"],
                            "default_selected": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            registry = InstitutionRegistry.load(cfg_path, project_root=REPO_ROOT)
        record = registry.get("miamioh")
        self.assertIsNotNone(record)
        self.assertEqual(record.canvas_domain, "miamioh.instructure.com")
        self.assertEqual(record.mapped_course_ids, ("250433",))
        self.assertEqual(registry.default().institution_key, "miamioh")

    def test_canvas_state_derives_next_due_and_exam(self) -> None:
        state = normalize_canvas_state(
            {
                "institution_key": "miamioh",
                "courses": [{"id": "250433", "name": "MTH025 H C"}],
                "enrollments": [{"course_id": "250433", "course_section_name": "Section H"}],
                "assignments": [
                    {"id": "a1", "course_id": "250433", "name": "Homework 1", "due_at": "2030-04-01T12:00:00+00:00"},
                    {"id": "a2", "course_id": "250433", "name": "Exam 2", "due_at": "2030-03-20T12:00:00+00:00"},
                ],
                "events": [{"id": "e1", "course_id": "250433", "title": "Office Hours", "start_at": "2030-03-18T14:00:00+00:00"}],
                "modules": [{"id": "m1", "course_id": "250433", "name": "Factoring Trinomials", "position": 3, "state": "active", "items": []}],
            }
        )
        self.assertEqual(state["derived"]["next_due"]["name"], "Exam 2")
        self.assertEqual(state["derived"]["next_exam"]["name"], "Exam 2")
        self.assertEqual(state["derived"]["current_unit"], "Factoring Trinomials")
        self.assertEqual(extract_relevant_course_ids(state), [])
        lines = build_canvas_summary_lines(state)
        self.assertTrue(any("Next due assignment" in line for line in lines))
        self.assertTrue(any("Current unit or module" in line for line in lines))

    def test_bundle_retrieval_returns_course_chunks(self) -> None:
        cfg_path = REPO_ROOT / "browser" / "config" / "institutions.json"
        registry = InstitutionRegistry.load(cfg_path, project_root=REPO_ROOT)
        institution = registry.get("miamioh")
        self.assertIsNotNone(institution)
        chunks = retrieve_bundle_chunks(institution, "when is office hours", course_ids=["250433"], limit=3)
        self.assertTrue(chunks)
        self.assertTrue(any(chunk["source_type"] in {"event", "page", "module"} for chunk in chunks))

    def test_course_overview_retrieval_skips_internal_author_notes(self) -> None:
        cfg_path = REPO_ROOT / "browser" / "config" / "institutions.json"
        registry = InstitutionRegistry.load(cfg_path, project_root=REPO_ROOT)
        institution = registry.get("miamioh")
        self.assertIsNotNone(institution)
        chunks = retrieve_bundle_chunks(institution, "What is this course about?", course_ids=["250433"], limit=4)
        self.assertTrue(chunks)
        titles = [chunk["title"].lower() for chunk in chunks]
        self.assertFalse(any("author notes" in title for title in titles))
        self.assertFalse(any("do not publish" in title for title in titles))
        overview_chunks = retrieve_pilot_override_chunks(institution, "What is this course about?", course_ids=["250433"], limit=4)
        self.assertTrue(any(chunk["source_type"] == "pilot_roadmap" for chunk in overview_chunks))
        summary_lines = build_pilot_override_summary_lines(institution, course_ids=["250433"], query="What is this course about?")
        self.assertTrue(any("Course theme and framing:" in line for line in summary_lines))
        self.assertTrue(any("Students work through:" in line for line in summary_lines))
        self.assertTrue(any("Linear Equations" in line for line in summary_lines))

    def test_pilot_override_retrieval_prefers_schedule_chunks(self) -> None:
        cfg_path = REPO_ROOT / "browser" / "config" / "institutions.json"
        registry = InstitutionRegistry.load(cfg_path, project_root=REPO_ROOT)
        institution = registry.get("miamioh")
        self.assertIsNotNone(institution)
        payload = load_pilot_overrides(institution, "250433")
        self.assertTrue(payload)
        self.assertEqual(payload.get("course_id"), "250433")
        self.assertTrue(any("Exam #2" in str(item.get("name")) for item in payload.get("assessment_calendar", [])))
        self.assertTrue(any("Factoring" in str(item) for item in payload.get("upcoming_module_titles", [])))
        self.assertTrue(is_schedule_query("when is exam 2"))
        lines = build_pilot_override_summary_lines(institution, course_ids=["250433"], query="when is exam 2")
        self.assertTrue(any("course at-a-glance guide" in line.lower() for line in lines))
        chunks = retrieve_pilot_override_chunks(institution, "when is exam 2", course_ids=["250433"], limit=3)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0]["title"], "Exam #2")
        self.assertTrue(all(chunk["title"] == "Exam #2" for chunk in chunks))
        self.assertTrue(any(chunk["source_type"] == "pilot_assessment" for chunk in chunks))

    def test_pilot_override_exact_assessment_match_and_bundle_hint(self) -> None:
        cfg_path = REPO_ROOT / "browser" / "config" / "institutions.json"
        registry = InstitutionRegistry.load(cfg_path, project_root=REPO_ROOT)
        institution = registry.get("miamioh")
        self.assertIsNotNone(institution)
        lines = build_pilot_override_summary_lines(institution, course_ids=["250433"], query="Help me study for Quiz 6")
        self.assertTrue(any("Requested assessment: Quiz #6" in line for line in lines))
        self.assertTrue(any("factoring trinomials" in line.lower() for line in lines))
        chunks = retrieve_pilot_override_chunks(institution, "Help me study for Quiz 6", course_ids=["250433"], limit=3)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0]["title"], "Quiz #6")
        self.assertTrue(all(chunk["title"] == "Quiz #6" for chunk in chunks))
        bundle_query = build_pilot_bundle_query(institution, "Help me study for Quiz 6", course_ids=["250433"])
        self.assertIn("Quiz #6", bundle_query)
        self.assertIn("factoring trinomials", bundle_query.lower())

    def test_discussion_query_prefers_discussion_bundle_chunks(self) -> None:
        cfg_path = REPO_ROOT / "browser" / "config" / "institutions.json"
        registry = InstitutionRegistry.load(cfg_path, project_root=REPO_ROOT)
        institution = registry.get("miamioh")
        self.assertIsNotNone(institution)
        chunks = retrieve_bundle_chunks(institution, "What should I know about discussions?", course_ids=["250433"], limit=4)
        self.assertTrue(chunks)
        titles = [chunk["title"].lower() for chunk in chunks]
        self.assertTrue(any("discussion" in title or "replies reminder" in title for title in titles))
        self.assertFalse(any("but i didn't know" in title for title in titles))


if __name__ == "__main__":
    unittest.main()
