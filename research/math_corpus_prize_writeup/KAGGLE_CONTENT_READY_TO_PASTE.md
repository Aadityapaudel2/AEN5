# Canon DSL v2.1 + Runtime-at-Boot: Auditable Math Data

Mathematical datasets usually fail quietly. A row can look correct while the answer column is wrong. A generated problem can look new while the underlying route is shallow. A model can appear to solve a benchmark while it is really recalling an answer anchor.

This project is my attempt to make those failures visible.

The goal is not only to publish more math problems. The goal is to publish mathematical data with enough structure that another researcher can inspect it, mutate it, certify it, reuse it, and know which claims are safe.

The short version:

> Canon DSL v2.1 turns solved mathematical problems into auditable metadata records. Runtime-at-Boot turns those records and route contracts into role-specific study data, problem-proof repair records, and certification gates. VoE-2026 gives a small exact-answer evaluation surface for reproducible testing.

The project began as a Math Corpus Prize attempt: I wanted to build useful synthetic mathematics data, not only a benchmark. Over time it became clear that the important contribution was not simply "more rows." The important contribution was a way to make mathematical rows auditable, mutable, certifiable, and safe to reuse.

That is why the project grew from a raw math-corpus prototype into Canon DSL v2.1, Runtime-at-Boot, VoE-2026, and the AEN evaluation architecture. The early prototype contained useful mathematical seeds, but it also had processing mistakes and uneven difficulty. The cleaned contribution is the later metadata-first pipeline and dataset release path.

## Motivation: From Math Corpus To Auditable Runtime Data

My original goal was to make a mathematical corpus useful enough for people to train, test, and debate with. The hard lesson was that data quality is not just row count. For mathematical data, the hidden contract matters: answer type, route structure, verification method, mutation boundary, and contamination status.

So the project moved toward an audit-first view of math data.

Instead of asking only:

```text
Can we generate more problems?
```

the project now asks:

```text
Can we generate mathematical data with enough structure that another researcher can inspect it, certify it, mutate it, and know how it was used?
```

That is the reason for Canon DSL v2.1. It is the reason Runtime-at-Boot separates study rows from certification rows. It is also the reason V34 is labeled as answer-aware diagnostic data instead of being advertised as a blind benchmark result.

The broader motivation is community value. If we want open mathematical reasoning systems to improve, we need datasets that expose not only final answers, but also route contracts, failure modes, verification hooks, and contamination boundaries.

## Links

- Canon DSL v2.1 paper: https://zenodo.org/records/19694800
- Runtime-at-Boot Kaggle dataset: https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot
- VoE-2026 benchmark: https://huggingface.co/datasets/Neohm/VoE-2026
- VoE-2026 DOI: https://doi.org/10.57967/hf/8554
- AEN revision ledger: https://github.com/Aadityapaudel2/AEN_Architecture/tree/main/revisions
- V34 AIME-2026 Runtime-at-Boot diagnostic: https://github.com/Aadityapaudel2/AEN_Architecture/tree/main/revisions/2026-04-29-artifact-06-v34-full-test-run

## What Problem This Dataset Tries To Solve

Most math datasets are released as rows like:

```text
problem, answer, maybe solution
```

That is useful, but it hides many things that matter for synthetic mathematics:

- What objects does the problem define?
- What are the givens?
- What is the exact ask?
- What answer type is expected?
- What normalization rule applies?
- Which quantities are parameters and which are derived?
- What invariant or theorem makes the problem solvable?
- How can the answer be checked?
- If the problem is mutated, what changed structurally?
- Is this row safe for benchmark use, boot memory, certification, or only answer-aware repair?

Canon DSL v2.1 and Runtime-at-Boot are my attempt to make those hidden layers explicit.

The dataset is not meant to be only a pile of prompts. It is meant to be a set of inspectable mathematical records that can become different downstream views:

- rendered problems,
- solved examples,
- metadata records,
- problem-proof repair rows,
- answer-free boot-memory cards,
- certification gates,
- check reports,
- and exact-answer benchmark rows.

## What Canon DSL v2.1 Is

Canon DSL v2.1 is a YAML metadata schema for mathematical problem distillation.

Paper: https://zenodo.org/records/19694800

