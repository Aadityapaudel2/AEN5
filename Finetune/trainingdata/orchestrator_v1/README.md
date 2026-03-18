# Orchestrator Dataset V1

This package is the canonical source and compiled seed corpora for the minimal orchestration pipeline.

## Files

- `scenario_cards.yaml`: human-editable source of truth
- `orchestrator_seed.jsonl`: compiled orchestrator rows
- `solver_a_seed.jsonl`: compiled Solver-A rows
- `solver_b_seed.jsonl`: compiled Solver-B rows
- `manifest.json`: counts, route/domain splits, and token stats

## Build

From the repo root:

```powershell
python .\Finetune\tooling\builders\build_orchestrator_dataset.py --bootstrap --write --validate --token-stats
```

After the initial bootstrap, regenerate from the canonical YAML with:

```powershell
python .\Finetune\tooling\builders\build_orchestrator_dataset.py --write --validate --token-stats
```

## Notes

- The source cards are math + logic only.
- The compare GUI is intentionally not part of the source pipeline.
- Solver datasets stay role-pure and do not emit query tags.
- The orchestrator dataset teaches selective routing rather than defaulting to `query_both`.
