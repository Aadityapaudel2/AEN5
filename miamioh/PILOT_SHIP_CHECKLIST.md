# MiamiOH Pilot Ship Checklist

## Auth
- Ensure `browser/config/portal_auth.env` contains:
  - `ATHENA_GOOGLE_CLIENT_ID`
  - `ATHENA_GOOGLE_CLIENT_SECRET`
  - `ATHENA_DEFAULT_INSTITUTION=miamioh`
  - `ATHENA_AUTH_PROVIDER=google`
  - `ATHENA_PORTAL_SESSION_SECRET`
- Canvas env vars may stay blank for this pilot.

## Course Context
- `institutions/miamioh/courses/250433/pilot/pilot_overrides.json` must exist.
- `institutions/miamioh/courses/250433/pilot/pilot_people.json` must exist.
- `institutions/miamioh/courses/250433/derived/content_chunks.jsonl` must exist.
- If the at-a-glance file changes, rerun:

```powershell
python D:\AthenaPlayground\AthenaV5\miamioh\build_canvas_bundle.py
```

- Before the live sign-in check, run the offline prompt smoke:

```powershell
python D:\AthenaPlayground\AthenaV5\miamioh\pilot_question_smoke.py
```

## Restart
- Restart the portal with the production script.
- Open the login surface and confirm `Continue with Google` is visible.
- Confirm the page copy says MiamiOH is detected automatically after Google sign-in.

## Acceptance Questions
Sign out completely, then sign in with a real `@miamioh.edu` Google account and verify:
- `What is this course about?`
- `When is Exam 2?`
- `When is the final?`
- `What should I know about discussions?`
- `Help me study for Quiz 6`
- `What is my name and what is my position?`

## Instructor Identity
- The current pilot resolves instructional role from `pilot_people.json`.
- `build_canvas_bundle.py` now seeds `pilot_people.json` from the at-a-glance guide.
- If the authenticated Google name matches the instructor of record in the course guide, Athena should treat the user as the course instructor.
- Student roster support can be added later by extending `pilot_people.json` with verified student records and emails.

## Pilot Guardrail
- The pilot is course-aware, but it does **not** claim live Canvas sync or personal due-date awareness.
- Schedule answers should come from the course at-a-glance guide and bundled course materials.
- Schedule answers should copy dates exactly as written in the course guide.
