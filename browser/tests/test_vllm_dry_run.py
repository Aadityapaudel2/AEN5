from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "run_vllm.ps1"
STATE = REPO_ROOT / ".local" / "runtime" / "vllm_runtime.json"


def _hash_or_missing(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "PowerShell dry-run test requires Windows")
class VllmDryRunTests(unittest.TestCase):
    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(LAUNCHER),
                *arguments,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

    def test_native_preview_is_redacted_and_does_not_rewrite_runtime_state(self) -> None:
        before = _hash_or_missing(STATE)
        result = self._run(
            "-DryRun",
            "-ContextProfile",
            "native",
            "-LanguageModelOnly",
            "-ApiKey",
            "DRYRUN-CANARY-SECRET",
        )
        after = _hash_or_missing(STATE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DRYRUN-CANARY-SECRET", result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["mutates_runtime"])
        self.assertEqual(payload["context_profile"], "native")
        self.assertEqual(payload["max_model_len"], 128000)
        api_index = payload["command_args"].index("--api-key")
        self.assertEqual(payload["command_args"][api_index + 1], "<redacted>")
        self.assertEqual(before, after)

    def test_yarn_preview_is_guarded_and_preserves_hf_override_json(self) -> None:
        blocked = self._run("-DryRun", "-ContextProfile", "yarn_1010k")
        self.assertNotEqual(blocked.returncode, 0)
        allowed = self._run(
            "-DryRun",
            "-ContextProfile",
            "yarn_1010k",
            "-AllowExperimentalUltraLongContext",
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        payload = json.loads(allowed.stdout)
        rope = payload["hf_overrides"]["text_config"]["rope_parameters"]
        self.assertEqual(payload["max_model_len"], 1010000)
        self.assertEqual(payload["transport"], "wsl_bash_script_with_single_quoted_arguments")
        self.assertEqual(rope["rope_type"], "yarn")
        self.assertEqual(rope["factor"], 4.0)
        hf_index = payload["command_args"].index("--hf-overrides")
        forwarded = json.loads(payload["command_args"][hf_index + 1])
        self.assertEqual(forwarded, payload["hf_overrides"])


if __name__ == "__main__":
    unittest.main()
