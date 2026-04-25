# AIchemy — Running Catalog of Shortcuts, Deferrals, and Known Issues

**Purpose:** single source of truth for everything that was simplified,
stubbed, hardcoded, skipped, or deferred. When resuming work, check this
file before trusting the pipeline output.

Last updated: 2026-04-19

---

## 🔴 Critical — known to silently produce wrong results

### `delta_g` is all `None` for every MetaNetX reaction in `data/processed/reactions.parquet`
- **Why:** `augment_thermo` is wired into `dvc.yaml` but the eQuilibrator run was never actually executed end-to-end on real data. The 61,052 MetaNetX reactions get the placeholder `None` from ingest and never have it filled.
- **Impact:** the MILP solver doesn't apply any thermodynamic feasibility constraint. It could pick reactions that go uphill.
- **Fix:** run `uv run aichemy augment thermo --config configs/default.yaml`. Expected ~1–2 hr on 61k rows with `n_jobs=-1`. First run downloads ~100 MB of eQuilibrator tables.

### `CuratedPriceLookup` is wired, but never *run* against real molecules
- **Status correction:** As of the current `prices.py:367`, `make_lookup` does construct `CuratedPriceLookup()` when `"curated"` appears in the chain. So the code path is live.
- **What's still missing:** we've never actually executed `aichemy augment prices` against `data/interim/deduped/molecules.parquet` to measure catalog hit-rate. Based on MetaNetX ID naming conventions (MNX molecules rarely share canonical SMILES with catalog-common compounds) the real hit rate is probably low — maybe ~10–50 out of 1.29M.
- **Fix:** run `uv run aichemy augment prices --config configs/default.yaml`, then `pl.read_parquet('data/interim/augmented/molecules_priced.parquet').filter(pl.col('price_per_gram').is_not_null()).height`. Expected: 10–200 rows priced out of 1.29M. The solver's `default_buy_price=$1000/g` kicks in for the rest, which is probably still a bad default.

### Solver picks on real data have only been validated with **random prices**
- **Why:** Every time we've run the MILP on real MetaNetX data, we injected synthetic `random.uniform(0.1, 100.0)` per-gram prices. The $3,284.54 profit number you saw is arithmetic on random noise.
- **Impact:** we have zero evidence the solver picks chemically sensible products.
- **Fix:** fix the two bullets above, then re-run `aichemy solve`.

### MetaNetX reactions get `direction: "forward"` unconditionally
- **Why:** MetaNetX's `reac_prop.tsv` doesn't carry an explicit direction flag in the format we're parsing. Ingest (`metanetx.py:141`) sets `pl.lit("forward").alias("direction")` on every row. Some MetaNetX reactions are *actually reversible* or *reverse-only* in biochemistry.
- **Good news:** the `direction` column *is* produced at ingest and carried through subsequent stages (dedup/balance/augment are schema-preserving).
- **Caveat:** `data/processed/reactions.parquet` currently on disk was generated BEFORE the direction column was added, so the on-disk file doesn't have it. A fresh `dvc repro` will populate it.
- **Limit:** even after repro, the column is all `"forward"` so `apply_directionality(mode=DUPLICATE_REVERSIBLE)` finds nothing to duplicate.
- **Fix:** parse MetaNetX `mnet-spec.tsv` (per-model direction), OR compute ΔG'° and infer direction from sign.

### USPTO reactions assign `coefficient=1.0` to every participant
- **Why:** USPTO ingest doesn't parse stoichiometry. `src/aichemy/preprocessing/sources/uspto.py` writes `{"mol_id": smi, "coefficient": 1.0}` for every reactant/product unconditionally.
- **Impact:** mass-balance constraints in the MILP are wrong for any USPTO reaction that actually has non-unit stoichiometry (e.g. `2 H2O2 → 2 H2O + O2`). SYN-RBL can fix these if run, but we're not carrying its output back into the stoichiometry list.
- **Fix:** after SYN-RBL, re-parse the balanced SMILES to extract true coefficients and rewrite `reactants`/`products` structs. Non-trivial — at minimum a Polars `with_columns` that runs RDKit atom-counting to derive coefficients.

