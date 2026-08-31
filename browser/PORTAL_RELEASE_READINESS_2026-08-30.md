# Athena V5 Public Portal Release Readiness

Date: 2026-08-30; continuation evidence added 2026-08-31
Status: Tutor candidate implemented, committed, and pushed after all non-visual critical gates passed; production rollout remains blocked on required browser visual QA.

## Outcome

The local portal candidate now presents an institution-neutral public entry point. With the current ignored production configuration, it advertises exactly Google, GitHub, and Guest sign-in. It does not advertise Institution access because no institution has a complete OAuth configuration, it does not mention MiamiOH in the rendered public entry page, and it does not automatically attach institution or course context to Google users.

Athena V5 remains the public interface. The required public inference identity is `Qwen3.5-4B`, displayed as `Qwen3.5-4B (base)`. The production preflight verifies that identity against the model actually served by vLLM.

## Completed checklist

- [x] Replaced duplicated sign-in markup with one shared sign-in-method partial.
- [x] Show Google only when its client ID and secret are configured.
- [x] Show GitHub only when its client ID and secret are configured.
- [x] Show Guest only when guest access is enabled.
- [x] Show an Institution dropdown only when at least one institution has a complete OAuth configuration.
- [x] Removed stale MiamiOH and pilot instructions from the rendered public login and landing surfaces.
- [x] Cleared the default institution in the active ignored deployment configuration.
- [x] Disabled automatic Google-to-institution attachment by default and in the active ignored deployment configuration.
- [x] Prevented dormant persisted institution/course context from entering ordinary public prompts unless institution context is explicitly active.
- [x] Added a neutral institution-deployment enquiry instead of presenting an unusable sign-in control.
- [x] Identified Athena V5 as the interface and Qwen3.5-4B base as the public inference model.
- [x] Added a public local-runtime explanation covering operational control, version stability, data routing, and the limits of local serving.
- [x] Kept the public system prompt independent of non-public continuity, hidden artifacts, and personal history.
- [x] Enforced the expected served model ID in production preflight and runtime health checks.
- [x] Reduced `/healthz` and `/api/config` to public-safe status fields; model paths, backend URLs, API credentials, and log roots are not returned.
- [x] Replaced reflected OAuth exception text with a generic public error while retaining internal logging.
- [x] Made `authlib` conditional: OAuth deployments require it, while a genuine guest-only deployment can still start without it.
- [x] Corrected WSL vLLM endpoint discovery so Windows persists and uses the reachable loopback endpoint instead of an unreachable/stale WSL guest IP.
- [x] Updated the public runbook, portal README, configuration reference, example environment, tests, and production preflight around the same contract.
- [x] Verified that the active secret-bearing configuration and generated runtime environment are ignored and untracked.

## Current deployment contract

| Capability | Current local production configuration | Public behavior |
| --- | --- | --- |
| Google OAuth | Configured | Shown |
| GitHub OAuth | Configured | Shown |
| Guest | Enabled | Shown |
| Institution OAuth | No complete institution deployment | Hidden; neutral enquiry remains |
| Default institution | None | No institution is preselected or implied |
| Google institution auto-attach | Disabled | Google sign-in does not add course context |
| Public model label | Qwen3.5-4B (base) | Disclosed on the public runtime page |
| Required served model ID | Qwen3.5-4B | Enforced in production preflight |

Institution support has not been deleted. It is now configuration-driven and dormant until a deployment has complete OAuth settings. A future institution can be added without restoring institution-specific claims to the generic Google button.

## Public/private boundary

The public candidate describes only the published interface, public model, public prompt, and account-scoped portal features. Non-public continuity, private checkpoint identity, hidden workspace artifacts, and personal relational context are not presented as part of the public model.

Internal institution adapters and privacy assertions remain available for controlled deployments and regression protection. They do not activate or render merely because an institution exists in the registry.

## Verification evidence

- Project unit suite: `49` tests passed.
- Python in-memory syntax compilation: passed.
- JavaScript syntax check: passed.
- Production preflight: passed.
- Advertised methods reported by preflight: `google, github, guest`.
- Production-mode rendered login: HTTP `200`; Google `true`; GitHub `true`; Guest `true`; Institution `false`; MiamiOH text `false`; runtime link `true`.
- Institution configuration probe: `0` sign-in-ready institutions; no default institution; Google auto-attach `false`.
- vLLM endpoint: reachable at Windows loopback through the existing WSL-served runtime.
- Served model: `Qwen3.5-4B`.
- Authenticated chat smoke with thinking disabled: exact response `PUBLIC_RUNTIME_OK`, finish reason `stop`.
- Public-surface privacy scan for stale pilot/institution/private-runtime wording: clean.
- Secret-file tracking check: active auth and generated runtime environment files are ignored and untracked.
- `git diff --check`: no whitespace errors; Git reports only expected LF-to-CRLF normalization warnings on Windows.

