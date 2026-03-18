# AIMO3 Smoke Log

## Scope

This note records the first terminal-visible headless smokes for the Kaggle submission surface.

## Validated Commands

### 2B baseline smoke

```powershell
& D:\AthenaPlayground\.venv\Scripts\python.exe -m desktop_engine.agentic.kaggle_smoke --problem "What is 2 + 7? Return only the final answer." --model-dir D:\AthenaPlayground\AthenaV5\models\Qwen3.5-2B --strategy baseline --no-tools
```

Result:
- raw answer: `9`
- normalized answer: `9`
- status: `baseline`
- rounds used: `1`
- solver repair path was used and still produced a clean strict marker answer

### 4B loop smoke

```powershell
& D:\AthenaPlayground\.venv\Scripts\python.exe -m desktop_engine.agentic.kaggle_smoke --problem "Solve 4 + x = 4 for x. Return only the final answer." --model-dir D:\AthenaPlayground\AthenaV5\models\Qwen3.5-4B --strategy loop --max-rounds 1 --no-tools
```

Result:
- raw answer: `0`
- normalized answer: `0`
- verified: `true`
- status: `solved`
- rounds used: `1`
- verifier passed cleanly in strict marker format

## Interpretation

- The headless Kaggle smoke surface is mechanically working.
- The AIMO3 answer normalization path is now aligned with plain integer output in `0..99999`.
- 2B is capable of producing a clean simple-answer baseline for trivial arithmetic.
- 4B can already execute the bounded solver-verifier loop coherently on a simple algebra sanity case.

## Observed Warnings

### Missing fast path kernels

Observed warning:
- `The fast path is not available because one of the required library is not installed. Falling back to torch implementation.`

Interpretation:
- this is a performance warning, not a correctness failure
- it matters for throughput and large-scale submission efficiency
- it does not block local smoke validation

### `top_k` ignored warning

Observed warning:
- `The following generation flags are not valid and may be ignored: ['top_k']`

Interpretation:
- the current Transformers path appears to ignore `top_k` in this runtime/model combination
- this should be treated as an inference-stack detail to revisit during Kaggle packaging
- it does not block baseline smoke correctness

## Next Recommended Steps

1. Run a fixed 10-20 problem local smoke pack across 2B, 4B, and 9B.
2. Compare baseline vs loop, not just one model size.
3. Only after that choose the Kaggle packaging target.
4. Then build the utility-notebook dependency path and final inference notebook.