The Canon DSL paper defines it as a way to turn a solved mathematical problem into a structured record that can be inspected and reused for synthetic problem generation. Each record makes explicit:

- objects,
- givens,
- asks,
- parameter domains,
- invariants,
- theorem roles,
- answer normalization,
- solved-instance snapshots,
- computational checks,
- and generation lineage.

The central direction is:

```text
solved source problem
  -> Canon DSL metadata record
  -> rendered problem / mutation / check / Runtime-at-Boot row / benchmark row
```

The metadata record is the stable object. A rendered problem is only one projection of it.

This is different from ordinary model distillation. I am not trying to compress a model's answer. I am trying to distill the mathematical problem family itself.

## Full Canon DSL v2.1 Schema Skeleton

The core schema from the Canon DSL v2.1 paper is:

```yaml
schema_id: distillator_dsl.math.v2.1
schema_version: 1

identity:
  family_id: <semantic_slug_with__double_underscores>
  instance_id: <semantic_instance_id>
  short_name: <concise human title>
  generation: 1

taxonomy:
  domain: <algebra|number_theory|geometry|combinatorics|probability|calculus|linear_algebra|analysis|discrete_math|mixed>
  subdomain(s):
    - <short_phrase1>
    - <short_phrase2>
  topic_path:
    - <broad>
    - <narrow>
    - <specific>
  tags:
    - <keyword>

problem_spec:
  summary: <structural description of the problem type>
  object(s):
    - name: <symbol>
      type: <integer|real|point|matrix|polynomial|sequence|graph|function|set|other>
      role: <given|unknown|aux|output>
      dependency: <independent|dependent>
  givens:
    - <formal mathematical givens>
  ask:
    - <exact mathematical task>

answer_spec:
  type: <integer|integer_mod_m|rational|expression|count|set|object>
  normalization: <none|mod_m|p_plus_q|reduced>

family_structure:
  parameter(s):
    - name: <parameter_name>
      type: <int|real|enum|geometry_config|graph|function|other>
      domain: <decidable description>
      purpose: <what variation this parameter enables>
  invariant(s):
    - name: <invariant_name>
      depends_on: [<parameter_or_object>]
      statement: <formal invariant that must hold>
  operator(s):
    - <operator such as modular_reduction, recurrence, centroid, derivative, gcd_boundary_count>
  essential_assumption(s):
    - <assumption without which the problem is ill-defined>
  uniqueness_certificate(s):
    - <structural reason the answer is unique>

reasoning_components:
  technique(s):
    - name: <technique_name>
      inputs:
        - <mathematical structure>
      purpose: <why this technique is necessary>
      outputs:
        - <structural consequence>
  theorem(s):
    - name: <theorem_or_lemma_name>
      role: <what it guarantees or enables>
  closest_first_principle_concept_applied:
    - <e.g. Pigeonhole Principle, CRT, Pick's theorem, Vieta, Burnside>

solution_signature:
  critical_trick(s):
    - <indispensable ideas>
  finish_type: <closed_form|finite_enumeration|extremal_argument|counting_argument|constructive|existence_uniqueness|recurrence_based>

computational_context:
  preferred_language: <language>
  library(s):
    - name: <library>
      reason: <why this library is appropriate>
  import_hint(s):
    - <canonical symbolic imports, recordkeeping only>
  task(s):
    - name: <computational task>
      reason: <why computation is useful or necessary>

well_posed: <yes|no>

instance_snapshot:
  parameter_value(s):
    <parameter_name>: <value>
  final_answer:
    value: <as given>
    normalized: <postprocessed>
```

This schema is useful because it asks for the mathematical contract before asking for more generated rows.

## Canon DSL v2.1 In Plain English

Suppose we start with a solved number theory problem. A normal dataset row might store the statement and answer. Canon DSL asks for more:

- What are the variables?
- What is fixed and what may vary?
- What are the allowed domains?
- Which congruences, recurrences, or invariants control the route?
- What is the answer contract: integer, residue class, rational number, set, proof object?
- What is the normalized output form?
- What check would independently confirm the answer?

For example, a modular problem should not merely say "answer is 257." It should say:

- the final output is an integer modulo 1000;
- the canonical representative is in `{0,...,999}`;
- a bridge quantity is computed in one component and consumed by another;
- the recurrence or enumeration used for verification is explicitly named;
- and the instance snapshot binds the abstract family to concrete parameters.

