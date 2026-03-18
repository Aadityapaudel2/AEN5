# Adding a Course to `institutions/`

Use this layout for future institution/course bundles:

```text
institutions/
  <institution>/
    raw/
      ...
    courses/
      <course_id>/
        derived/
        pilot/
```

## Meaning

- `raw/`
  - upstream exports and source files
- `derived/`
  - normalized machine-readable files produced from raw sources
- `pilot/`
  - operator-managed overlays for schedule facts, people, or pilot-only adjustments

## Recommended steps

1. Create the institution root.
2. Place raw source material under `raw/`.
3. Build normalized artifacts into `courses/<course_id>/derived/`.
4. Add pilot overlays into `courses/<course_id>/pilot/` only when needed.
5. Point `browser/config/institutions.json` at the institution root.

## MiamiOH example

- institution root:
  - `institutions/miamioh`
- raw Canvas export:
  - `institutions/miamioh/raw/canvas_export/mth025-h-c-export.imscc`
- derived pilot course bundle:
  - `institutions/miamioh/courses/250433/derived/`
- pilot overlays:
  - `institutions/miamioh/courses/250433/pilot/`

## Do not mix responsibilities

- Do not put class-specific files in `browser/`
- Do not put live course data in `miamioh/`
- Do not store raw exports beside normalized bundle files
