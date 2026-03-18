# Institutions Layout

Runtime institution data now lives under `institutions/`.

Structure:

- `institutions/<institution>/raw/`
  - raw upstream exports and source files
- `institutions/<institution>/courses/<course_id>/derived/`
  - normalized bundle files generated from raw sources
  - examples: `course.json`, `modules.json`, `pages.json`, `assignments.json`, `files_manifest.json`, `content_chunks.jsonl`
- `institutions/<institution>/courses/<course_id>/pilot/`
  - pilot-only overlays and operator-maintained facts
  - examples: `pilot_overrides.json`, `pilot_people.json`

For MiamiOH MTH025C:

- raw Canvas export:
  - `institutions/miamioh/raw/canvas_export/mth025-h-c-export.imscc`
- derived bundle:
  - `institutions/miamioh/courses/250433/derived/`
- pilot overlays:
  - `institutions/miamioh/courses/250433/pilot/`

This layout keeps class-specific data separate from the browser runtime and gives future courses a predictable place to land.