---

## 🟡 Substantial stubs / scale limitations

### SYN-RBL has never been run on full USPTO (1.8M reactions)
- **Status:** script `scripts/run_syn_rbl_full.py` exists with chunking + resume. Benchmarked to ~2.7 rxn/s single-threaded → ~8 days wall-clock single-machine. With `n_jobs=-1` (~10 cores) more like ~20 hours.
- **Two prior attempts crashed** early because SYN-RBL has internal pandas bugs that throw `KeyError: 0` on malformed USPTO SMILES. Wrapper now has `max_retry_depth=1` binary subdivide to limit blast radius, but still loses ~half a failing batch.
- **Current state:** only `3% of USPTO is balanced as-ingested`. Full-SYN-RBL recovery rate is extrapolated (~50–90% based on 50-row sample at 100%) but not measured at scale.
- **What's needed:** ~20 hours of wall-clock on a workstation. Can resume from partial shards.

### MILP solver does not scale to combined MetaNetX + USPTO network
- CBC (bundled solver) handles 42,760 balanced MetaNetX reactions in ~6 min. Adding even 100k USPTO reactions extrapolates to hours, and full ~1M USPTO will not terminate in useful time.
- **Two fallback options:**
  1. Buy/get Gurobi academic license (drop-in, ~10–100× faster).
  2. Pre-filter USPTO by patent class, year, or product of interest before normalize.

### No actual vendor scraping for prices
- **Status:** `ScraperBase`, `StructuredDataPriceScraper`, `BenchChemScraper`, `ChemicalBookScraper` classes exist but all require `scraper.enabled=True` in config (default: `False`) plus per-vendor `enabled=True` in the allowlist.
- **Why off:** ToS review per vendor required before enabling; I didn't do that review.
- **Coverage gap:** the curated catalog has ~120 entries. MetaNetX has 1.29M molecules. Even with 100% catalog match on common ones, the long tail is un-priced.

### ZINC bulk price data is NOT wired
- Plan was to download ZINC20 "purchasable" subset and use as a `ZINCPriceLookup`. Never implemented. The curated catalog is a hand-written stopgap.

### Patent scrapers exist but never hit a live endpoint
- `USPTOPatentsView` client is coded + tested with `pytest-httpx` mocks. Never run against the real patentsview.org API. Rate limits, output shape under real queries unverified.

---

## 🟠 Shortcuts in the preprocessing pipeline itself

### Balance validate uses `ignore_elements=["H"]` by default on MetaNetX
- **Why:** MetaNetX elides H+ protons by convention. If we enforce strict H balance, ~99% of MetaNetX reactions fail.
- **Tradeoff:** reactions that are *actually* off by H+/H- count are flagged as balanced. A protein-coupled electron transfer with mismatched H count will get a pass.
- **Cleaner fix:** run the `HEURISTIC_H` policy which actually inserts protons to balance, instead of ignoring them.

### SMILES `is_valid` / `parse` call path isn't perfectly robust
- On atom-mapped USPTO SMILES like `[Br:1][CH2:2][OH:4]`, RDKit produces a lot of warnings (suppressed by `RDLogger.DisableLog("rdApp.*")` in `syn_rbl.py` — applied globally once loaded).

### Hydrocarbon filter semantics relaxed from the proposal
- Proposal says "remove reactions with ≤1 carbon count among reactants or products". Strict reading: every participant needs ≥2 C. That kills ~99% of MetaNetX (every reaction involving H2O or H+).
- **What we do instead:** at least one ≥2-C participant *per side*. Keeps ~82% of MetaNetX.

### Normalize's `canonicalize_molecules` doesn't actually re-canonicalize SMILES
- It only populates `carbon_count`. The `canonical_smiles` column comes verbatim from MetaNetX's `chem_prop.tsv` (or USPTO's `mol_id`-as-SMILES). We don't actually run `Chem.MolToSmiles(mol, canonical=True)` on every molecule, so two MetaNetX entries with different-but-equivalent SMILES representations will not dedupe.
- **In practice MetaNetX is already canonicalized**, so this is fine for MetaNetX. For USPTO it's a real gap.