The production preflight warns that native Windows cannot import `vllm`; this is expected because vLLM is served through WSL. The endpoint itself and served model identity both passed.

## Intentionally not performed

- [ ] Commit changes.
- [ ] Push changes.
- [ ] Restart the portal process.
- [ ] Restart or modify the public tunnel.
- [ ] Deploy or publish the candidate to `portal.neohmlabs.com`.
- [ ] Perform interactive visual QA in the in-app browser; no controllable browser was available in this session.
- [ ] Complete real-account Google and GitHub callback tests; no unattended account actions were authorized.
- [ ] Verify the public domain after deployment; no deployment was authorized.

No local portal process was listening on port `8000` during the final read-only listener check. Nothing was started to compensate. The currently published portal should therefore be treated as unchanged until the approved rollout.

## Approval-time rollout sequence

1. Review this report and the scoped diff.
2. Start the candidate locally and inspect the landing, login, runtime, terms, privacy, and chat pages at desktop and narrow viewport sizes.
3. Smoke-test Guest, Google, and GitHub with authorized accounts; confirm no institution/course context appears for ordinary Google users.
4. If an institution is intentionally enabled, verify its complete OAuth record and dropdown behavior separately.
5. Run the production preflight again and require the exact served model ID.
6. Commit the reviewed candidate.
7. Restart the portal and public tunnel through the documented runbook.
8. Verify the public landing page, login page, `/runtime`, `/healthz`, and `/api/config`; confirm the status endpoints expose no paths, credentials, or backend URLs.
9. Push or publish only after the live checks pass.

## Rollback boundary

Because no commit, restart, tunnel change, or deployment occurred, the current work is only an uncommitted local candidate. Rollback before approval is simply a review decision about this scoped diff; no public rollback action is presently required.

## Later August 30 tutor deep-dive addendum

The institution-neutral portal pass above was followed by a separate tutor-runtime deep-dive. That pass added the unified tutor prompt compiler, tutor routing and controller contracts, governed learner-memory controls, a confident authenticated boot surface, guarded native/YaRN context profiles, and a live candidate behavior evaluator.

Later evidence supersedes the earlier test count without erasing it:

- complete unit and contract suite: `72/72` passed
- live candidate tutor probes: `7/7` passed
- stochastic greeting repetition after budget enforcement: `3/3` passed
- prompt profile: `public_athena_tutor_v1` version `2.0`
- final prompt SHA-256: `5946a3bd187e87a6c7ac6b63ae97992083898e5833f382fc8508d5005022b3c3`
- production preflight: passed against served model `Qwen3.5-4B`
- native context profile remains `128000`; experimental `yarn_1010k` remains dormant
- no commit, push, portal/model/tunnel restart, deployment, or publication occurred

See `ATHENA_TUTOR_DEEP_DIVE_2026-08-30.md` for the complete evidence ledger and `ATHENA_TUTOR_IMPLEMENTATION_PROMPT_2026-08-31.md` for the next-session objective and release gates.

## August 31 tutor implementation and gated rollout attempt

This section supersedes only the August 30 tutor test counts and runtime-action statements above. It preserves the earlier sanitization evidence as historical evidence.

### Outcome

The continuation workstreams are implemented. The final candidate passed every automated, security, functional, and model-behavior gate that can be completed without an interactive browser. Production was deliberately not replaced because the required in-app browser inventory was empty, so viewport, keyboard, focus, contrast, reduced-motion, menu-overflow, and screenshot inspection could not be honestly certified.

This is an implementation success and a deployment-verification blocker. It is not a failed public rollout: the production portal and named tunnel were never stopped, so rollback was not needed.

### Workstream completion

