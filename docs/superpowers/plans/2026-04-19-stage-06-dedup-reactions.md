# Stage 06 — dedup reactions

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 06 COMPLETE`.

**Goal:** Replace `aichemy dedup reactions` stub. Steps: (1) rewrite every reaction's reactant/product mol_ids through `dedup_map.json` from Stage 05; (2) hash by canonical reaction SMILES and drop exact duplicates; (3) Tanimoto cluster within hash-collision groups at `reaction_tanimoto_threshold` and collapse; (4) assert referential integrity — every mol_id referenced in reactions resolves in the deduped molecules table.

**Status:** Stub writes empty parquet.

**Architecture:** `aichemy.preprocessing.dedup.reactions.dedup_reactions(reactions, molecules, dedup_map, config) -> pl.DataFrame`. Sub-helpers: `rewrite_mol_ids`, `canonical_reaction_smiles`, `tanimoto_cluster_within_hash`.

## Tasks

### T1: `rewrite_mol_ids(reactions, dedup_map)`

- [ ] Failing test: reaction with reactants `[{mol_id: "A"}]`, map `{A: "B"}` → `[{mol_id: "B"}]`
- [ ] Implement using Polars struct mutation
- [ ] Commit

### T2: `canonical_reaction_smiles(reactants, products)`

- [ ] Failing test: given sorted mol_id lists, produces a stable hash-friendly string `"A.B>>C"`
- [ ] Implement: sort by mol_id then coefficient; concat with `.` then `>>`
- [ ] Commit

### T3: Hash-based dedup

- [ ] Failing test: 3 reactions with identical canonical form → 1 surviving row
- [ ] Implement: `df.with_columns(canonical=...)`; `group_by("canonical").agg(first())`
- [ ] Commit

### T4: Tanimoto cluster within hash-collision groups (optional refinement)

- [ ] Failing test: 2 reactions with near-identical but non-equal SMILES, Tanimoto=0.99 ≥ 0.95 threshold → collapse to 1
- [ ] Implement: group by hash, within each group compute reaction fingerprints (concat reactant + product fps), do Butina clustering at threshold
- [ ] Commit

### T5: Referential integrity assertion

- [ ] Failing test: if `rewrite_mol_ids` left a dangling mol_id, `dedup_reactions` raises
- [ ] Implement: after final rewrite, `set(all_reactant_mol_ids) - set(molecules.mol_id)` must be empty
- [ ] Commit

### T6: `dedup_reactions` orchestrator + CLI wiring

- [ ] Failing integration test: on tiny fixture, dedup works end-to-end and referential integrity holds
- [ ] Wire CLI: reads `normalized/reactions.parquet` + `deduped/molecules.parquet` + `deduped/dedup_map.json`, writes `deduped/reactions.parquet`
- [ ] Commit

### T7: End-to-end verification

- [ ] `uv run dvc repro dedup_reactions`
- [ ] `uv run pytest` all green
- [ ] Commit + push
