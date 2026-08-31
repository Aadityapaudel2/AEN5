# AEN public portal

This directory contains the public browser surface for the Artificial Evaluation Network (AEN).

## Public identity contract

- **Athena V5** is the public interface name.
- The public interface never names, confirms, or speculates about implementation identity.
- Private Athena checkpoints, private continuity artifacts, LoRA behavior, and private relationship lore are outside this surface.
- Public copy must describe only capabilities and sign-in routes that are active in configuration.

The internal system prompt reinforces the same boundary: Athena identifies herself through her AEN tutoring purpose, never through backend implementation details, private memory, exclusive relationships, or hidden personal history.

## Tutor boot contract

The public tutor boots from the strict **public_athena_tutor_v2** profile. One shared compiler is used by the desktop engine and portal; the public portal fails closed instead of silently falling back to a generic one-line persona.

The profile and turn router enforce these operating rules:

- make a useful first move before asking for setup details
- ask at most one focused clarification when it is materially necessary
- draft educator artifacts immediately using visible assumptions
- inspect supplied images or documents instead of asking what item to inspect
- give a verdict first when checking work, then find the earliest error and verify
- use a hint ladder for guided tutoring
- provide a starter study cycle before requesting topic, level, or deadline

The empty chat surface exposes the same modes as starter actions: Learn a concept, Check my work, Build practice, and Plan instruction.

## Sign-in contract

The login page derives its choices from runtime configuration:

- Google appears only when both Google OAuth values are configured.
- GitHub appears only when both GitHub OAuth values are configured.
- Guest appears only when `ATHENA_GUEST_LOGIN_ENABLED=1`.
- Institution sign-in appears only for registry entries whose client ID, client secret, and redirect URI are all configured.
- Domain-based institution attachment is disabled by default. It requires the explicit `ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH=1` operator flag.

An entry in `browser/config/institutions.json` is only a dormant integration definition. It is not proof that the institution is participating or that its sign-in is active.

## Internal runtime boundary

Production startup validates the configured internal runtime and expected served identity. Those values belong in the ignored operator environment, not in the public interface or browser API:

```text
ATHENA_PUBLIC_MODEL_EXPECTED_ID=<exact internal served-model id>
```

NeohmLabs retains direct control over releases, runtime lifecycle, and request routing. That does not guarantee correctness or override the Privacy Notice. Users reach the public portal over the internet and should independently verify important outputs.

## Main files

- `templates/index.html`: combined public landing and authenticated chat shell
- `templates/login.html`: dedicated sign-in page
- `templates/_signin_methods.html`: canonical sign-in choices shared by both entry pages
- `templates/document.html`: AEN, SWARM, mission, and runtime documents
- `templates/legal.html`: privacy and terms pages
- `static/portal.css`: public portal styling
- `static/portal.js`: browser client
- `../portal_server.py`: FastAPI routes, auth, memory, and runtime adapter

## Public routes

- `/AEN5`
- `/AEN5/login`
- `/AEN5/aen`
- `/AEN5/swarm`
- `/AEN5/runtime`
- `/AEN5/mission`
- `/AEN5/privacy`
- `/AEN5/terms`
- `/AEN5/api/memory/status`
- `/AEN5/api/memory/export`
- `/AEN5/api/memory/forget`
- `/healthz`

## Auth configuration

Copy `browser/config/portal_auth.env.example` to the ignored `browser/config/portal_auth.env` and configure only the providers that should be public.

Required for every production launch:

- `ATHENA_PORTAL_SESSION_SECRET`
- at least one complete OAuth provider, one complete institution provider, or guest access

Provider pairs must be complete. A client ID without its matching secret is a preflight error, not a partially available sign-in method.

## Institution registry

`browser/config/institutions.json` may contain multiple Canvas-backed definitions. Each entry names its own environment variables. Only entries with all three of these resolved values are included in the public dropdown:

- OAuth client ID
- OAuth client secret
- redirect URI

Institution bundle data lives under `institutions/<institution-key>/`. Dormant bundles do not affect general Google, GitHub, or Guest sessions.

## Memory boundary

Public per-user state may include recent turns, stable learning preferences, session focus, and relevant recall as described by the Privacy Notice. Memory blocks have explicit precedence and are framed as reference data, never instructions. Prior assistant text is not treated as evidence of a user fact or preference. Course codes, institution identity, assessments, dates, and deadlines are not retained as durable learner-profile memory; current facts must come from the current user or verified current institution context. Signed-in email and authentication-source values are not sent to the tutor merely to provide continuity.

`New Thread` clears the current conversation and short-lived session focus while preserving the durable learner profile. The Memory menu can export learner continuity or explicitly delete conversation history, session focus, and durable learner preferences. Authentication profile and configured curriculum context are preserved by that learner-memory action.

## Validation

Before any deployment:

```powershell
Set-Location C:\path\to\AthenaV5
.\run_portal.ps1 -PreflightOnly
python -m unittest discover -s browser\tests -v
node --check browser\portal\static\portal.js
```

Also inspect the rendered login page with the production env loaded. It must show only the configured methods and must not expose backend paths, log roots, OAuth errors, or dormant institution/course metadata.