- [x] Expanded the evaluator to 30 distinct probes, repeated three times for 90 attempts.
- [x] Added raw-model and post-controller evidence, separate stage attribution, five scored dimensions, per-probe stability, critical-gate accounting, controller rescue accounting, and a zero-regression release requirement.
- [x] Covered every requested learner, educator, image, memory, injection, integrity, high-stakes, correctness, course/date, and learner-level scenario.
- [x] Implemented explicit Explain, Coach, Check work, Build practice, and Plan instruction response contracts.
- [x] Added direct-solution versus guided-hint routing, image-presence routing, useful-first broad-help behavior, educator no-blocking behavior, subject-neutral fallbacks, and high-confidence contradiction repair.
- [x] Added full learner-memory lifecycle controls: bounded recall, bounded/redacted export, account scoping, New Thread semantics, exact-confirmation Forget, and inert untrusted-memory framing.
- [x] Kept lexical recall rather than adding embeddings; the present bounded store does not justify a new dependency or deletion-index lifecycle.
- [x] Added accessible composer/log/status semantics, visible focus styling, reduced-motion rules, textarea autosizing, a bounded Memory menu, and starter actions that fill the composer without sending.
- [x] Added native and experimental context profiles, guarded YaRN activation, launcher dry-run, redacted previews, and intact WSL JSON argument handling.
- [x] Added the public tutor threat model, same-origin action checks, path-containment tests, raster signature checks, no-store export handling, security headers, public-status minimization, and stale/private marker scans.
- [x] Updated the runbook, portal/config references, memory architecture notes, behavior summary, and release evidence.
- [ ] Complete interactive visual and accessibility QA in an in-app browser.
- [ ] Replace the production portal/tunnel and execute public smoke checks. These actions remain gated by the preceding item.

### Final automated and model-behavior evidence

- Complete Python unit and contract suite: `98/98` passed.
- Python compilation: passed for the path, runtime, prompt compiler, portal server, and behavior evaluator modules.
- JavaScript syntax: passed for the portal client.
- PowerShell AST parsing: passed for all four release launch/tunnel scripts.
- `git diff --check`: passed with no whitespace errors; Windows line-ending notices only.
- Standalone public-runtime preflight: passed.
- `run_portal.ps1 -PreflightOnly`: passed.
- Public prompt: `public_athena_tutor_v1` version `2.0`.
- Prompt SHA-256: `64046e73413b03d5a75b8286ad1291236c905a0bd48a4f05a48dfcd01a917749`.
- Served model: `Qwen3.5-4B`.
- Active context profile: native `128000`.
- Experimental `yarn_1010k`: dormant; a dry run is rejected without explicit experimental authorization and never mutates runtime state.
- Behavior suite: `30` probes x `3` repetitions = `90/90` attempts passed (`100%`).
- Raw model stage: `73/84` applicable attempts passed (`86.90%`).
- Controller rescues: `14`; controller regressions: `0`.
- Stable probes: `30`; unstable probes: `0`.
- Critical gates: correctness `36/36`, privacy `6/6`, memory injection `6/6`, educator no-blocking `18/18`.
- Dimension averages out of two: correctness `2.0`, initiative `2.0`, pedagogical value `1.6667`, role fit `2.0`, mechanical compliance `2.0`.
- Sanitized aggregate: `TUTOR_BEHAVIOR_EVAL_2026-08-31.json`.
- Full transient evidence SHA-256: `207ff25e6f0415c0e9686340959baa997c2f1707d6d6321cd65fc30b1e681c59` (`469725` bytes).

### Local authenticated functional and security QA

A loopback-only production-mode preview ran on port `8010`; its launcher explicitly reported `tunnel=skipped(local-preview)`.

- Signed-out landing, runtime, privacy, and terms surfaces: HTTP `200`.
- Local `/healthz`: HTTP `200`.
- Google, GitHub, and Guest controls: present; no institution-specific public text.
- Google authorization initiation: HTTP `302` to the expected Google host.
- GitHub authorization initiation: HTTP `302` to the expected GitHub host.
- Guest authenticated shell: confident boot, tutor starters, New Thread, memory export, and Forget controls present.
- Real streaming turns: Learn a concept, Check my work, Build practice, and Plan instruction all completed with the tutor contract satisfied.
- Restored thread, New Thread, export, failed wrong-confirmation Forget, and successful exact-confirmation Forget: passed.
- Empty authenticated submission: rejected with HTTP `400`.
- Memory export: attachment disposition plus `no-store`.
- Missing action header and cross-site destructive action: rejected with HTTP `403`.
- Public security headers: passed for MIME sniffing, framing, content security policy, referrer policy, permissions policy, and API no-cache/no-store behavior.
- Static public marker scan: zero stale institution, private identity, personal path, or personal-account hits.
- Rendered public and authenticated marker scan: zero hits.

OAuth initiation is verified; completing real-account provider callbacks was not performed. No account credentials or callback tokens were captured in evidence.

### Runtime intervention and process custody

Sustained evaluation exposed a concrete vLLM health failure: generation throughput fell from roughly 30-35 tokens per second to roughly 2.5 tokens per second, five requests reached the 90-second timeout, and a short hint took 56.1 seconds. The exact old WSL API process and children were fingerprinted, then only that verified vLLM process was terminated. vLLM was relaunched on the native profile and recovered to roughly 30-36 generated tokens per second.

