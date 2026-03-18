# Agentic Math Loop

This package contains the headless `Solver + Verifier` math loop.

## Entrypoints

Single problem:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_math_loop.ps1 -Problem "What is 7 + 8?"
```

From a problem file:

```powershell
.\run_math_loop.ps1 -File .\evaluation\testdata\aimo\problems\algebra_complex_numbers_1.txt
```

Evaluation on a manifest subset:

```powershell
.\evaluate_math_loop.ps1 -Limit 25
```

Observer GUI:

```powershell
.\run_math_loop_observer.ps1
```

Kaggle-style submission build:

```powershell
.\run_kaggle_submission.ps1 -InputFile .\test.csv -OutputFile .\submission.csv -SampleSubmission .\sample_submission.csv
```

Single-problem Kaggle smoke in terminal:

```powershell
.\run_kaggle_smoke.ps1 -Problem "What is 7 + 8?" -Strategy baseline
```

## Notes

- Uses one shared `Qwen3.5-4B` runtime sequentially for both roles by default.
- The controller is rule-based.
- Calculator tool use is enabled by default in the loop.
- The loop is artifact-driven: solver and verifier calls are rebuilt from structured artifacts rather than conversational history.
- AIMO3-style submission defaults are now plain integers in the range `0..99999`, not zero-padded mod-1000 strings.