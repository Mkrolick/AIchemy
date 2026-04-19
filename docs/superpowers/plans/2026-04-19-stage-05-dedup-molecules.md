# Stage 05 — dedup molecules

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 05 COMPLETE`.

**Goal:** Replace `aichemy dedup molecules` stub with real dedup: InChIKey equality is primary, Tanimoto=1.0 on Morgan fingerprints is a secondary collision check. Emit `data/interim/deduped/molecules.parquet` plus a `dedup_map.json` (or sidecar parquet) mapping every pre-dedup `mol_id` to its canonical ID.

**Status:** Stub writes empty parquet.

**Architecture:** `aichemy.preprocessing.dedup.molecules.dedup_molecules(df, config) -> tuple[pl.DataFrame, dict[str, str]]`. Primary test: group by `inchi_key`, pick a canonical `mol_id` for each group (MetaNetX ID wins over InChIKey-style, by lex). Secondary check: for any groups with mismatched canonical_smiles, fall back to Tanimoto=1.0 and log a warning (canonicalization bug signal). Union `source_refs` across group members.

## Tasks

### T1: `primary_group_by_inchi_key`

- [ ] Failing test: 4 rows, 2 share an InChIKey → returns 3 groups
- [ ] Implement: `df.group_by("inchi_key").agg(mol_id=pl.col("mol_id"), source_refs=pl.col("source_refs").flatten(), ...)`
- [ ] Commit

### T2: `pick_canonical_mol_id`

- [ ] Failing test: group with `["MNXM123", "VOMZLUQCCQVQTK-UHFFFAOYSA-N"]` picks `MNXM123`
- [ ] Failing test: group with only InChIKey-style IDs picks the lex-min one
- [ ] Implement: sort by (`starts_with("MNX")` desc, lex), take first
- [ ] Commit

### T3: `secondary_tanimoto_collision_check`

- [ ] Failing test: group with same InChIKey but divergent canonical_smiles (synthetic) — function detects mismatch and logs a warning with both SMILES; returns still-valid group
- [ ] Implement: within each group, compute morgan fingerprints and assert all-pairs Tanimoto == 1.0; if not, warn
- [ ] Commit

### T4: `dedup_molecules(df, config)` assembly

- [ ] Failing test: fixture molecules df with known duplicates → one row per InChIKey, canonical mol_id preferred, source_refs unioned; returned dedup_map has every old mol_id mapping to canonical
- [ ] Implement: chain T1-T3; build dedup_map explicitly
- [ ] Commit

### T5: Wire CLI

- [ ] CLI reads `normalized/molecules.parquet`, calls `dedup_molecules`, writes `deduped/molecules.parquet` + `deduped/dedup_map.json`
- [ ] Update `dvc.yaml` for the `dedup_molecules` stage's `outs` to include `dedup_map.json`
- [ ] CliRunner integration test
- [ ] Commit

### T6: End-to-end verification

- [ ] `uv run dvc repro dedup_molecules`
- [ ] `uv run pytest` all green
- [ ] Commit + push
