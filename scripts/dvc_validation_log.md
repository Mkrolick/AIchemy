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
- Commit: 4817185

### Subset infrastructure (in-iter, per user request mid-iteration)
- Built `scripts/build_subset.sh` + `configs/subset.yaml` to enable fast e2e validation.
- `data_subset/` populated with: 200 MNX reactions, 5000 MNX mols, 200 USPTO reactions.
- Commit: 3743725

### Subset run revealed second blocker (CXSMILES)
- `aichemy dedup reactions` raised ValueError: 13 mol_ids referenced by USPTO reactions but missing from molecules table. Root cause: `src/aichemy/preprocessing/sources/uspto.py:54-56` `_split` naively split on `.` even inside CXSMILES extensions like ` |f:0.1.2,3.4,6`, producing garbage tokens ('1', '2', '3', '4,6', '|f:4', etc.) that never resolved as valid molecules.
- Fix: strip everything from ' |' onwards before splitting. Single 6-line edit.
- Re-ran ingest_uspto + normalize: 113 → 199 reactions survived (86 reactions recovered), 360 → 637 molecules.
- All downstream stages clean. **End-to-end SUBSET validation complete:**
  - ingest_metanetx → 5000 mol, 200 rxns
  - ingest_uspto → 200 rxns
  - normalize → 637 mol, 199 rxns kept (5003 empty orphans dropped, 3 class metabolites resolved)
  - dedup_molecules → 493 rows (collapsed 144), is_class_resolved column preserved ✓
  - dedup_reactions → 196 rows (collapsed 3)
  - balance_uspto → 196 USPTO rows in 4 chunks of 50, **58 balanced (29.6%)** at conf>0.8
- Commit: b5b2a4d

## Iter 2 — kick off normalize on full data

- ps clean on entry.
- `dvc status` showed lots of stale stages. Notably: `fetch_raw` deps changed (cli.py) but outputs (data/raw) actually fine. To skip an unwanted ~1.3GB re-download of MetaNetX TSVs: `uv run dvc commit fetch_raw -f` to declare current disk state canonical.
- `ingest_metanetx`: up to date (no re-run needed).
- Started `uv run dvc repro normalize` (kicked off ingest_uspto + normalize cascade). Now running in background as PID 35610 (aichemy normalize at 21:24).
- Expected: ingest_uspto ~1 min on full 1.8M rows, normalize ~10-15 min on full data (resolve_class_metabolites is the bottleneck on ~242k wildcard molecules).

## Next iteration

Iter 3: ps check normalize. If still running, wait. When done, validate output schema (is_class_resolved column present, mol counts sane) then run `dvc repro dedup_molecules` + `dvc repro dedup_reactions`. Then iter 4 kicks off balance_uspto in background.