### USPTO mol_ids are raw atom-mapped SMILES
- When USPTO reactions flow into normalize, their `mol_id` fields are the raw SMILES strings from the `.rsmi` (e.g. `[Br:1][CH2:2][OH:4]`). The molecules table's `mol_id` column is also that string.
- **Result:** `dedup_molecules` only collapses *exact-string* USPTO molecules, not chemically-equivalent ones. And the solver creates LP variables named after these long strings — ugly but functional.
- **Fix:** in `extract_uspto_molecules`, use the canonical InChIKey as `mol_id` instead of the raw SMILES. Non-trivial because reactions also reference the raw SMILES.

### Yield imputation falls through to a $0.85 fixed value on enzymatic reactions
- MetaNetX reactions start with `yield_rate=None`. `global_mean_imputer` can't fabricate a mean from all-None. So with default config on real MetaNetX data, yields stay None until Stage 09 fills them... but with what? Currently it's whatever `PreprocessingConfig.yields.fixed_value=0.85` says. This is the proposal's "prior mean" but it's a single scalar applied uniformly.
- **Impact:** solver math treats every reaction as if it yields 85%, which is optimistic.

---

## 🔵 Scientific / correctness caveats

### MILP is missing proposal's fixed reaction costs (`φ_r · y_r`)
- The proposal §Sets and Parameters lists `φ_r` (fixed activation cost). We don't use it.
- **Would matter for:** differentiating cheap pathways (enzymatic, low capex) from expensive ones (requires new reactor).

### MILP is missing enzymatic catalyst amortization
- Enzymes deactivate over use. Proposal notes they enter as amortized cost. Not modeled.

### MILP is missing reaction-feasibility uncertainty (ASKCOS)
- Proposal suggests weighting `y_r` by ASKCOS-predicted reaction probability. Not wired.

### MILP is missing transition cost between enzymatic ↔ chemical
- Proposal §Todos. Not wired.

### Solver's `default_buy_price=$1000/g` penalty is hand-tuned, not derived
- When a molecule has no real price, buying it costs $1000/g (a penalty to discourage). That value is arbitrary. Should probably scale with some estimator of rarity (MW, complexity).

### The 120 curated prices are order-of-magnitude, not live data
- Based on 2024 academic-catalog memory (Sigma-Aldrich, Alfa Aesar, TCI). Real procurement varies ±2× with volume/purity/supplier/country. Use as anchors, not ground truth.

### Eval benchmarks are structurally correct but not yet run
- `aichemy.eval.benchmarks.summarize_solution(sol, molecules)` resolves solver output against a 6-molecule curated "known profitable" list. Has never been called on real solver output because we've never had real prices in the solver.

---

## 🟣 Tooling / infrastructure shortcuts

### CBC from pulp is x86-only on macOS
- **Workaround:** `brew install cbc` provides ARM-native CBC; `_make_solver` prefers system CBC if `shutil.which("cbc")` finds it.
- **Brittle:** breaks on fresh Apple Silicon without Homebrew. Also no CI coverage.

### SYN-RBL needs `libomp` on macOS
- **Workaround:** `brew install libomp`.
- **Breaks:** users who pip install aichemy without knowing this.

### eQuilibrator model cache is user-local
- First call downloads ~100 MB to `~/.cache/equilibrator/`. We don't pin a version — they could change the compound-contribution model and break reproducibility.

### DVC remote is a user-local path
- `.dvc/config` has `url = /tmp/aichemy-dvc-placeholder` (bogus); each user overrides with `.dvc/config.local`. If someone forgets, `dvc push` writes to `/tmp/` and they lose it on reboot.

### No CI for long-running tests
- `pytest -m slow` tests (full-network solve, SYN-RBL real-data run, eQuilibrator) are skipped by default. CI on GitHub Actions only runs the fast tests. Regressions in the slow path aren't caught until someone manually runs `-m slow`.

