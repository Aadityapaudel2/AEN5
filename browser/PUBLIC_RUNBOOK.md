# Public Athena V5 runbook

Operator runbook for the public AEN browser portal.

## Release contract

- Public interface: Athena V5
- Public implementation identity: not exposed by pages, browser APIs, or Athena responses
- Production backend and expected served identity: internal operator configuration
- Tutor prompt: strict named and hashed public profile
- Default context profile: native / 128000 configured tokens
- Public sign-in: only fully configured Google, GitHub, Guest, and institution routes
- Private Athena checkpoints and private continuity: excluded

## Required runtime pieces

- Python environment with the portal dependencies
- reachable internal inference endpoint
- locally configured public-candidate weights
- a non-default `ATHENA_PORTAL_SESSION_SECRET`
- at least one usable auth route: complete Google OAuth, complete GitHub OAuth, complete institution OAuth, or enabled Guest access

Authlib is required when any OAuth route is configured. A guest-only deployment does not require an OAuth client.

## Important settings

```text
ATHENA_RUNTIME_BACKEND=vllm_openai
ATHENA_PUBLIC_VLLM_ONLY=1
ATHENA_VLLM_BASE_URL=http://127.0.0.1:8001/v1
ATHENA_PUBLIC_MODEL_EXPECTED_ID=<exact internal served-model id>
ATHENA_DEFAULT_INSTITUTION=
ATHENA_GOOGLE_INSTITUTION_AUTO_ATTACH=0
```

Keep `ATHENA_DEFAULT_INSTITUTION` blank for the general portal. Enable an institution default or Google-domain attachment only for a deliberate, currently active deployment.

## Preflight

From the repository root:

```powershell
Set-Location C:\path\to\AthenaV5
.\run_portal.ps1 -PreflightOnly
```

Preflight validates:

- provider pairs are complete
- at least one sign-in route exists
- session secret is set
- vLLM backend selection is correct
- public model directory exists
- the served model is reachable when the runtime should already be running
- any configured institution has complete OAuth values
- the public tutor prompt contains every required boot, identity, routing, tutoring, educator, memory, mathematics, formatting, and default-mode section
- the native and guarded YaRN context profiles match their expected safety contract

## Non-disruptive candidate preview

Use the authenticated loopback-only preview before touching the production listener or tunnel:

```powershell
Set-Location C:\path\to\AthenaV5
.\run_portal.ps1 -LocalPreview
```

The preview binds to loopback, requires authentication, uses a localhost-compatible session cookie, and never starts the public tunnel. It may reuse the already healthy vLLM endpoint, but it must not restart vLLM merely to preview portal changes.

Before changing a context profile, inspect the exact resolved vLLM command without launching or stopping anything:

```powershell
.\run_vllm.ps1 -ContextProfile native -DryRun
.\run_vllm.ps1 -ContextProfile yarn_1010k -AllowExperimentalUltraLongContext -DryRun
```

Dry-run output redacts the API key. `native` must resolve to `128000`. A YaRN preview must remain opt-in and must not mutate the runtime state file or process tree.

## Start

```powershell
Set-Location C:\path\to\AthenaV5
.\run_portal.ps1
```

`run_portal.ps1` delegates to `browser/run_browser.ps1`, which reuses or starts the vLLM runtime and then starts the FastAPI portal.

Native Windows does not launch vLLM directly. Use WSL/Linux and follow `browser/WSL_VLLM_RUNBOOK.md`.

## Readiness checks

Check:

- `GET /healthz`
- authenticated `GET /AEN5/api/config`

Expected public fields include readiness, the Athena service identifier, and only the configuration needed by the browser client. Responses must not contain implementation identity, prompt metadata or text, runtime backend identifiers, model directories, backend URLs, log roots, API keys, OAuth secrets, or dormant institution course metadata.

## Live smoke before announcement

