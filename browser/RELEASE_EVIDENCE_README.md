# Local release evidence

Generated candidate-validation artifacts for the Athena V5 public portal must not contain API keys, OAuth values, cookies, private prompt text, private continuity, or user data. Evidence distinguishes candidate implementation checks from deployment verification; a local evaluation is not proof that the public hostname served the candidate.

`TUTOR_BEHAVIOR_EVAL_2026-08-31.json` is the repository-safe aggregate for the repeated tutor release gate. It records the exact counts, critical gates, prompt identity, runtime profile, controller accounting, and SHA-256 of the full local evaluator artifact without publishing raw conversations.

The full evaluator artifact contains synthetic probe prompts plus both raw-model and post-controller outputs. Keep it local and transient. Its hash is sufficient to bind a reviewed local copy to the sanitized aggregate; do not move it into a public static directory, attach it to a public issue, or treat it as deployment verification.

Release evidence has three distinct layers:

1. implementation evidence: unit, syntax, security, privacy, behavior, and local functional results;
2. local presentation evidence: authenticated browser screenshots and keyboard/viewport checks;
3. deployment evidence: exact process replacement plus local and public post-launch smoke checks.

Passing an earlier layer never substitutes for a later one. If the in-app browser or public hostname cannot be verified, record that blocker and leave the existing production portal and tunnel unchanged.
