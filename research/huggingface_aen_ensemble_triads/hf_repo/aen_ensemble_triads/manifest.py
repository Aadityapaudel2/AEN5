from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping YAML at {path}")
    return dict(payload)


def repo_file(root: str | Path, relative: str) -> Path:
    return Path(root).expanduser().resolve() / str(relative).replace("/", "\\")


def load_manifest(root: str | Path, manifest_name: str = "aen_manifest.yaml") -> dict[str, Any]:
    return read_yaml(repo_file(root, manifest_name))


def load_profile(root: str | Path, manifest: dict[str, Any], profile_id: str | None = None) -> dict[str, Any]:
    selected = str(profile_id or manifest.get("default_profile") or "clean_aime2026")
    profiles = dict(manifest.get("profiles") or {})
    if selected not in profiles:
        raise KeyError(f"Unknown AEN profile {selected!r}; available={sorted(profiles)}")
    profile = read_yaml(repo_file(root, str(profiles[selected])))
    profile["_selected_profile"] = selected
    return dict(profile)