### Tests for `CuratedPriceLookup` don't exist
- Class is written, wired in `make_lookup`, never tested. Coverage gap.

### `data/processed/*.parquet` is stale
- The current files on disk were generated before several recent changes (USPTO molecule extraction, `direction` column add, `augment_thermo` DVC stage add, `CuratedPriceLookup` wire-in). Anything read from `data/processed/` today reflects an older pipeline version.
- **Fix:** `rm -rf data/interim/ data/processed/ && uv run dvc repro` once all fixes above are applied. Budget ~4 hours if eQuilibrator runs, ~minutes otherwise.

### Fixture coverage is thin
- MetaNetX: `tests/fixtures/metanetx_sample/` — ~10 molecules + 5 reactions hand-curated.
- USPTO: `tests/fixtures/uspto_sample/reactions.rsmi` — 4 hand-curated rows.
- **Gap:** no stress-test fixture for edge cases (charged species, metal complexes, non-unit stoichiometry, atom-mapped reactions).

### Deprecated Polars call
- Earlier benchmark scripts use `pl.count()` which emits `DeprecationWarning: use pl.len() instead`. Non-blocking but noisy.

### `augment directionality` in `ANNOTATE` mode is a no-op
- When `mode=ANNOTATE` (the default), `apply_directionality` returns the df unchanged. The CLI wiring runs it anyway and writes to a "reactions_full.parquet" file — fine, just a round-trip through parquet with no real transformation. Not a bug, just noted.

### ruff + black disagree on our line length for long SMILES
- `pyproject.toml` has a per-file ignore for `prices_curated.py` (`E501`) because some SMILES strings are >100 chars. Hack, not principled.

---

## 🟢 "Design choices" that look like shortcuts but are deliberate

### `backend="stub"` was the previous default, now `"chained"`
- We explicitly changed this when wiring curated prices. The stub path is preserved for tests + CI.

### Only `balanced=True` reactions enter the MILP
- This is the right call — unbalanced reactions break mass-balance constraints. It's documented as the first line of `build_and_solve`.

### USPTO is processed through normalize by extracting SMILES-as-mol_ids
- Not great chemically (no canonicalization, no InChIKey dedup) but avoids running RDKit canonicalize on 1.8M × ~10 fragments = very slow. A faster-but-less-rigorous tradeoff documented in `extract_uspto_molecules`.

### We never actually ran `dvc repro` end-to-end on both databases after adding USPTO molecule extraction
- The `augment_thermo` stage was added to `dvc.yaml` but `dvc.lock` is probably stale. Running `dvc repro` now would re-execute many stages.

---

## 📋 Prioritized next-session checklist

Copy this into your next work session:

1. [ ] Register `"curated"` handler in `make_lookup` factory (5 min)
2. [ ] Add unit tests for `CuratedPriceLookup` (10 min)
3. [ ] Run `aichemy augment prices` on real data; check catalog hit rate (~seconds)
4. [ ] Run `aichemy augment thermo` on 61k MetaNetX reactions (~1–2 hours)
5. [ ] Add `delta_g ≤ 0` constraint to the MILP for enzymatic rows (~30 min)
6. [ ] Re-run 50-reaction solver test with real prices + thermo; compare picks (~minutes)
7. [ ] Fix USPTO coefficient=1.0 bug (derive from SYN-RBL output) (~1–2 hours)
8. [ ] Measure catalog hit rate on full molecules table and decide if ZINC integration is worth the engineering (~30 min + decision)
9. [ ] `dvc repro` the full pipeline end-to-end and confirm output shape (~5 hr if augment_thermo is included)
10. [ ] Run `aichemy.eval.summarize_solution` on real solver output and record which known-profitable molecules the solver rediscovers

## 📁 Files to consult when in doubt

- `docs/superpowers/specs/2026-04-19-repo-layout-design.md` — overall architecture
- `docs/superpowers/plans/README.md` — stage roadmap with status
- `docs/superpowers/plans/2026-04-19-open-*.md` — per-open-item design
- `proposal.md` — original scientific proposal
- This file — what's actually (not) done