That is the reason for the DSL. It makes the problem family machine-readable without requiring a full proof assistant.

## Why Canon DSL Can Produce High-Quality Math Data

Canon DSL improves data quality because it forces a generated problem to carry its mathematical contract.

In ordinary synthetic generation, a model can produce a plausible statement and a plausible answer while silently losing the route. Canon DSL makes that harder because the row must expose:

- the exact answer object,
- the normalization rule,
- the admissible parameter domain,
- the invariants that survive mutation,
- the theorem or lemma roles,
- the uniqueness certificate,
- and at least one check route.

This does not remove the need for a strong generator. In practice, high-quality synthesis still benefits from a very capable reasoning model or high-compute model, such as a GPT-5-Pro-class system or equivalent, because the generator must preserve constraints while changing the family. The DSL is not magic. It is a contract.

The important point is that once a good record exists, smaller inference models can use it. In the AEN experiments, Qwen-family roughly 9B-class role models used Canon/Runtime-at-Boot style route contracts as operating memory. They were not asked to invent the whole corpus from scratch; they were asked to solve with structured memory, certification, and role discipline loaded into context.

## How Canon DSL Synthesizes New Data

Here is a concrete synthesis pattern.

Start with a solved source family:

```text
Define m by two congruences.
Define n by two congruences.
Build a lattice triangle from m and n.
Use Pick's theorem to compute the number of interior lattice points.
```

Canon DSL distills this into:

- objects: `m`, `n`, `O`, `A`, `B`, `Delta`, `I`;
- givens: two CRT systems and a triangle definition;
- ask: compute `I`, the number of strict interior lattice points;
- answer type: integer;
- invariants: CRT uniqueness, determinant area, boundary gcd count, Pick's theorem;
- checks: exact CRT solution, determinant computation, gcd boundary count.

A compact Canon DSL record for this family would look like:

```yaml
schema_id: distillator_dsl.math.v2.1
schema_version: 1
identity:
  family_id: crt_lattice_triangle__pick_interior_count
  instance_id: crt_lattice_triangle__example_mutation_001
  short_name: CRT-defined lattice triangle interior count
  generation: 2
taxonomy:
  domain: number_theory
  subdomain(s):
    - crt
    - lattice_geometry
    - pick_theorem
  tags:
    - canon_v2_1
    - crt
    - lattice_points
problem_spec:
  summary: Compute CRT parameters, build a lattice triangle, and count strict interior lattice points.
  object(s):
    - {name: m, type: integer, role: aux, dependency: dependent}
    - {name: n, type: integer, role: aux, dependency: dependent}
    - {name: Delta, type: other, role: given, dependency: dependent}
    - {name: I, type: integer, role: output, dependency: dependent}
  givens:
    - m is the smallest positive integer satisfying two coprime congruences.
    - n is the smallest positive integer satisfying two coprime congruences.
    - Delta has vertices O=(0,0), A=(m,n), B=(m+n,m-n).
  ask:
    - Compute I, the number of lattice points strictly inside Delta.
answer_spec:
  type: integer
  normalization: none
family_structure:
  parameter(s):
    - {name: crt_moduli_for_m, type: int, domain: coprime positive moduli, purpose: determine m uniquely}
    - {name: crt_moduli_for_n, type: int, domain: coprime positive moduli, purpose: determine n uniquely}
  invariant(s):
    - {name: crt_uniqueness, depends_on: [m,n], statement: each CRT system has a unique residue class}
    - {name: lattice_area_determinant, depends_on: [A,B], statement: area is abs(det(A,B))/2}
    - {name: boundary_gcd_count, depends_on: [O,A,B], statement: boundary points are counted by edge gcds}
    - {name: pick_theorem, depends_on: [Delta], statement: area = I + B/2 - 1}
  operator(s):
    - crt_solution
    - determinant
    - gcd_boundary_count
    - pick_theorem
  uniqueness_certificate(s):
    - CRT fixes m and n; determinant and boundary gcds then uniquely determine I.
reasoning_components:
  theorem(s):
    - {name: Chinese Remainder Theorem, role: determine m and n}
    - {name: Pick's theorem, role: convert area and boundary count into I}
solution_signature:
  critical_trick(s):
    - Do not stop at area; boundary lattice points must be audited.
  finish_type: counting_argument
computational_context:
  preferred_language: python
  task(s):
    - {name: exact_integer_check, reason: recompute CRT, determinant, gcds, and Pick count}
well_posed: yes
instance_snapshot:
  parameter_value(s):
    m_congruences: ["m = 1 mod 5", "m = 2 mod 7"]
    n_congruences: ["n = 2 mod 9", "n = 3 mod 8"]
  final_answer:
    value: 108
    normalized: "108"
```

