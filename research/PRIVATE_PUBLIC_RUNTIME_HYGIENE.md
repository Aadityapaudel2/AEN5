# Private/Public Runtime Hygiene

## Canonical split

- Public-facing model work happens in the browser surface (`run_dev.ps1`, `run_portal.ps1`).
- Evaluation data, manifests, and tests live under `evaluation/`.
- Desktop experimentation belongs to the private Athena surface only.
- The root `run_ui.ps1` is now a wrapper that forwards into `run_ui_private.ps1`.
- The live private desktop runs from the ignored `exclusive/` tree, not from the root repo surface.

## Tracked reproducibility

- The tracked bootstrap seed lives in `archive/shared_archives/private_desktop_seed_2026-03/`.
- That seed contains the desktop code and assets needed to recreate the private desktop locally.
- The retired root desktop surface is preserved under `archive/shared_archives/private_desktop_seed_2026-03/root_surface_retired/`.

## Public config

- Public browser config lives under `browser/config/`.
- Shared engine tool behavior lives under `desktop_engine/config/`.
- Browser auth secrets now live under `browser/config/portal_auth.env`.

## Private local state

- Private model lives under `exclusive/AthenaV1` when present.
- Private prompt/config live under `exclusive/config/`.
- Private NDJSON desktop logs live under `exclusive/logs/desktop/`.
- Private staged desktop images live under `exclusive/data/desktop_images/`.
- Private launcher now boots through its own private vLLM sidecar namespace via `run_ui_private.ps1` (default `http://127.0.0.1:8002/v1`).
- `exclusive/` is ignored by git and should remain outside the public repo surface.

## Reproducibility rule

Any new desktop-only capabilities such as persistent memory replay, private file search, private web tooling, autonomy, or build outputs should be added to the private desktop path first. Public-facing experimentation should remain browser-first unless there is a specific reason to share the capability across surfaces.

