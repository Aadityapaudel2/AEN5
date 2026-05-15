# Reviewer Response Draft

Hello @philipvonderlind, @sambealing, and @friederrr,

Thank you for looking closely at the submission. Your questions identify the main weakness of the original last-minute package, and I agree with the concern.

The original `math_corpus.csv` should be treated as a prototype artifact, not as the cleaned benchmark-grade release. In the `nt20` example, the mathematical statement and worked seed solution give the correct answer `243`, but the exported `answer` column shows `3`. That is a processing/export bug, and any analysis that trusted the early CSV answer column directly would be affected.

The `alg_08` example is also fair criticism. Some early rows were intentionally standard seed problems. They are useful for schema sanity, answer normalization, and family construction, but they should not be advertised as hard benchmark items.

The contribution I would like to present in the writeup is therefore the improved dataset pipeline that came after the raw CSV:

- **Canon DSL v2.1:** a metadata-first schema for distilling a solved mathematical problem into a structured problem-family contract.
- **Runtime-at-Boot dataset:** a cleaned Kaggle dataset with answer-key-free study rows separated from answer-bearing certification gates.
- **VoE-2026:** a reproducible exact-integer public-answer benchmark released on Hugging Face with a DOI.

What sets my DSL apart is that it distills the **mathematical problem family**, not a model response. The stable object is the metadata contract: objects, givens, unknowns, invariants, theorem roles, parameter domains, solved-instance snapshots, answer normalization, and checking rules. Rendered problems, boot-memory rows, certification probes, and benchmark tables are downstream views of that contract.

The cleaned Runtime-at-Boot release has explicit boundary semantics:

- study rows are answer-key-free and may be used as runtime memory;
- certification rows contain MCQ answer keys and are only for proving the memory loaded;
- certification answers must not be injected into ordinary solve prompts.

This boundary is now documented in manifests and sanitize reports.

I will write the Kaggle writeup around this corrected framing rather than asking reviewers or the community to rely on the original raw CSV. Thank you for pointing directly at the parts that needed to be clarified.

Relevant links:

- Runtime-at-Boot dataset: https://www.kaggle.com/datasets/aadityapaudel/runtimeatboot
- Canon DSL v2.1 paper: https://zenodo.org/records/19694800
- VoE-2026 benchmark: https://huggingface.co/datasets/Neohm/VoE-2026
