# MiamiOH Operator Notes

`miamioh/` now holds operator scripts and pilot documentation.

Live course data no longer lives here.

Use these paths instead:

- raw Canvas export:
  - `institutions/miamioh/raw/canvas_export/`
- normalized course bundle:
  - `institutions/miamioh/courses/250433/derived/`
- pilot overlays:
  - `institutions/miamioh/courses/250433/pilot/`

Files in `miamioh/`:

- `build_canvas_bundle.py`
  - rebuilds the derived and pilot files under `institutions/`
- `pilot_preflight.py`
  - checks auth/config plus the live MiamiOH pilot bundle
- `pilot_question_smoke.py`
  - offline smoke for the main pilot questions
- `browser/public_runtime_preflight.py`
  - runtime/operator preflight for the public vLLM-backed portal
- `run_portal.ps1 -PreflightOnly`
  - easiest public-facing preflight entrypoint
- `PILOT_SHIP_CHECKLIST.md`
  - operator checklist before announcement

If you are looking for `pilot_overrides.json`, `pilot_people.json`, `modules.json`, or `files_manifest.json`, check `institutions/miamioh/...`, not `miamioh/courses/...`.
