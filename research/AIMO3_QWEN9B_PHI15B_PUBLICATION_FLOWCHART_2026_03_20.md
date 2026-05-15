# AIMO3 Publication Flowchart Note

Date: 2026-03-20

Primary asset:

- [AIMO3_QWEN9B_PHI15B_PUBLICATION_FLOWCHART_2026_03_20.svg](/d:/AthenaPlayground/AthenaV5/research/AIMO3_QWEN9B_PHI15B_PUBLICATION_FLOWCHART_2026_03_20.svg)

This figure is the publication-oriented version of the current bounded solver-verifier algorithm.

Serving note:

- the verifier checkpoint is `Phi-4-reasoning-vision-15B`
- the canonical runtime still serves it in `text-only` mode
- the publication flow assumes no image inputs, vision encoder passes, or multimodal profiling

## Intended interpretation

- Planning stage is a fixed two-step negotiation before solving begins.
- Solving stage is a bounded exchange loop.
- The solving loop must run for at least `2` exchanges.
- The solving loop may run for at most `11` exchanges.
- Final answer stage requires `2` consecutive verifier agreement checks on the same integer before reporting.

## Generation settings reflected by the figure

- Solver temperature band: `0.23` to `0.30`
- Verifier temperature band: `0.23` to `0.30`
- Solver max new tokens: `4096`
- Verifier max new tokens: `4096`
- Verifier thinking: `ON`
- Verifier serving path: `text-only`

## Phase summary

1. Planning Stage
   The solver proposes a plan, the verifier challenges it, and the solver consolidates a working plan plus unresolved risks.

2. Solving Stage
   The solver drafts, the verifier critiques, the solver revises, and the loop repeats under an explicit exchange counter.

3. Final Answer Stage
   The solver freezes a candidate final answer, the verifier checks it, the solver restates the same locked answer, and a second verifier agreement check is required before reporting.

## Supersession

This publication flowchart supersedes the earlier exploratory diagram:

- [AIMO3_QWEN9B_PHI15B_FLOWCHART_2026_03_20.svg](/d:/AthenaPlayground/AthenaV5/research/AIMO3_QWEN9B_PHI15B_FLOWCHART_2026_03_20.svg)
