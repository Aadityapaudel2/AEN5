from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from starlette.requests import Request

os.environ.setdefault("ATHENA_WEB_LOAD_MODEL", "0")

from browser import portal_server
from browser.canvas_support import InstitutionRecord, InstitutionRegistry


class PublicPortalSanitizationTests(unittest.TestCase):
    @staticmethod
    def _request(path: str = "/AEN5/login", query_string: bytes = b"") -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": path,
                "root_path": "",
                "scheme": "https",
                "query_string": query_string,
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 443),
                "router": portal_server.app.router,
                "session": {},
            }
        )

    @staticmethod
    def _public_cfg(**changes: object):
        base = {
            "google_client_id": "google-id",
            "google_client_secret": "google-secret",
            "github_client_id": "github-id",
            "github_client_secret": "github-secret",
            "guest_login_enabled": True,
            "guest_prompt_limit": 0,
            "default_institution_key": "",
        }
        base.update(changes)
        return replace(portal_server.cfg, **base)

    def test_general_login_renders_exactly_three_configured_public_methods(self) -> None:
        canvas_env = {
            "ATHENA_CANVAS_MIAMIOH_CLIENT_ID": "",
            "ATHENA_CANVAS_MIAMIOH_CLIENT_SECRET": "",
            "ATHENA_CANVAS_MIAMIOH_REDIRECT_URI": "",
        }
        with patch.object(portal_server, "cfg", self._public_cfg()):
            with patch.dict(os.environ, canvas_env, clear=False):
                response = portal_server.login_page(self._request())
        body = response.body.decode("utf-8")
        self.assertEqual(body.count("login-choice-btn"), 3)
        self.assertIn("Continue with Google", body)
        self.assertIn("Continue with GitHub", body)
        self.assertIn("Continue as Guest", body)
        self.assertIn("Qwen3.5-4B (base)", body)
        self.assertIn("local-first runtime", body)
        self.assertNotIn("MiamiOH", body)
        self.assertNotIn("miamioh.edu", body)
        self.assertNotIn("institution-login-form", body)

    def test_main_landing_uses_same_sanitized_signin_partial(self) -> None:
        canvas_env = {
            "ATHENA_CANVAS_MIAMIOH_CLIENT_ID": "",
            "ATHENA_CANVAS_MIAMIOH_CLIENT_SECRET": "",
            "ATHENA_CANVAS_MIAMIOH_REDIRECT_URI": "",
        }
        with patch.object(portal_server, "cfg", self._public_cfg()):
            with patch.dict(os.environ, canvas_env, clear=False):
                response = portal_server.portal_index(self._request(path="/AEN5"))
        body = response.body.decode("utf-8")
        self.assertEqual(body.count("login-choice-btn"), 3)
        self.assertIn('href="/AEN5/runtime"', body)
        self.assertIn("Qwen3.5-4B (base)", body)
        self.assertNotIn("MiamiOH", body)
        self.assertNotIn("miamioh.edu", body)

    def test_runtime_page_explains_local_first_without_claiming_magic_privacy(self) -> None:
        with patch.object(portal_server, "cfg", self._public_cfg()):
            response = portal_server.runtime_page(self._request(path="/AEN5/runtime"))
        body = response.body.decode("utf-8")
        self.assertIn(portal_server.PUBLIC_MODEL_LABEL, body)
        self.assertIn("Local-first", body)
        self.assertIn("not a magic privacy or accuracy guarantee", body)
        self.assertIn("Privacy Notice", body)

    def test_unconfigured_provider_is_not_advertised(self) -> None:
        cfg = self._public_cfg(
            google_client_id="",
            google_client_secret="",
            guest_login_enabled=False,
        )
        with patch.object(portal_server, "cfg", cfg):
            response = portal_server.login_page(self._request())
        body = response.body.decode("utf-8")
        self.assertNotIn("Continue with Google", body)
        self.assertNotIn("Continue as Guest", body)
        self.assertIn("Continue with GitHub", body)

    def test_configured_institution_appears_as_minimal_dropdown_option(self) -> None:
        record = InstitutionRecord(
            institution_key="example",
            label="Example University",
            canvas_domain="canvas.example.edu",
            oauth_client_id_env="TEST_CANVAS_ID",
            oauth_client_secret_env="TEST_CANVAS_SECRET",
            redirect_uri_env="TEST_CANVAS_REDIRECT",
            bundle_root=Path("institution-data"),
            mapped_course_ids=("private-course-id",),
            course_hints=("private-course-hint",),
        )
        registry = InstitutionRegistry((record,))
        with patch.object(portal_server, "institutions", registry):
            with patch.object(portal_server, "cfg", self._public_cfg(default_institution_key="example")):
                with patch.dict(
                    os.environ,
                    {
                        "TEST_CANVAS_ID": "id",
                        "TEST_CANVAS_SECRET": "secret",
                        "TEST_CANVAS_REDIRECT": "https://portal.example/callback",
                    },
                    clear=False,
                ):
                    options = portal_server._signin_institutions()
                    response = portal_server.login_page(self._request())
        self.assertEqual(options, [{"institution_key": "example", "label": "Example University", "default_selected": False}])
        body = response.body.decode("utf-8")
        self.assertIn("Institution sign-in", body)
        self.assertIn("Example University", body)
        self.assertNotIn("canvas.example.edu", body)
        self.assertNotIn("private-course-id", body)
        self.assertNotIn("private-course-hint", body)

    def test_api_config_redacts_internal_paths_and_dormant_course_metadata(self) -> None:
        request = self._request(path="/AEN5/api/config")
        request.scope["session"] = {
            "user": {"email": "guest-test@neohmlabs.invalid", "name": "Guest", "is_guest": True}
        }
        snapshot = {
            "runtime_backend": "vllm_openai",
            "model_loaded": True,
            "model_label": "Qwen3.5-4B",
            "model_dir": "http://192.168.1.2:8001/v1",
            "log_root": "D:/private/logs",
            "api_key": "do-not-expose",
        }
        with patch.object(portal_server, "cfg", self._public_cfg(auth_required=True)):
            with patch.object(portal_server.engine, "runtime_snapshot", return_value=snapshot):
                payload = portal_server.api_config(request)
        serialized = json.dumps(payload).lower()
        for forbidden in ("model_dir", "active_model_dir", "log_root", "api_key", "192.168.1.2", "private-course"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(payload["public_model_label"], "Qwen3.5-4B (base)")

    def test_login_errors_are_generic(self) -> None:
        request = self._request(query_string=b"error=oauth_failed")
        message = portal_server._login_error_message(request)
        self.assertIn("Sign-in could not be completed", message)
        self.assertNotIn("OAuth", message)
        self.assertNotIn("exception", message.lower())

    def test_public_identity_files_exclude_stale_and_private_markers(self) -> None:
        files = (
            Path(portal_server.TEMPLATES_DIR) / "index.html",
            Path(portal_server.TEMPLATES_DIR) / "login.html",
            Path(portal_server.TEMPLATES_DIR) / "_signin_methods.html",
            Path(portal_server.CONFIG_DIR) / "system_prompt.json",
        )
        combined = "\n".join(path.read_text(encoding="utf-8-sig").lower() for path in files)
        for marker in ("miamioh", "@miamioh.edu", "athenav11", "athena_v11", "stellar sway"):
            self.assertNotIn(marker, combined)


if __name__ == "__main__":
    unittest.main()