The prompt to synthesize a same-family problem can be as simple as:

```text
You are given a Canon DSL v2.1 metadata record for a mathematical problem family.

Generate one new problem instance from the same family.
Preserve the answer contract, theorem roles, and invariants.
Change the CRT residues and moduli while keeping moduli coprime.
Do not reuse the original constants.
After generating the problem, solve it exactly and emit:
1. rendered problem,
2. solution,
3. final answer,
4. updated instance_snapshot,
5. independent arithmetic check.

Reject your own output if Pick's theorem does not apply or if the final answer is not an integer.
```

Then we can synthesize a new same-family problem by mutating the parameters while preserving the contract:

```text
Define m to be the smallest positive integer satisfying
m = 1 (mod 5) and m = 2 (mod 7).

Define n to be the smallest positive integer satisfying
n = 2 (mod 9) and n = 3 (mod 8).

Let O=(0,0), A=(m,n), B=(m+n,m-n).
Let I be the number of lattice points strictly inside triangle OAB.
Compute I.
```

The generated instance has:

```text
m = 16
n = 11
A = (16,11)
B = (27,5)
det(A,B) = 16*5 - 11*27 = -217
area = 217/2
boundary points = gcd(16,11) + gcd(27,5) + gcd(11,6) = 1 + 1 + 1 = 3
I = area - B/2 + 1 = 217/2 - 3/2 + 1 = 108
```

So the generated answer is:

```text
108
```

The important part is not only that a new problem was created. The important part is that the generated problem can be audited against the same Canon DSL contract:

- CRT still gives unique `m` and `n`.
- The triangle is still a lattice triangle.
- The determinant area is exact.
- Boundary points are checked by gcd.
- Pick's theorem applies.
- The answer is still an integer.

That is the difference between schema-guided synthesis and loose paraphrase.

## Mutation And Difficulty

The paper emphasizes that mutation should change mathematical structure, not just wording.

Good mutations include:

- parameter coupling,
- bridge insertion,
- invariant swaps,
- answer-normalization changes,
- domain lifts,
- and check hardening.

A problem is stronger if one component computes a bridge quantity that a later component needs. That prevents a generated item from becoming two unrelated exercises stapled together.

Canon DSL requires the metadata to change when the problem changes. If a generated descendant changes from a polynomial-factorization route to a resultant route, then the theorem roles, invariants, operators, critical trick, and computational context should change as well. If they do not, the row is stale and should be rejected or rewritten.

## What Runtime-at-Boot Is

Runtime-at-Boot is a downstream dataset built from the same metadata-first philosophy.

It has two closely related data modes:

1. **Answer-free study/certification data**, represented by the cleaned v33 Runtime-at-Boot package.
2. **V34 diagnostic extension data**, represented by answer-aware repair rows for known misses.

These should not be confused.

The v33 package teaches general problem-class reasoning discipline without giving final benchmark answers. V34 is a diagnostic extension built after specific misses were known. It is useful for studying repair and context recall, but it is not a blind benchmark training set.

## Runtime-at-Boot v33: Study Rows And Certification Lines

The active public Runtime-at-Boot dataset is:

https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot

The cleaned v33 package contains **600 canonical rows**. This includes the certification data lines themselves; they are part of the Runtime-at-Boot dataset, not an external scoring script or a separate private artifact.

| role | study rows | certification rows |
| --- | ---: | ---: |
| Athena | 100 | 100 |
| Artemis | 100 | 100 |
| Aria | 100 | 100 |
| total | 300 | 300 |

The study rows and certification rows have different meanings, but both are first-class dataset components.

**Study rows are answer-key-free.** They may be used as boot memory. They teach reusable mathematical operating discipline.

**Certification rows are answer-bearing MCQ gates.** They prove that the boot memory loaded and can be applied. They should not be injected into ordinary solve prompts.

