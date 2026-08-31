# Athena V5 Public Tutor Threat Model

Date: 2026-08-31
Scope: public Athena V5 portal candidate
Trust boundary: public Qwen3.5-4B base runtime, account-scoped learner data, configured curriculum sources, and the browser surface

## Security objectives

The public tutor must not reveal its system prompt, prompt path, backend URL, API credentials, OAuth values, session material, log root, another account's data, or private Athena continuity. Current user instructions may guide the tutoring task but cannot alter server policy. Memory and retrieved content may improve relevance but remain untrusted data. Destructive learner-memory actions must require an authenticated account, an explicit browser action, and exact confirmation where deletion is irreversible.

## Input surfaces and controls

| Surface | Principal risk | Candidate control | Verification |
| --- | --- | --- | --- |
| Current user text | Prompt extraction, role override, secret requests | Strict public prompt, public/private boundary, controller gate, bounded status output | Privacy and public-boundary behavior probes |
| Retrieved course excerpts | Instructions embedded in course content | Delimited untrusted excerpt block; current user and verified facts take precedence | Memory overlay contract tests |
| Recalled user or assistant text | Stored prompt injection or false user facts | Delimited untrusted recall; prior assistant claims are not user facts; clipped excerpts | Adversarial canary probe and memory lifecycle tests |
| Imported curriculum | Malicious policy or role text | Account/institution scope, normalized records, untrusted retrieved framing | Curriculum retrieval and public sanitization tests |
| Image content or OCR-like text | Visual prompt injection, malformed active content | Raster allowlist, file-signature verification, size/count limits, no SVG, image route remains subordinate to policy | Upload signature and image-route tests |
| Exported then reintroduced memory | Secret persistence or instruction laundering | Export redaction, size bounds, no credential-bearing keys, all reintroduced text remains untrusted user data | Export redaction/size tests and injection probe |
| Upload download path | Traversal or cross-account read | Resolved `Path.relative_to` containment under log root and authenticated user root | Prefix-sibling and traversal tests |
| Reset, Forget, logout | Cross-site request forgery | SameSite=Lax signed session plus required custom action header, Fetch Metadata rejection, Origin host check when present | Destructive-action security tests |
| Export response | Browser/proxy caching of learner data | `no-store, private`, `Pragma: no-cache`, attachment disposition | Response-header tests |
| Public status and health | Infrastructure disclosure | Allowlisted prompt identity and sanitized runtime metadata only | Runtime-status and privacy-marker scans |

## Memory bounds and deletion semantics

- Recent context is limited to eight completed turn pairs.
- Recalled older text is lexical, account-scoped, candidate-limited, and clipped before prompt assembly.
- Exported strings, turns, nesting, and total encoded payload are bounded. Credential-like keys and path/secret patterns are removed.
- New Thread deletes recent conversation and short-lived session focus while preserving the durable learner profile and resetting its `source_turn_count` to zero.
- Confirmed Forget deletes recent conversation, session focus, and the durable learner profile while preserving the sign-in profile and configured curriculum context.
- There is no embedding index in this candidate. Lexical recall remains appropriate for the current bounded per-account corpus, is dependency-light, and requires no separate deletion or rebuild path. If an embedding index is added later, Forget must delete its account partition and rebuilding must use only surviving account-scoped records.

## Browser protections

The portal applies no-store headers to API responses and sends `nosniff`, frame denial, a restrictive frame-ancestor policy, same-origin referrer policy, and a permissions policy. The current content policy permits the portal's own assets, required inline bootstrap configuration, and the MathJax CDN origin; it denies plugins/objects and cross-origin connections.

## Residual risks

- A language model can still produce incorrect or unsafe prose; release therefore requires repeat behavior evaluation and 100% critical gates.
- The custom action header prevents ordinary cross-site form submission but is not a substitute for preventing same-origin script compromise.
- The export redactor is defense in depth, not authorization; account scoping remains the primary isolation boundary.
- Image models can semantically follow malicious text rendered inside an otherwise valid raster. Prompt hierarchy and adversarial behavior tests remain necessary.
- Live OAuth callbacks depend on external provider state and must be smoke-tested without recording credentials or cookies.

## Release rule

Do not promote the candidate unless the full unit suite, production preflight, JavaScript/Python/PowerShell checks, privacy scan, repeated tutor behavior gates, authenticated browser QA, and public post-restart smoke checks all pass. If the public smoke fails after process replacement, restore the previous portal process configuration and record implementation success separately from deployment failure.
