# Stage 11 — augment directionality

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 11 COMPLETE`.

**Goal:** Apply MetaNetX's directionality flag: forward-only reactions kept as-is; reversible reactions either annotated or duplicated (forward + reverse rows) depending on config; USPTO reactions are always forward (no-op).

## Tasks

### T1: `apply_directionality(df, config, mode)`
- [ ] Mode `annotate`: add `direction: enum{forward, reversible}` column
- [ ] Mode `duplicate_reversible`: emit a second row for each reversible reaction with reactants↔products swapped
- [ ] Failing tests for each mode
- [ ] Commit

### T2: Wire CLI + dvc repro verify
- [ ] Commit + push