Final safe process evidence:

| Role | PID | State | Safe command evidence |
| --- | ---: | --- | --- |
| Existing production portal | `44808` | Still listening on port `8000`; not restarted | SHA-256 `c7522a83165d321dbe5915642642a2fc62c263f678e10d079e3127556706544b` |
| Loopback-only candidate preview | `38096` | Listening on `127.0.0.1:8010` | Portal marker verified |
| Existing named public tunnel | `15728` | Still running; not restarted | SHA-256 `66a3ebe1d71b58cac11b6ec74dd600008ffa2bb9b5ab77af159f2babe860ab4d` |
| Managed vLLM launcher | `39216` | Running after evidence-based recovery | SHA-256 `053ddc596a524177eefc11f760a7a5522246e13fac51305ac50a9917ba917222` |
| WSL vLLM API server | `370` | Listening through loopback on port `8001` | SHA-256 `7903bf3f1ad3f94285df708c4cfbfbf2bafe046a41c0488dc857248f5a373155`; native `128000`; no YaRN marker |

Raw command lines were deliberately omitted because runtime arguments can contain credentials.

### Workspace custody and scoped inventory

- Final observed branch: `main` at `34d20480f9db33c4dad94b61cda04286af911fd4`.
- The worktree was already dirty and remains dirty; unrelated modified and untracked material was preserved.
- At this evidence checkpoint, no commit or push had occurred. Repository publication is recorded in the later section below.

Material candidate surfaces changed or added by the combined public-portal and tutor passes:

- Runtime/configuration: `athena_paths.py`, `desktop_engine/runtime.py`, `desktop_engine/prompt_config.py`, `run_vllm.ps1`, `run_portal.ps1`, `browser/run_browser.ps1`, `browser/config/context_profiles.json`, `browser/config/system_prompt.json`.
- Tutor/security core: `browser/portal_server.py`, `browser/public_runtime_preflight.py`, `browser/tutor_behavior_eval.py`.
- Interface: `browser/portal/templates/index.html`, `browser/portal/templates/login.html`, `browser/portal/templates/_signin_methods.html`, `browser/portal/static/portal.css`, `browser/portal/static/portal.js`.
- Tests: the public portal, runtime, tutor, memory lifecycle, security, evaluator, and vLLM dry-run suites under `browser/tests`.
- Documentation/evidence: `browser/PUBLIC_RUNBOOK.md`, the portal and configuration READMEs, `browser/PUBLIC_TUTOR_THREAT_MODEL_2026-08-31.md`, `browser/RELEASE_EVIDENCE_README.md`, `browser/TUTOR_BEHAVIOR_EVAL_2026-08-31.json`, and the public memory architecture notes.

### Release blocker and exact continuation

The in-app browser inventory returned an empty list on every attempt. The browser-control contract prohibits treating HTTP/source inspection as visual QA. Therefore these required checks remain unverified:

1. Desktop wide, 1280px, tablet, and 390px layouts.
2. Keyboard-only navigation and visible focus order.
3. Contrast and reduced-motion behavior.
4. Memory-menu stacking/overflow and composer interaction.
5. Screenshots of empty, streaming, error, restored, New Thread, export, and Forget states.

Once an in-app browser is available, run those checks against the existing loopback preview. Only if they pass should the exact verified production portal and named tunnel be replaced through `run_portal.ps1`. Then verify local and public `/healthz`, the public `/AEN5` surface, all three sign-in choices, tutor starters, Check my work, educator mode, New Thread, memory export, and confirmed Forget. If any public smoke check fails, stop only the new verified portal process and restore the prior verified command fingerprint.

## August 31 repository publication

After the candidate and evidence above were sealed, the user explicitly authorized staging, committing, and pushing the verified release set.

- Release commit: `73ef635` (`feat: ship public Athena tutor experience`).
- Published branch: `origin/main`.
- Scope: the 36 portal, tutor, runtime-profile, security, test, and release-evidence files listed above.
- Excluded from the commit: unrelated frontier-problem material, local skill material, and the older untracked under-the-hood report.
- Pre-commit verification: `98/98` tests, both runtime preflights, Python compilation, JavaScript syntax, four PowerShell AST parses, staged whitespace check, and staged privacy/credential-shape scans all passed.
- Publication is not deployment verification. The candidate was pushed while the public portal and named tunnel remained stopped.
- The loopback-only candidate remains the visual-QA target; public launch remains gated on a connected supported browser.
