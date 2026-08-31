from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("ATHENA_WEB_LOAD_MODEL", "0")

from fastapi.testclient import TestClient

from browser import portal_server


class PublicPortalSecurityTests(unittest.TestCase):
    def test_memory_export_is_bounded_redacted_and_account_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = portal_server.UserLogStore(Path(tmpdir))
            alice = "alice@example.edu"
            bob = "bob@example.edu"
            store.ensure_profile({"email": alice, "name": "Alice"})
            store.ensure_profile({"email": bob, "name": "Bob"})
            store.save_summary(
                alice,
                {
                    "summary": "Uses D:\\private\\athena\\notes and api_key=SECRET-VALUE for a demo.",
                    "preferences": ["short examples"],
                },
            )
            store.save_summary(bob, {"summary": "BOB-ONLY-CANARY"})
            for index in range(12):
                request_id = f"alice-{index}"
                store.log_event(
                    alice,
                    {
                        "event_type": "request_start",
                        "request_id": request_id,
                        "prompt": "p" * 6000,
                    },
                )
                store.log_event(
                    alice,
                    {
                        "event_type": "request_done",
                        "request_id": request_id,
                        "assistant_final": "a" * 6000,
                    },
                )
            exported = store.export_learner_memory(alice)
        serialized = json.dumps(exported, ensure_ascii=False)
        self.assertLessEqual(len(serialized.encode("utf-8")), portal_server.MAX_MEMORY_EXPORT_BYTES)
        self.assertLessEqual(len(exported["recent_conversation"]), portal_server.MAX_MEMORY_EXPORT_TURNS)
        self.assertNotIn("D:\\private", serialized)
        self.assertNotIn("SECRET-VALUE", serialized)
        self.assertNotIn("BOB-ONLY-CANARY", serialized)

    def test_memory_export_has_download_and_no_store_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = portal_server.UserLogStore(Path(tmpdir))
            store.ensure_profile({"email": "anonymous@dev", "name": "Anonymous"})
            with patch.object(portal_server, "logs", store):
                response = TestClient(portal_server.app).get(
                    f"{portal_server.cfg.path_prefix}/api/memory/export"
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, private")
        self.assertIn("attachment", response.headers.get("content-disposition", ""))
        self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")

    def test_destructive_actions_require_same_origin_action_header_and_exact_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = portal_server.UserLogStore(Path(tmpdir))
            store.ensure_profile({"email": "anonymous@dev", "name": "Anonymous"})
            client = TestClient(portal_server.app)
            with patch.object(portal_server, "logs", store):
                missing = client.post(f"{portal_server.cfg.path_prefix}/api/chat/reset", json={})
                wrong = client.post(
                    f"{portal_server.cfg.path_prefix}/api/memory/forget",
                    json={"confirmation": "DELETE"},
                    headers={"X-Athena-Action": "1"},
                )
                cross_site = client.post(
                    f"{portal_server.cfg.path_prefix}/api/memory/forget",
                    json={"confirmation": "FORGET"},
                    headers={"X-Athena-Action": "1", "Sec-Fetch-Site": "cross-site"},
                )
                accepted = client.post(
                    f"{portal_server.cfg.path_prefix}/api/memory/forget",
                    json={"confirmation": "FORGET"},
                    headers={"X-Athena-Action": "1", "Sec-Fetch-Site": "same-origin"},
                )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(cross_site.status_code, 403)
        self.assertEqual(accepted.status_code, 200)

    def test_path_containment_rejects_prefix_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "user"
            sibling = Path(tmpdir) / "user-evil" / "image.png"
            child = root / "uploads" / "image.png"
            self.assertTrue(portal_server._path_is_within(child, root))
            self.assertFalse(portal_server._path_is_within(sibling, root))

    def test_image_allowlist_validates_declared_type_and_signature(self) -> None:
        self.assertEqual(
            portal_server._validate_public_image(b"\x89PNG\r\n\x1a\nrest", "image/png"),
            ".png",
        )
        with self.assertRaises(ValueError):
            portal_server._validate_public_image(b"<svg><script/></svg>", "image/svg+xml")
        with self.assertRaises(ValueError):
            portal_server._validate_public_image(b"not-a-png", "image/png")

    def test_api_responses_receive_security_headers(self) -> None:
        response = TestClient(portal_server.app).get(f"{portal_server.cfg.path_prefix}/api/config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers.get("content-security-policy", ""))
        self.assertEqual(response.headers.get("cache-control"), "no-store, private")


if __name__ == "__main__":
    unittest.main()