1. Open `/AEN5` in a signed-out browser.
2. Verify only configured sign-in methods appear.
3. Verify the page, `/healthz`, `/AEN5/api/config`, and Athena identity responses contain no model, provider, checkpoint, parameter-count, or backend disclosure.
4. Verify `/AEN5/runtime`, `/AEN5/privacy`, and `/AEN5/terms` load; the runtime route must describe service principles only.
5. Exercise each enabled sign-in route.
6. In chat, exercise Learn a concept, Check my work, Build practice, and Plan instruction; also test formatted output, inline math, `Stop`, and `New Thread`.
7. Confirm vague math or study requests receive a useful first move rather than a multi-question intake.
8. Confirm educator artifacts are drafted immediately with visible assumptions.
9. Confirm `New Thread` preserves the durable learner profile; test Memory export and confirmed Forget learner memory separately.
10. Confirm an ordinary Google account receives no institution or course context unless the explicit deployment flag is enabled.
11. If an institution is intentionally configured, verify its dropdown entry and Canvas callback separately.
12. At desktop, tablet, and narrow mobile widths, inspect layout, scrolling, focus visibility, keyboard operation, labels, live regions, and the Memory menu. Repeat with reduced-motion preference enabled.
13. Verify destructive browser actions reject cross-origin requests and require the portal action header.
14. Verify memory export is account-scoped, bounded, redacted, downloaded as an attachment, and served with `no-store`; verify an incorrect Forget phrase changes nothing before testing the confirmed phrase.
15. Test a greeting and a purpose question against an account with archived historical context; neither may resurrect an old course, assessment, date, or open loop.

## Tests

```powershell
python -m unittest discover -s browser\tests -v
python -m py_compile browser\portal_server.py browser\canvas_support.py browser\public_runtime_preflight.py browser\tutor_behavior_eval.py desktop_engine\prompt_config.py
node --check browser\portal\static\portal.js
python browser\tutor_behavior_eval.py --repeat 3 --max-tokens 800 --timeout 240
```

The release behavior run must contain at least 24 distinct probes, score at least 90% overall, record zero controller regressions, and pass correctness, privacy, memory-injection, and educator-no-blocking gates at 100%. Preserve the machine-readable evaluator artifact as release evidence; do not copy raw learner content or credentials into the operator report.

Also require PowerShell AST parsing for the launch scripts, a public-surface privacy-marker scan, `git diff --check`, and a final `run_portal.ps1 -PreflightOnly` immediately before rollout.

## Data layout and privacy

- User logs and memory remain outside public static assets.
- Institution data lives under `institutions/<institution-key>/`.
- Registry entries without complete OAuth values remain dormant and are not exposed in the dropdown.
- Local-first serving does not mean browser requests stay on the user's device; the Privacy Notice still applies.
- New Thread clears the current thread and short-lived focus but keeps durable learner preferences.
- The Memory menu provides signed-in export and an explicit confirmed learner-memory deletion action.

## Context extension

Do not confuse YaRN with learner memory. YaRN extends the inference token window; it does not select, govern, or protect remembered facts.

The yarn_1010k profile is dormant and requires the explicit AllowExperimentalUltraLongContext switch. It is intended for H100-class or equivalent deployments and should not be activated on the current 16 GB workstation. See research/QWEN35_CONTEXT_PROFILES.md.

## Rollback

Before rollout, resolve and record the exact portal listener PID, its parent chain, command lines, and the exact named Cloudflare tunnel process. Never use a broad process-name stop. Do not stop or restart the vLLM process when the existing endpoint is healthy and serves the expected model.

After all critical gates pass, replace only the verified portal and `portal.neohmlabs.com` tunnel processes through `run_portal.ps1`. Re-resolve process IDs after launch rather than assuming they were reused.

If any public smoke check fails, stop only the newly verified portal/tunnel processes and restore the previously approved portal command and configuration. Re-run local and public health checks after restoration. Do not weaken provider validation, expose an unconfigured institution, or switch context profiles as a workaround.
