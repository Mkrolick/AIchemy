# Stage 03 — ingest uspto

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 03 COMPLETE`.

**Goal:** Replace the `aichemy ingest uspto` stub with a real parser over the Lowe USPTO reaction-SMILES dataset, producing `data/interim/uspto/reactions_raw.parquet`.

**Status:** Stub writes empty schema-valid parquet.

**Inputs:** `data/raw/uspto/` containing Lowe's reaction SMILES dump. Common formats: `.rsmi` (tab-separated ReactionSMILES + metadata) or `.txt.gz` with one reaction SMILES per line. Fixture-driven tests live in `tests/fixtures/uspto_sample/`.

**Architecture:** `aichemy.preprocessing.sources.uspto` provides `parse_reaction_smiles(rxn_smiles: str) -> dict` (splits `reactants>agents>products`, tokenizes each SMILES, canonicalizes), `parse_rsmi_file(path) -> pl.DataFrame`, and `ingest_uspto(config)` orchestrator. Yields are present in ~15% of Lowe rows (in a `yield_rate` or `Yield` column) — preserve if present, else NaN.

## Tasks

### T1: USPTO fixture

- [ ] Create `tests/fixtures/uspto_sample/reactions.rsmi` with ~10 rows: mix of yielded and non-yielded, some balanced, some with agents
- [ ] Commit

### T2: `parse_reaction_smiles` function

- [ ] Failing test: `parse_reaction_smiles("CC(=O)O.OC>>CCO.O")` returns `{"reactants": ["CC(=O)O", "OC"], "agents": [], "products": ["CCO", "O"]}`
- [ ] Test with agent form `CCO>[Pt]>CC=O`
- [ ] Implement: split on `>`, then `.` (respecting RDKit canonicalization optional)
- [ ] Commit

### T3: `parse_rsmi_file`

- [ ] Failing test: reads fixture, returns polars df with `rxn_smiles`, `yield_rate`, `patent_id` if present
- [ ] Implement: `pl.read_csv(separator="\t", has_header=True)` over the `.rsmi` file; rename columns to snake_case; preserve nullables
- [ ] Commit

### T4: `ingest_uspto(config)` orchestrator

- [ ] Failing integration test: produces Reaction-schema parquet with `type="chemical"`, `source="uspto"`, stoichiometric coefficients set to 1.0 (real stoichiometry comes from Stage 07 SYN-RBL)
- [ ] Implement: call `parse_rsmi_file`, apply `parse_reaction_smiles` row-wise (Polars `map_elements`), emit a reactions parquet
- [ ] Note: molecule-level dedup/canonicalization happens in Stage 04; USPTO ingest emits molecules implicitly via reactants/products lists with bare SMILES — Stage 04 normalizes to mol_ids
- [ ] Commit

### T5: Wire CLI

- [ ] Replace `ingest_uspto` stub with orchestrator call
- [ ] CliRunner smoke test: output parquet non-empty on fixture
- [ ] Commit

### T6: End-to-end verification

- [ ] `uv run dvc repro ingest_uspto`
- [ ] `uv run pytest` all green
- [ ] Commit + push
