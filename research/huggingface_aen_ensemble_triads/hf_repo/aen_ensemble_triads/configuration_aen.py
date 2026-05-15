from __future__ import annotations

from transformers import PretrainedConfig


class AENConfig(PretrainedConfig):
    model_type = "aen_ensemble_triads"

    def __init__(
        self,
        aen_manifest: str = "aen_manifest.yaml",
        default_profile: str = "clean_aime2026",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.aen_manifest = str(aen_manifest)
        self.default_profile = str(default_profile)
