from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from exclusive.desktop_engine.memory_manager import MemoryManager, trim_working_messages
from exclusive.desktop_engine.memory_store import EpisodeRecord, MemoryStore
from exclusive.desktop_engine.runtime import ChatTurnResult, RuntimeMessage
from exclusive.desktop_engine.session import EngineSession


class _FakeWorker:
    def runtime_snapshot(self) -> dict:
        return {}

    def base_system_prompt(self) -> str:
        return "BASE"

    def estimate_tokens(self, **kwargs):
        return {"available": True}

    def set_tools_enabled(self, enabled: bool) -> None:
        del enabled

    def cancel(self) -> None:
        return None

    def run_turn(self, *, prompt: str, history, image_paths, emit, system_prompt_override=None):
        del prompt, image_paths, emit, system_prompt_override
        response = RuntimeMessage("assistant", f"echo:{history[-1].content if history else 'fresh'}")
        return type(
            "FakeWorkerResult",
            (),
            {"turn": ChatTurnResult(assistant=response.content, visible_messages=[response]), "model_loaded": True},
        )()


class PrivateMemoryContractTests(unittest.TestCase):
    def test_resume_reads_latest_visible_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "logs" / "desktop"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "20260319T010000Z_older.ndjson").write_text(
                json.dumps(
                    {
                        "ts": "2026-03-19T01:00:00Z",
                        "event_type": "turn_done",
                        "visible_messages": [{"role": "user", "content": "older"}, {"role": "assistant", "content": "reply older"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (log_dir / "20260319T020000Z_newer.ndjson").write_text(
                json.dumps(
                    {
                        "ts": "2026-03-19T02:00:00Z",
                        "event_type": "turn_done",
                        "visible_messages": [{"role": "user", "content": "latest"}, {"role": "assistant", "content": "reply latest"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "ATHENA_MEMORY_ROOT": str(root / "memory"),
                    "ATHENA_LOG_ROOT": str(root / "logs"),
                },
                clear=False,
            ):
                store = MemoryStore()
                recent = store.load_recent_messages()

        self.assertEqual([item["content"] for item in recent], ["latest", "reply latest"])

    def test_forget_session_preserves_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(
                os.environ,
                {
                    "ATHENA_MEMORY_ROOT": str(root / "memory"),
                    "ATHENA_LOG_ROOT": str(root / "logs"),
                },
                clear=False,
            ):
                store = MemoryStore()
                store.save_profile({"summary": "Durable profile", "preferences": ["concise"]})
                store.save_session({"current_focus": "Current turn", "open_loops": ["Follow up"]})
                store.append_episode(
                    EpisodeRecord(
                        episode_id="ep1",
                        ts_utc="2026-03-19T02:00:00Z",
                        title="Important episode",
                        tags=["portal"],
                        salience=0.8,
                        user_excerpt="Please remember this portal issue.",
                        assistant_excerpt="I will keep it in mind.",
                        artifact_refs=["run_portal.ps1"],
                        source_session_id="session1",
                    )
                )
                store.forget_session()
                profile = store.load_profile()
                session = store.load_session()
                recalled = store.search_episodes("portal issue", [], limit=2)

        self.assertEqual(profile["summary"], "Durable profile")
        self.assertEqual(profile["preferences"], ["concise"])
        self.assertEqual(session["current_focus"], "")
        self.assertEqual(session["open_loops"], [])
        self.assertTrue(recalled)

    def test_trim_working_messages_keeps_last_eight_pairs(self) -> None:
        messages = []
        for index in range(10):
            messages.append({"role": "user", "content": f"u{index}"})
            messages.append({"role": "assistant", "content": f"a{index}"})
        trimmed = trim_working_messages(messages)
        self.assertEqual(len(trimmed), 16)
        self.assertEqual(trimmed[0]["content"], "u2")
        self.assertEqual(trimmed[-1]["content"], "a9")

    def test_memory_overlay_contains_all_layers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(
                os.environ,
                {
                    "ATHENA_MEMORY_ROOT": str(root / "memory"),
                    "ATHENA_LOG_ROOT": str(root / "logs"),
                },
                clear=False,
            ):
                store = MemoryStore()
                store.save_profile(
                    {
                        "summary": "Prefers concise engineering help.",
                        "preferences": ["concise"],
                        "goals": ["stabilize Athena"],
                    }
                )
                store.save_session(
                    {
                        "current_focus": "private memory",
                        "current_objective": "retain continuity",
                        "open_loops": ["design episodic recall"],
                    }
                )
                store.append_episode(
                    EpisodeRecord(
                        episode_id="ep1",
                        ts_utc="2026-03-19T02:00:00Z",
                        title="Portal regression",
                        tags=["portal", "regression"],
                        salience=0.9,
                        user_excerpt="The public portal regressed.",
                        assistant_excerpt="We fixed the regression.",
                        artifact_refs=["portal_server.py"],
                        source_session_id="session1",
                    )
                )
                manager = MemoryManager(store)
                overlay = manager.build_prompt_overlay(
                    "BASE PROMPT",
                    [{"role": "user", "content": "current"}],
                    "portal regression memory",
                )

        self.assertIsNotNone(overlay)
        assert overlay is not None
        self.assertIn("BASE PROMPT", overlay)
        self.assertIn("Durable memory:", overlay)
        self.assertIn("Current session memory:", overlay)
        self.assertIn("Relevant earlier episodes:", overlay)

    def test_schedule_refresh_writes_memory_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(
                os.environ,
                {
                    "ATHENA_MEMORY_ROOT": str(root / "memory"),
                    "ATHENA_LOG_ROOT": str(root / "logs"),
                },
                clear=False,
            ):
                store = MemoryStore()
                manager = MemoryManager(store)
                visible_messages = [
                    {"role": "user", "content": "I prefer concise answers and I need to stabilize the private portal."},
                    {"role": "assistant", "content": "We should focus on the portal and keep the plan concise."},
                    {"role": "user", "content": "Please remember run_ui_private.ps1 and the vLLM memory work."},
                    {"role": "assistant", "content": "Next best action: implement persistent private memory."},
                ]
                scheduled = manager.schedule_refresh(visible_messages, source_session_id="session-123")
                self.assertTrue(scheduled)
                deadline = time.time() + 3.0
                while time.time() < deadline:
                    session = store.load_session()
                    if int(session.get("source_turn_count") or 0) >= 2:
                        break
                    time.sleep(0.05)
                profile = store.load_profile()
                session = store.load_session()
                recalled = store.search_episodes("run_ui_private memory", visible_messages, limit=2)

        self.assertEqual(session["current_focus"], "Please remember run_ui_private.ps1 and the vLLM memory work.")
        self.assertTrue(profile["preferences"])
        self.assertTrue(profile["goals"])
        self.assertTrue(recalled)

    def test_forget_logs_and_memory_removes_desktop_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "logs" / "desktop"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "first.ndjson").write_text("{}", encoding="utf-8")
            (log_dir / "second.ndjson").write_text("{}", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "ATHENA_MEMORY_ROOT": str(root / "memory"),
                    "ATHENA_LOG_ROOT": str(root / "logs"),
                },
                clear=False,
            ):
                store = MemoryStore()
                store.save_profile({"summary": "keep"})
                deleted_logs = store.forget_logs_and_memory()
                remaining_logs = list(log_dir.glob("*.ndjson"))
                profile = store.load_profile()
                session = store.load_session()

        self.assertEqual(deleted_logs, 2)
        self.assertEqual(remaining_logs, [])
        self.assertEqual(profile["summary"], "")
        self.assertEqual(session["current_focus"], "")

    def test_engine_session_turn_done_handles_restored_history(self) -> None:
        session = EngineSession(_FakeWorker())
        session.restore_history(
            [
                {"role": "user", "content": "old question"},
                {"role": "assistant", "content": "old answer"},
            ]
        )
        events = []

        session._run_turn("new question", [], None, events.append, None)

        self.assertTrue(events)
        final_event = events[-1]
        self.assertEqual(final_event.type, "turn_done")
        self.assertEqual(
            [item["content"] for item in final_event.visible_messages],
            ["old question", "old answer", "new question", "echo:old answer"],
        )


if __name__ == "__main__":
    unittest.main()
