# Canon DSL v2.1 Study Summary

This is a compact study guide for the Canon DSL v2.1 paper and how it should be explained in the Kaggle dataset writeup.

Paper:

```text
Canon DSL v2.1: Metadata-First Distillation for Synthetic Mathematical Data
https://zenodo.org/records/19694800
```

Local staged copy:

```text
N:\Research\Canon_DSL_v2.1
```

## Core Thesis

Canon DSL v2.1 treats a solved mathematical problem as a source for a structured metadata record.

The key claim is:

> The stable artifact should be the problem-family metadata contract, not only the rendered prompt and answer.

This matters because a prompt/answer pair is hard to audit. A metadata contract can expose what the generated problem is supposed to preserve: objects, givens, target, domains, invariants, route tools, answer normalization, and verification checks.

## The Distillation Loop

The paper's workflow is:

1. Start from a solved source problem.
2. Distill the source into a Canon DSL YAML metadata record.
3. Use the metadata record to render, forge, or mutate new problems.
4. Re-check the generated problem against the metadata contract.
5. Reject or revise stale metadata when mutation changes the mathematical obligation.

This is the important directionality:

```text
solved source -> metadata contract -> rendered problems / descendants / checks
```

The metadata is not decorative. It is the control layer.

## What The Schema Records

A Canon DSL record is intended to capture:

- problem identity and lineage;
- mathematical domain;
- declared objects;
- givens and unknowns;
- parameter domains;
- invariants;
- theorem and tool roles;
- solved-instance snapshots;
- answer contract;
- computational or symbolic checks;
- mutation notes;
- and release/provenance metadata.

For the Kaggle writeup, explain this as a way to make synthetic math data auditable rather than merely abundant.

## Mutation Philosophy

The paper distinguishes real mathematical mutation from superficial rewording.

A useful mutation changes the solver's obligation. For example, it may:

- add a bridge constraint;
- change parameter regimes;
- alter a boundary condition;
- introduce an invariant;
- require a different theorem role;
- or change the answer-normalization contract.

The metadata must change with the problem. If the generated problem changes but the metadata stays stale, the row should be rejected.

This is one of the most important points to highlight for the Math Corpus Prize: Canon DSL tries to make synthetic data quality inspectable at the family level.

## Checking Contract

Canon DSL does not replace formal proof assistants. It gives a practical data-engineering contract around generated math.

The checking layer can include:

- exact answer constraints;
- integer or modular answer contracts;
- symbolic checks;
- computational checks;
- consistency checks against parameter domains;
- and sanity checks for generated descendants.

The paper's relation-to-formalization section is useful here:

- Lean formalizes mathematical claims inside a proof assistant.
- Canon DSL formalizes metadata around mathematical problem generation.
- These approaches are compatible, not competitors.

## Production Case Study

The paper includes a production-style case study and a three-generation number-theory lineage.

The point of the lineage is not just that a model generated more problems. The point is that the descendant problems retain inspectable ancestry through metadata:

```text
source problem
  -> seed metadata
  -> generated metadata
  -> mutated metadata
  -> further generated descendant
```

This is how the writeup can answer "what sets this apart from other DSL submissions?"

The answer:

> Canon DSL is a problem-family metadata DSL. It is not only a prompt format, not only a model distillation trace, and not only a formal proof representation.

## Limitations From The Paper

The paper is clear that Canon DSL depends on the quality of the source and distillation.

Failure modes include:

- wrong solved source;
- shallow distillation;
- plausible but stale metadata;
- mutation that changes the problem without updating checks;
- and difficulty claims not backed by evaluation.

This limitation section is useful for the Kaggle response because it lets you acknowledge the original `math_corpus.csv` problems without collapsing the whole project.

## How To Explain It To The Community

Use this framing:

1. The raw early CSV exposed why synthetic math data needs stronger audit structure.
2. Canon DSL v2.1 is the proposed structure.
3. Runtime-at-Boot is one downstream projection of that structure into reusable role memory.
4. VoE-2026 is a separate exact-answer evaluation surface.
5. The community can use these pieces independently.

## Best Short Description

Canon DSL v2.1 is a metadata-first schema for turning solved mathematical problems into auditable problem-family records, so generated descendants can be inspected, checked, mutated, and packaged with provenance rather than released as opaque prompt-answer rows.
