# Stage 02 — ingest metanetx

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 02 COMPLETE`.

**Goal:** Replace the `aichemy ingest metanetx` stub with a real parser over the MetaNetX TSVs, producing `data/interim/metanetx/molecules_raw.parquet` and `data/interim/metanetx/reactions_raw.parquet` that conform to the `Molecule` / `Reaction` patito schemas.

**Status:** Stub writes empty schema-valid parquets. Real parser needed.

**Inputs:** `data/raw/metanetx/{reac_prop.tsv, chem_prop.tsv, reac_xref.tsv, chem_xref.tsv}`. In the absence of Stage 01, tests use `tests/fixtures/metanetx_sample/` with ~20 hand-curated rows.

**Architecture:** `aichemy.preprocessing.sources.metanetx` gets three pure functions: `parse_chem_prop(path) -> pl.DataFrame`, `parse_reac_prop(path) -> pl.DataFrame`, `parse_reac_xref(path) -> pl.DataFrame`. Each handles MetaNetX's `#` header lines and tab delimiters. The `ingest_metanetx(config)` orchestrator reads all three, normalizes column names, extracts stoichiometry from `equation` field, and writes the two output parquets.

## Tasks

### T1: Build MetaNetX fixture

- [ ] Create `tests/fixtures/metanetx_sample/reac_prop.tsv` with ~5 hand-picked reactions (realistic MetaNetX format: `#` header, MNXR ID, equation, ECs, directionality)
- [ ] Same for `chem_prop.tsv` (~15 molecules: MNXM ID, name, reference, formula, charge, mass, InChI, InChIKey, SMILES)
- [ ] Same for `reac_xref.tsv` and `chem_xref.tsv` (cross-refs to KEGG/Rhea for a few rows)
- [ ] Commit fixture files

### T2: `parse_chem_prop` — molecules

- [ ] Write failing test: `parse_chem_prop(fixture_path)` returns `pl.DataFrame` with expected columns (`mnx_id`, `canonical_smiles`, `inchi_key`, `formula`, `mass`)
- [ ] Implement: use `pl.read_csv(comment_prefix="#", separator="\t")`; map MetaNetX columns to schema
- [ ] Commit

### T3: `parse_reac_prop` — reactions with equation → stoichiometry

- [ ] Failing test: `parse_reac_prop` returns df with `mnx_rxn_id`, `reactants: list[{mol_id, coefficient}]`, `products: list[...]`, `equation`, `direction`
- [ ] Implement equation parser: split on ` = `, each side is `N MNXM... + N MNXM... + ...`
- [ ] Commit

### T4: `parse_reac_xref` + `parse_chem_xref`

- [ ] Failing test for each; implement straightforward TSV parse returning `mnx_id`, `xref_source`, `xref_id` triples
- [ ] Commit

### T5: `ingest_metanetx(config)` orchestrator

- [ ] Failing integration test: call `ingest_metanetx(config_with_fixture_paths)` and assert two parquets land at expected paths, conform to `Molecule` / `Reaction` schemas, row counts match fixture
- [ ] Implement: call the three parsers, assemble into the unified `Molecule` / `Reaction` output shapes (`type="enzymatic"`, `source="metanetx"`, missing `yield_rate` filled with `None`/NaN for now — augment stage fills later)
- [ ] Commit

### T6: Wire CLI subcommand

- [ ] Replace `ingest_metanetx` stub in `src/aichemy/cli.py` to call real orchestrator instead of `write_empty_*`
- [ ] Integration test: run via CliRunner, verify output parquets have rows (not empty)
- [ ] Commit

### T7: End-to-end verification

- [ ] `uv run dvc repro ingest_metanetx` green
- [ ] `uv run pytest` all green
- [ ] `uv run ruff check . && uv run mypy src/` clean
- [ ] Commit + push