The mechanics are simple:

1. The runtime loads the role's answer-free study rows into the role session as boot memory.
2. The runtime then reads the matching certification lines for that role.
3. Each certification line asks a short MCQ about the invariant, ledger, or closeout rule from a study row.
4. The model answers the MCQ, and the gate records whether it chose the correct option.
5. If certification passes, the certified boot-memory transcript can be captured as the baseline before benchmark solving.
6. If certification fails, the run should be treated as a failed memory-load intervention rather than a valid Runtime-at-Boot solve.

The certification line is not random trivia. It is tied to a `study_source_id`, contains a `probe_prompt`, balanced answer choice, expected reasoning, option diagnostics, and the certified invariant.

For example, a certification row may ask:

```text
In a conditional_probability problem, what action preserves answer_object_identification?
```

The correct option is the one that opens the answer-object ledger and applies it before closeout. The wrong options are real failure modes: submit a plausible numeric object, treat peer agreement as proof, or ignore the output rule.

That is why the certification files are useful. They turn runtime memory into something testable.

## Runtime-at-Boot v33 Domains And Skills

The v33 boot memory is organized as a 10 by 10 grid.

10 domains:

- conditional probability,
- number theory modular,
- algebra functional equations,
- geometry coordinates,
- exact cover tiling,
- graph path state,
- temporal logic casework,
- answer contract integerization,
- inequality extremal,
- enumerative combinatorics.

10 transferable skills:

- answer object identification,
- event denominator ledger,
- branch case completeness,
- state vector recurrence,
- collision or injectivity audit,
- normalization rule lock,
- local obstruction certificate,
- independent arithmetic audit,
- peer disagreement gate,
- confidence ceiling closeout.

Each role receives 100 study rows, one for each domain-skill slot.

A typical study row contains:

- trigger,
- asked-object discipline,
- skill invariant,
- required ledger,
- unsafe shortcut,
- repair move,
- micro-transfer pattern,
- closeout rule,
- contamination guard.

This is not an answer key. It is structured reasoning hygiene.

## Experimental Evidence From AEN

The reason I believe this dataset direction matters is that it has already produced measurable behavior in AEN experiments with small fixed-weight role models.

AEN uses a triadic runtime: Athena, Artemis, and Aria. In the current experiments, these roles are served as Qwen-family roughly 9B-class model sessions under a controller. The dataset work matters because the controller does not only ask a model for a final answer. It loads role memory, certifies it, routes peer exchange, tracks disagreement, and owns finalization.

The public revision ledger shows three important signals:

| artifact | interpretation | score | mean tokens/question |
| --- | --- | ---: | ---: |
| April 27 benchmarkgrade AEN | answer-free efficiency result | 21/30 | 128,625 |
| April 28 Runtime-at-Boot v33 | negative diagnostic | 17/30 | 134,446 |
| April 29 V34 Runtime-at-Boot | answer-aware repair/context-recall diagnostic | 29/30 | 4,354,927 |

The April 27 run is the cleanest efficiency signal: a structured AEN runtime reached 21/30 on AIME-2026 Q1-Q30 while using far less average token budget than the unrestricted reference run.

The April 28 Runtime-at-Boot run is also important because it failed. It showed that simply loading and certifying answer-free boot memory does not automatically improve final answers. That is useful evidence: the architecture exposes failed interventions instead of hiding them.

The April 29 V34 run reached 29/30, or 96.7%, but it is answer-aware. It should be read as a context-recall and repair diagnostic, not a blind benchmark claim. It proves that Runtime-at-Boot memory can be loaded, certified, retained, and used by the role sessions. It also proves why contamination boundaries matter.

<p align="center">
  <img src="https://raw.githubusercontent.com/Aadityapaudel2/AEN_Architecture/main/revisions/visualizations/five_run_scoreboard_q1_q30.svg" width="560">
</p>

For the dataset, this is the key lesson:

> Canon DSL and Runtime-at-Boot are not only abstract schema work. They create measurable runtime behavior: memory loading, certification, recall, repair, verifier pressure, and auditable failures.

That is why I think this line of work can help the community. It does not merely report a score; it gives researchers a way to inspect what kind of data caused the score.

## How A Small Role Model Uses The Distillation

