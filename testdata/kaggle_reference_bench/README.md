# Kaggle AIMO3 Reference Bench

This folder now mirrors the actual public AIMO3 reference bench rather than the earlier placeholder pack.

Primary public sources used:
- Studylib public mirror of the AIMO3 reference PDF: https://studylib.net/doc/28138782/aimo3-reference-problems
- Hugging Face public mirror / viewer: https://huggingface.co/datasets/UR-xiaoyang/AIMO3_CoT/viewer

What was fixed in this pass:
- Replaced the previous incorrect problem set with the actual 10-problem AIMO3 reference bench.
- Normalized OCR-compressed expressions like `105`, `220`, and `1010^5` into `10^5`, `2^20`, and `10^(10^5)` where the public mirrors clearly imply those forms.
- Added per-problem validity metadata in `manifest.jsonl`.
- Marked the few entries that still depend on OCR normalization so they can be treated more carefully during manual review.

Important note:
- Problem 7 required the most normalization because public OCR copies break both the ratio expression and the final exponent expression. The stored text is the best cleaned version consistent with the public answer key.
- Problem 6 also required formula normalization because OCR copies collapse exponents and separators.

Treat this pack as a strong public reference set for local inspection and comparison, while still preferring the official Kaggle rendering if you later copy problems directly into a notebook.
