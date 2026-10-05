# Stage 04 — normalize

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 04 COMPLETE`.

**Goal:** Merge the raw MetaNetX and USPTO interim parquets into unified `Molecule` + `Reaction` tables, apply canonical SMILES, apply carbon-count filter, and emit `data/interim/normalized/{molecules,reactions}.parquet`.

**Status:** Stub writes empty parquets. Core merge + canonicalize + filter logic needed.

**Architecture:** `aichemy.preprocessing.normalize` module owns `normalize(config) -> tuple[pl.DataFrame, pl.DataFrame]`. Internally:

1. Read MetaNetX + USPTO interim parquets.
2. Extract a universe of molecules (SMILES strings seen across both sources' reactions + MetaNetX's molecules table).
3. For each unique SMILES: canonicalize, compute InChIKey, count carbons. Assign a `mol_id` — MetaNetX ID if source had one, else the InChIKey.
4. Emit a Molecule table with no duplicates (by `mol_id`).
5. Rewrite each reaction's reactants/products to reference `mol_id` rather than raw SMILES.
6. Apply carbon filter: drop reactions where any participant has `carbon_count < cfg.filter.min_carbon_count`.
7. Emit merged Reaction table.

## Tasks

### T1: `collect_molecules` helper

- [ ] Failing test: given two tiny reaction dfs and one MetaNetX molecules df, returns a deduped set of `(canonical_smiles, source_refs)` tuples
- [ ] Implement using Polars concat + `group_by("canonical_smiles").agg(pl.col("source_refs").flatten())`
- [ ] Commit

### T2: `assign_mol_ids` helper

- [ ] Failing test: given a molecules df with some rows carrying `mnx_id` and others None, every row gets a `mol_id` (MNX when present, else InChIKey)
- [ ] Implement: `pl.when(col("mnx_id").is_not_null()).then(col("mnx_id")).otherwise(col("inchi_key"))`
- [ ] Commit

### T3: `rewrite_reaction_mol_ids` helper

- [ ] Failing test: given a reaction df with `reactants: list[{smiles, coefficient}]` and a SMILES→mol_id map, produces `reactants: list[{mol_id, coefficient}]`
- [ ] Implement
- [ ] Commit

### T4: `apply_carbon_filter`

- [ ] Failing test: table with 3 reactions — one all-heavy, one with water coproduct, one with H2 reactant. With `min_carbons=2`, only the first survives
- [ ] Implement: join each reaction's reactant/product mol_ids against the molecules df, check carbon_count per row
- [ ] Commit

### T5: `normalize(config)` orchestrator

- [ ] Failing integration test: on tiny MetaNetX + USPTO interim fixtures, emit normalized parquets that pass `Molecule.validate` / `Reaction.validate` and have expected row counts
- [ ] Implement: orchestrate T1–T4 in order
- [ ] Commit

### T6: Wire CLI

- [ ] Replace `normalize` stub with real call
- [ ] Integration test via CliRunner
- [ ] Commit

### T7: End-to-end verification

- [ ] `uv run dvc repro normalize`
- [ ] `uv run pytest` all green
- [ ] Commit + push