The practical value of the schema is that it turns a hard problem into a reusable route contract.

For example, in an AIME-style permutation problem, the useful distilled record is not just a final answer. The useful record says:

- answer object: count the valid maps under the stated condition;
- route hinge: a map from a finite set onto itself is a permutation;
- invariant: if `pi^6(a)=a` for every element, then every cycle length divides 6;
- audit target: reject branches that count arbitrary functions or allow 4-cycles and 5-cycles;
- closeout rule: submit only after the cycle-type ledger and normalization rule agree.

A small Qwen-family role model can use this as runtime memory. Athena uses it as a route plan, Artemis uses it as a proof audit, and Aria uses it to keep disagreement from collapsing into premature consensus. In answer-aware V34, the same mechanism can also recall answer anchors, which is exactly why V34 is treated as a diagnostic extension rather than a blind score.

## The Athena Dataset

Athena is the solver role.

Athena data focuses on route construction:

- identify the answer object;
- identify the route axis;
- choose the invariant;
- compute bridge values;
- maintain the output contract;
- and produce the final candidate.

Athena also has a Canon v2.1 schema database:

```text
canondatabase/Athena_100_HQ_canon_v21_schema.ndjson
```

Those records preserve Canon DSL-style YAML inside NDJSON rows. They are rich decomposition records containing:

- objects,
- givens,
- asks,
- invariants,
- techniques,
- theorem roles,
- critical tricks,
- finish types,
- answer-normalization contracts,
- computational checks,
- and instance snapshots.

In the local audit, the Athena Canon v2.1 database spans:

| source domain | rows |
| --- | ---: |
| number theory | 45 |
| algebra | 26 |
| discrete math | 9 |
| linear algebra | 7 |
| mixed | 4 |
| geometry | 3 |
| combinatorics | 2 |
| calculus | 2 |
| probability | 1 |
| analysis | 1 |

This makes Athena's data useful both as solver memory and as an example of full metadata-first problem decomposition.

## The Artemis Dataset

Artemis is the verifier and proof-pressure role.

This is one of the strongest parts of the package.

The Artemis v33 rows teach general verification discipline:

- do not accept agreement as proof;
- check the answer object;
- verify branch completeness;
- preserve normalization;
- look for local obstructions;
- run independent arithmetic;
- and refuse closeout when the ledger is incomplete.

The Artemis certification rows test whether that discipline loaded.

The answer-aware diagnostic rows go further: they are problem-plus-proof repair records. They include the actual problem statement, verified answer, observed wrong answer, route axis, proof hinge, failure mode, and role-specific audit instructions.

That is a useful problem-plus-solution shape. It does not only say what the answer is. It says why, what went wrong, what proof object matters, and what a verifier must check.

## The Aria Dataset

Aria is the agentic synthesis role.

Aria data focuses on coordination and state discipline:

- preserve alternatives,
- track unresolved blockers,
- compare peer candidates,
- identify the disagreement field,
- prevent premature consensus,
- and synthesize the route after proof pressure.

In v33, Aria receives the same domain-skill grid as Athena and Artemis, but under a different role contract. The same memory card becomes different behavior depending on role identity.

In V34, Aria's answer-aware repair rows also contain problem statements, verified answers, wrong-answer traces, route axes, and role-specific synthesis instructions. Aria's value is that it is designed to hold the debate state: which candidate is live, which route is supported, where the blocker sits, and when consensus is real rather than social.

That is useful for multi-agent reasoning experiments because many failures do not come from lack of computation alone. They come from bad arbitration.

## Why The Certification Lines Matter

Runtime-at-Boot certification is not just a label.

The certification rows make the memory layer measurable.

A study row might say:

```text
Skill invariant:
Name the object being asked for before solving; do not let a convenient intermediate become the answer.
```

The certification row then asks a non-isomorphic MCQ:

```text
What action preserves this invariant in this domain?
```

The correct option opens the appropriate ledger. The distractors encode realistic failures.

This gives the runtime a pre-solve gate:

```text
study memory -> answer MCQ -> certify loaded invariant -> proceed to solve
```

The important split is:

- study rows can be used as boot memory;
- certification rows prove loading;
- certification answer keys must not become solve-time memory;
- V34 answer-aware rows are diagnostic/problem-proof data, not blind benchmark memory.

