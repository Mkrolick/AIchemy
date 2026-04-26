# DVC Pipeline Validation Log (Ralph Loop)

Goal: validate `uv run dvc repro` succeeds through `balance_uspto`.
Working branch: `dvc-pipeline-validation`.

## Iter 1 — fix dedup_molecules schema preservation

- ps clean (no DVC/aichemy running)
- Branch state on entry: was on `main`, switched to `dvc-pipeline-validation`. Noted concurrent commit `6fac430` (pricing-plans refinement) appeared on the branch — touches docs only, not blocking.
- Fixed `src/aichemy/preprocessing/dedup/molecules.py:71-89`:
  - Added `"is_class_resolved": template.get("is_class_resolved", False)` to canonical_rows dict (`.get` for safety so existing test fixtures still construct cleanly).
  - Added `"is_class_resolved": pl.Boolean` to schema_overrides on the deduped DataFrame construction.
- Tests: `pytest tests/unit/test_{dedup_molecules,io,normalize,resolve_class}.py -x` → 41/41 passed.
- Next: iter 2 will run `uv run dvc repro normalize`.
