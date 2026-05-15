from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from transformers import PreTrainedModel

from .claims import claim_status_for, validate_claim_boundary
from .configuration_aen import AENConfig
from .manifest import load_manifest, load_profile


@dataclass
class AENResult:
    final_answer: str
    claim_status: dict[str, Any]
    telemetry: dict[str, Any] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)


class AENForReasoning(PreTrainedModel):
    config_class = AENConfig

    def __init__(self, config: AENConfig) -> None:
        super().__init__(config)


class AEN:
    def __init__(self, *, root: str | Path, manifest: dict[str, Any], profile: dict[str, Any]) -> None:
        self.root = Path(root).expanduser().resolve()
        self.manifest = dict(manifest)
        self.profile = dict(profile)
        validate_claim_boundary(self.profile)

    @classmethod
    def from_pretrained(
        cls,
        repo_id_or_path: str,
        profile: str = "clean_aime2026",
        long_context: bool | str = "auto",
        download_base_models: bool = False,
        **overrides: Any,
    ) -> "AEN":
        # Local-first scaffold. Hub download and base-checkpoint resolution will be
        # implemented in the next phase.
        root = Path(repo_id_or_path).expanduser()
        if not root.exists():
            raise FileNotFoundError(
                "This scaffold currently expects a local repo path. "
                "Hub snapshot download will be added in the implementation phase."
            )
        manifest = load_manifest(root)
        profile_cfg = load_profile(root, manifest, profile)
        profile_cfg["_long_context_request"] = long_context
        profile_cfg["_download_base_models"] = bool(download_base_models)
        profile_cfg["_overrides"] = dict(overrides)
        return cls(root=root, manifest=manifest, profile=profile_cfg)

    def solve(self, problem: str) -> AENResult:
        # Placeholder intentionally fails closed. The next phase ports the current
        # controller/runtime into this interface.
        raise NotImplementedError(
            "AEN runtime execution is not ported yet. "
            "The manifest/profile/model-card scaffold is ready for implementation."
        )

    def describe(self) -> dict[str, Any]:
        return {
            "repo_id": dict(self.manifest.get("identity") or {}).get("repo_id"),
            "architecture_version": dict(self.manifest.get("identity") or {}).get("architecture_version"),
            "profile": self.profile.get("profile_id"),
            "claim_status": claim_status_for(self.profile),
            "base_checkpoints": dict(self.manifest.get("base_checkpoints") or {}),
        }