That separation is the dataset's safety contract.

## VoE-2026 As A Benchmark Surface

VoE-2026, or Vault of Echoes 2026, is a 25-problem exact-integer reasoning benchmark released on Hugging Face:

https://huggingface.co/datasets/Neohm/VoE-2026

It has a public answer key and a DOI:

https://doi.org/10.57967/hf/8554

The schema is simple:

```csv
id,problem,answer
```

The answer contract is exact integer match.

Because the answer key is public, it should not be treated as a hidden benchmark after exposure. Its value is reproducibility, sanity checking, scoring examples, and public comparison. Future VoE volumes can move to hidden-key evaluation if needed.

## What The Community Can Use This For

### 1. Synthetic math data curation

Canon DSL can be used to turn solved problems into structured records before generating variants. This makes it easier to reject shallow rewrites and stale metadata.

### 2. Problem-family mutation

The schema gives a language for saying what changed between a source problem and a generated descendant.

### 3. Problem-plus-proof repair data

The V34 Artemis, Athena, and Aria rows are useful as answer-aware problem/proof repair data. They name the verified answer, the wrong answer, the proof hinge, and the repair route.

### 4. Verifier and critic training

The Artemis rows are especially useful for proof pressure, wrong-branch diagnosis, branch checks, normalization checks, and closeout discipline.

### 5. Multi-agent reasoning experiments

Athena, Artemis, and Aria give role-conditioned views of mathematical memory and repair. This supports experiments on solver-verifier-agent arbitration.

### 6. Runtime memory experiments

Runtime-at-Boot lets researchers ask whether preloaded memory helps, hurts, or contaminates problem solving.

### 7. Exact-answer evaluation

VoE-2026 gives a small public exact-answer surface with a simple scorer and answer contract.

### 8. Reproducible architecture evidence

The AEN revision ledger gives concrete experiment artifacts: answer-free efficiency runs, Runtime-at-Boot negative diagnostics, and answer-aware repair diagnostics. This makes the dataset useful not only as training material, but as a way to study what structured mathematical memory does inside a live reasoning architecture.

## Limitations

The earliest raw math-corpus CSV was not the clean final artifact. It had processing issues, including answer-column mistakes, and some seed problems were intentionally standard. Those rows should be understood as prototype material.

Canon DSL depends on source quality. If the solved source is wrong, or if the distillation is shallow, the metadata can be wrong. The schema improves auditability; it does not magically guarantee truth.

Runtime-at-Boot has a real contamination risk if answer-bearing certification rows or V34-style answer-aware repair rows are used inside ordinary solve prompts. That is why the dataset separates study rows from certification rows and why V34 is labeled as answer-aware diagnostic data.

VoE-2026 has a public key. It is reproducible, but not hidden after release.

The 29/30 V34 result should be understood as answer-aware repair evidence, not as a blind public benchmark score. The stronger answer-free efficiency claim is the separate April 27 AEN result. I include both because together they show the two sides of runtime memory: it can help structure reasoning, and it can also expose contamination when answer anchors are present.

These limitations are part of why the project is useful. They show why math datasets need provenance, boundary semantics, and audit records.

## Why This Matters For The Math Corpus Prize

The Math Corpus Prize is not only about making more problems. It is about making useful mathematical data.

This project contributes a way to make mathematical data more inspectable.

Canon DSL v2.1 gives a schema for problem-family metadata. Runtime-at-Boot shows how metadata and proof discipline can become study rows, certification gates, and problem-plus-proof repair data. VoE-2026 shows a small public benchmark release with exact-answer scoring.

The AEN experiments show why this matters in practice. With small fixed-weight Qwen-family role models, structured runtime data produced a strong answer-free AIME run, a visible failed Runtime-at-Boot intervention, and then a high-scoring answer-aware repair diagnostic. That is exactly the kind of evidence I want mathematical datasets to support: not only "what was the score?", but "what data entered the system, what did it certify, what failed, what was recalled, and what should be trusted?"

The main claim is modest but important:

> Synthetic mathematics should be released with enough structure that other people can inspect, mutate, verify, certify, and safely reuse it.

That is the contribution I hope the community finds valuable.

## Recommended Tags

- mathematics
- synthetic-data
- reasoning
- benchmark
- dataset
