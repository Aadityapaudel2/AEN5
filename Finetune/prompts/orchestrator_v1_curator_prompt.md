# Orchestrator Dataset V1 Curator Prompt

Generate **one YAML scenario record** for a math or logic orchestration example. Do **not** emit JSONL. Do **not** emit multiple records.

## Goal

Create a reviewable source card that can later be compiled into three role-pure corpora:
- `Orchestrator`
- `Solver-A`
- `Solver-B`

The scenario must teach **selective querying of two external models**. The domain is **math or logic only**.

## Hard Requirements

- The record must be syntactically valid YAML.
- The record must contain exactly these fields:
  - `id`
  - `domain`
  - `difficulty`
  - `problem`
  - `gold_answer`
  - `ambiguity_flag`
  - `recommended_routing`
  - `solver_a_draft`
  - `solver_b_draft`
  - `disagreement_notes`
  - `clarification_prompt`
  - `final_orchestration_action`
- `domain` must be `math` or `logic`.
- `difficulty` must be `easy`, `medium`, or `hard`.
- `recommended_routing` must be one of:
  - `direct_answer`
  - `query_solver_a`
  - `query_solver_b`
  - `query_both`
  - `clarify`
  - `disagreement_synthesis`
- `gold_answer` must be explicit and correct.
- `ambiguity_flag` must be `true` only when the user request is genuinely underspecified.
- `final_orchestration_action` must be exactly one of:
  - `<query target="solver_a">...</query>`
  - `<query target="solver_b">...</query>`
  - `<query target="both">solver_a: ...\nsolver_b: ...</query>`
  - `<clarify>...</clarify>`
  - `<answer>...</answer>`

## Role Purity

- Do not mix Orchestrator and solver behavior.
- `solver_a_draft` and `solver_b_draft` must use only:
  - `<answer>...</answer>`
  - `<confidence>high|medium|low</confidence>`
- Solver drafts must never include query tags.
- Avoid vague tutoring chatter, motivational language, or hidden reasoning.

## Dataset Intent

- Prefer selective routing over always querying both.
- Use `query_solver_a` when a direct formal derivation is the most relevant next move.
- Use `query_solver_b` when an edge-case or adversarial check is the most relevant next move.
- Use `query_both` only when dual evidence is actually justified.
- Use `clarify` when required information is missing.
- Use `disagreement_synthesis` only when drafts conflict and the orchestrator must reconcile them.

## Output Template

```yaml
id: orchestrator_math_001
domain: math
difficulty: medium
problem: |
  Solve 2x^2 - 7x + 3 = 0.
gold_answer: |
  x = 3 or x = 1/2
ambiguity_flag: false
recommended_routing: query_solver_a
solver_a_draft: |
  <answer>x = 3 or x = 1/2</answer>
  <confidence>high</confidence>
solver_b_draft: |
  <answer>x = 3 or x = 1/2</answer>
  <confidence>medium</confidence>
disagreement_notes: |
  
clarification_prompt: |
  
final_orchestration_action: |
  <query target="solver_a">Solve this math problem from first principles and return only &lt;answer&gt; and &lt;confidence&gt;.</query>
```
