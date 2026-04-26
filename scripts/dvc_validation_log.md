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

## Iter 3 — wait on normalize

- ps check: PID 35610 still running, 2:23 CPU at 21:26 (~3 min wall clock since 21:24 start).
- Output dir `data/interim/normalized/` empty (DVC cleaned it for fresh write).
- No action this iteration. Wait.

## Iter 4 — wait on normalize (still running)

- ps: PID 35610, 2:49 CPU (+26s since iter 3), ~4 min wall clock elapsed.
- Output dir still empty.
- No-op iteration.

## Iter 5 — wait on normalize (still running)

- ps: PID 35610, 3:14 CPU (+25s since iter 4), ~5 min wall.
- ~50% CPU utilization — single-threaded resolve_class_metabolites bottleneck.
- Estimate: 242k wildcards × ~5ms RDKit each = ~20 min total. Currently ~1/4 done.

## Iter 6 — wait on normalize (still running)

- ps: PID 35610, 3:47 CPU (+33s), ~6 min wall.
- Output dir empty.
- No-op iteration.

## Iters 3-9 — waiting on normalize

CPU progression (iters 3-30): 2:23 → ... → 12:00. Wall ~30 min, still no output written.

⚠️ Iter 30/60 burned. At current pace normalize will take another 5-10 min,
then dedup ~few min, then balance_uspto ~hours. Loop will hit 60-iter cap before
goal achievable. DVC processes keep running in background regardless.
Resolve_class_metabolites bottleneck (242k wildcards, single-threaded).

⚠️ Iteration budget concern: at this no-op cadence (~30s/iter wait per fire), we'll
hit the 60-iter cap before balance_uspto (2-4h) completes. Acceptable for now —
the background process will keep running even if the loop terminates. User can
re-set up a fresh monitor loop if needed.

## Next iteration

Continue ps-checking until normalize exits.

## Iter 32 — normalize done; dedup_molecules done; goal extended

- normalize finished at 21:36 (12 min wall total). Output: 1.3M molecules, ~250MB+279MB parquets.
  - is_class_resolved column present ✓ (resolver ran).
- dedup_molecules ran (during a partial earlier invocation that DVC picked up). Output: 1,302,619 rows with is_class_resolved=True for 4,453 mols. **Fix from iter 1 (4817185) confirmed working at full scale.**
- User extended GOAL: pipeline through `export` (data/processed/) including `augment_thermo` (delta_g). Updated ralph-loop.local.md completion phrase to DVC-PIPELINE-VALIDATED-THROUGH-EXPORT.

## Next iteration

Iter 33: ps check, then `uv run dvc repro dedup_reactions` (validates no missing mol_ids — was the bug we hit on subset).
