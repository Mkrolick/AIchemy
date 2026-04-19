# Stage 12 — export

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 12 COMPLETE`.

**Goal:** Write final `data/processed/{reactions,molecules}.parquet` plus a `hypergraph_manifest.json` summarizing counts, schema versions, source-db versions, and date. Schema validation via patito on every emitted row; fail the stage if referential integrity is violated (a reaction's mol_id not in molecules).

## Tasks

### T1: `write_manifest(reactions_df, molecules_df, config) -> dict`
- [ ] Fields: `spec_version`, `generated_at`, `counts.reactions`, `counts.molecules`, `counts.balanced_reactions`, `sources.metanetx_version`, `sources.uspto_slice`, `config_hash`
- [ ] Failing test: manifest keys + count fields match inputs
- [ ] Commit

### T2: `assert_referential_integrity(reactions_df, molecules_df)`
- [ ] Failing test: reaction referencing unknown mol_id raises
- [ ] Implement: set-difference check
- [ ] Commit

### T3: `export(config)` orchestrator
- [ ] Read augmented reactions + priced molecules, validate both through patito, assert integrity, write final parquets + manifest.json
- [ ] Commit

### T4: Wire CLI + dvc repro verify the full DAG end-to-end
- [ ] Commit + push
