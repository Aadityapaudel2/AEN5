from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ATHENA_WEB_LOAD_MODEL", "0")

from browser import portal_server


REPO_ROOT = Path(__file__).resolve().parents[1]


class PortalPilotRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.institution = portal_server.institutions.get("miamioh")
        self.assertIsNotNone(self.institution)

    def test_google_pilot_instructor_matches_course_guide_name(self) -> None:
        role_info = portal_server._resolve_google_pilot_role(
            self.institution,
            {
                "name": "Aaditya Paudel",
                "email": "paudela@miamioh.edu",
                "auth_source": "google",
                "institution_key": "miamioh",
            },
            course_ids=["250433"],
        )
        self.assertEqual(role_info["institution_role"], "MiamiOH instructor")
        self.assertIn("Instructor", role_info["course_role"])
        self.assertEqual(role_info["role_source"], "course at-a-glance guide")

    def test_google_pilot_non_instructor_defaults_to_student(self) -> None:
        role_info = portal_server._resolve_google_pilot_role(
            self.institution,
            {
                "name": "Jordan Student",
                "email": "studentj@miamioh.edu",
                "auth_source": "google",
                "institution_key": "miamioh",
            },
            course_ids=["250433"],
        )
        self.assertEqual(role_info["institution_role"], "MiamiOH student")
        self.assertIn("Student", role_info["course_role"])

    def test_memory_prompt_includes_authenticated_identity_context(self) -> None:
        prompt = portal_server._compose_memory_system_prompt(
            "Base prompt",
            {},
            {},
            [],
            {},
            [],
            [],
            [],
            {
                "name": "Aaditya Paudel",
                "email": "paudela@miamioh.edu",
                "auth_source": "google",
                "institution_name": "Miami University",
                "institution_role": "MiamiOH instructor",
                "course_role": "Instructor for MTH025C",
                "role_source": "course at-a-glance guide",
            },
        )
        self.assertIn("Authenticated session identity:", prompt)
        self.assertIn("Display name: Aaditya Paudel", prompt)
        self.assertIn("Current course role: Instructor for MTH025C", prompt)
        self.assertIn("reliable when the user asks about their own name or role", prompt)

    def test_new_thread_keeps_durable_profile_but_drops_recent_and_session_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = portal_server.UserLogStore(Path(tmpdir))
            user = {
                "email": "teacher@miamioh.edu",
                "name": "Teacher Example",
                "institution_key": "miamioh",
                "institution_name": "Miami University",
                "auth_source": "google",
            }
            store.ensure_profile(user)
            store.log_event(
                user["email"],
                {
                    "event_type": "request_start",
                    "request_id": "req-1",
                    "prompt": "hello athena",
                },
            )
            store.log_event(
                user["email"],
                {
                    "event_type": "request_done",
                    "request_id": "req-1",
                    "assistant_final": "hello teacher",
                },
            )
            store.save_summary(user["email"], {"summary": "recent continuity", "source_turn_count": 12})
            store.save_session_memory(user["email"], {"current_focus": "current thread"})

            self.assertTrue(store.load_recent_messages(user["email"]))
            self.assertTrue(store.load_summary(user["email"]).get("summary"))
            self.assertTrue(store.load_session_memory(user["email"]).get("current_focus"))

            store.clear_conversation_state(user["email"])

            self.assertEqual(store.load_recent_messages(user["email"]), [])
            self.assertEqual(store.load_summary(user["email"]).get("summary"), "recent continuity")
            self.assertEqual(store.load_summary(user["email"]).get("source_turn_count"), 0)
            self.assertEqual(store.load_session_memory(user["email"]).get("current_focus"), "")
            self.assertEqual(store.load_profile(user["email"]).get("institution_key"), "miamioh")
            self.assertEqual(store.load_curriculum_context(user["email"]).get("institution_name"), "")

    def test_forget_learner_memory_drops_durable_recent_and_session_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = portal_server.UserLogStore(Path(tmpdir))
            email = "learner@example.edu"
            store.ensure_profile({"email": email, "name": "Learner"})
            store.log_event(email, {"event_type": "request_start", "request_id": "req-1", "prompt": "help"})
            store.log_event(email, {"event_type": "request_done", "request_id": "req-1", "assistant_final": "start"})
            store.save_summary(email, {"summary": "prefers examples"})
            store.save_session_memory(email, {"current_focus": "linear equations"})

            store.forget_learner_memory(email)

            self.assertEqual(store.load_recent_messages(email), [])
            self.assertEqual(store.load_summary(email).get("summary"), "")
            self.assertEqual(store.load_session_memory(email).get("current_focus"), "")
            self.assertEqual(store.load_profile(email).get("name"), "Learner")

    def test_clear_conversation_state_keeps_curriculum_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = portal_server.UserLogStore(Path(tmpdir))
            user = {
                "email": "teacher@miamioh.edu",
                "name": "Teacher Example",
                "institution_key": "miamioh",
                "institution_name": "Miami University",
                "auth_source": "google",
            }
            store.ensure_profile(user)
            store.save_curriculum_context(
                user["email"],
                {
                    "institution_name": "Miami University",
                    "role_context": "Instructor",
                    "current_course": "MTH 025C",
                    "current_unit": "Exponents and Polynomials",
                },
            )

            store.clear_conversation_state(user["email"])

            context = store.load_curriculum_context(user["email"])
            self.assertEqual(context.get("institution_name"), "Miami University")
            self.assertEqual(context.get("current_course"), "MTH 025C")

    def test_grounded_identity_response_uses_authenticated_profile_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_logs = portal_server.logs
            try:
                portal_server.logs = portal_server.UserLogStore(Path(tmpdir))
                portal_server.logs.ensure_profile(
                    {
                        "email": "paudela@miamioh.edu",
                        "name": "Aaditya Paudel",
                        "institution_key": "miamioh",
                        "institution_name": "Miami University",
                        "institution_role": "MiamiOH instructor",
                        "course_role": "Instructor for MTH025C",
                        "auth_source": "google",
                    }
                )
                with patch.dict(os.environ, {"ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH": "1"}, clear=False):
                    response = portal_server._maybe_grounded_public_response(
                        "paudela@miamioh.edu",
                        "what is my name and what is my position",
                    )
            finally:
                portal_server.logs = original_logs
        self.assertIsNotNone(response)
        self.assertIn("Your name is Aaditya Paudel.", response)
        self.assertIn("Your current role is Instructor for MTH025C.", response)

    def test_grounded_schedule_response_copies_exact_exam_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_logs = portal_server.logs
            try:
                portal_server.logs = portal_server.UserLogStore(Path(tmpdir))
                portal_server.logs.ensure_profile(
                    {
                        "email": "paudela@miamioh.edu",
                        "name": "Aaditya Paudel",
                        "institution_key": "miamioh",
                        "institution_name": "Miami University",
                        "institution_role": "MiamiOH instructor",
                        "course_role": "Instructor for MTH025C",
                        "auth_source": "google",
                    }
                )
                with patch.dict(os.environ, {"ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH": "1"}, clear=False):
                    response = portal_server._maybe_grounded_public_response(
                        "paudela@miamioh.edu",
                        "when was exam 2 last semester?",
                    )
            finally:
                portal_server.logs = original_logs
        self.assertIsNotNone(response)
        self.assertIn("Exam #2", response)
        self.assertIn("Thu, Mar 19, 2026", response)

    def test_google_institution_context_is_inactive_by_default(self) -> None:
        profile = {
            "email": "teacher@miamioh.edu",
            "auth_source": "google",
            "institution_key": "miamioh",
            "institution_name": "Miami University",
            "course_role": "Instructor for MTH025C",
        }
        with patch.dict(os.environ, {"ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH": "0"}, clear=False):
            sanitized = portal_server._profile_for_active_context(profile)
        self.assertEqual(sanitized["institution_key"], "")
        self.assertEqual(sanitized["course_role"], "")
        self.assertEqual(sanitized["email"], "teacher@miamioh.edu")

    def test_google_institution_context_can_be_explicitly_enabled(self) -> None:
        profile = {
            "email": "teacher@miamioh.edu",
            "auth_source": "google",
            "institution_key": "miamioh",
            "institution_name": "Miami University",
        }
        with patch.dict(os.environ, {"ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH": "1"}, clear=False):
            self.assertTrue(portal_server._institution_context_enabled(profile))


if __name__ == "__main__":
    unittest.main()
