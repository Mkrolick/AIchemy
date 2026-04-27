# Pricing-Scalability Validation Handoff (2026-04-27)

This doc summarises the Lambda validation cycle for `feat/pricing-scalability`,
captures the architectural changes that went in during the cycle, and lists
the pending decisions so the next person (or session) can pick up cleanly.

---

## TL;DR

- The 13 pre-existing commits on `feat/pricing-scalability` were validated
  end-to-end against the real PubChem corpus on a 64-core Lambda node.
- Two architectural commits were added during validation and pushed to
  `origin/feat/pricing-scalability`:
  - `54704be feat(pricing): direct DSN -> backend dispatch in augment_prices`
  - `859a0a3 feat(pricing): scripts/build_pricing_index_fast.py — SID-Map only + parallel`
- End-to-end coverage on a 493-mol subset (MetaNetX + USPTO) is **16.8%**
  (83 priced). Fluorochem is the working backend (70.8% per-call hit rate);
  Enamine, ChemCruz, and MedChem parsers are largely 0% — separate follow-up.
- All 116 pricing tests + 47 top-level unit tests still pass.
- The branch is 15 commits ahead of `origin/pricing-integration` (PR base)
  and ready for PR open / refresh.

---

## What changed in this cycle

### 1. Direct DSN → backend dispatch (`54704be`)

`ChainedPriceLookup` fans every `(vendor, sku)` ref across every chain
member sequentially, even though resolver hits already carry the
authoritative DSN. At full scale this drove ~5× the necessary HTTP calls
and the L3 Browserbase Browser API (~10 s/call session setup) dominated
wall-clock — Tocris read-timeouts and Browserbase fall-through accounted
for the bulk of "wrote 0 rows" runs.

The augment_prices path now uses a DSN-keyed dispatch table built by
`build_default_dispatch(cache_path)`:

| DSN | Vendor (display) | Backend | Parser key |
|---|---|---|---|
| `29665` | Fluorochem | `FluorochemVendor` (L1) | n/a |
| `959`   | MedChemexpress MCE | `MedChemExpressVendor` (L2) | n/a |
| `25659` | Santa Cruz / ChemCruz | `BrowserbaseFetchLookup` (L3a) | `chemcruz` |
| `822`   | Enamine | `BrowserbaseBrowserLookup` (L3b) | `enamine` |

Hits with unmapped DSN (Sigma-Aldrich, Cayman `843`, broken Tocris `10600`)
are skipped — their parsers either don't exist or are broken anyway, so
the chain fan-out was just paying timeouts to confirm they wouldn't quote.
`DirectDispatchInchikeyLookup` mirrors `ChainedPriceLookup`'s swallow-and-
log on per-hit exceptions so one parser bug doesn't abort the whole
InChIKey. `VendorRewriter` rewrites `ref.vendor` to the parser-registry
key (e.g. `25659` → `chemcruz`) so L3 lookups see what they expect.

Drive-bys in the same commit:

- `TocrisVendor` removed from `_DEFAULT_VENDOR_CLASSES` (HTML restructure;
  see `docs/superpowers/findings/2026-04-26-pubchem-resolver-empirical-findings.md`).
- L3 Browser API gated out of `build_default_chain` — only the `enamine`
  parser is registered there and every non-enamine ref ate ~10 s session-
  setup with no upside. Direct dispatch re-uses `BrowserbaseBrowserLookup`
  gated by DSN.
- `FluorochemVendor` returns `None` on volume-only units (`'ml'`, `'l'`)
  instead of raising `KeyError` on liquid SKUs.

### 2. Fast resolver build (`859a0a3`)

`scripts/build_pricing_index_fast.py` produces a parquet schema-identical
to `PubChemCompoundResolver._persist` in ~5 min on a 64-core node, vs the
~3 hr single-threaded `from_files` builder.

- SID-Map's 4-column format already carries `(SID, source_name,
  source_reg_id, CID)`, so the full pass-1 Substance scan collapses into
  the SID-Map walk (~90 min saved).
- The Compound scan parallelises trivially via `ProcessPoolExecutor`.
  Workers receive the needed-CIDs set once via initializer, not per-task.
- DSN → display-name mapping is hardcoded for the seven curated vendors
  in `configs/default.yaml` (verified 2026-04-27 by sampling SID-Map.gz
  column 2).

Tradeoff: `canonical_url` is `None` for every row (SID-Map carries no
URL). The full 3-pass `from_files` build still populates URL when needed.
The validation contract doesn't read `canonical_url`.

Lambda 64-core measurement (data already on disk):

```
pass 1 (SID-Map walk):  142s -> 5.30M unique CIDs / 5.77M matches
pass 2 (Compound x64):  136s -> 5.30M InChIKey hits
pass 3 (JOIN+persist):    7s -> 5.77M rows / 5.30M unique InChIKeys
total:                  286s end-to-end
```

---

## Validation result

Subset: `data_subset/` built via `scripts/build_subset.sh` defaults
(5,000 MetaNetX molecules + 200 USPTO reactions → 493 deduped molecules).

```
total molecules:   493
priced molecules:  83
coverage:          16.8%

$/g distribution:
  min     0.067
  25%     0.31
  median  0.64
  75%     6.65
  max     20000.0

vendor breakdown (from cache):
  vendor              calls    quoted  hit-rate
  29665 (Fluorochem)    113        80     70.8%   <- working
  822   (Enamine)       177         3      1.7%   <- parser stale
  25659 (ChemCruz)      117         0      0.0%   <- parser stale
  959   (MedChem)        34         0      0.0%   <- parser stale
```

Fluorochem is the dominant working backend. The other three parsers
return ~0% — likely HTML drift similar to the Tocris case. Fixing them
is out of scope for this PR but explicit follow-up work.

Wall-clock comparison (493-mol subset, `max_workers=100`):

| Run | Result |
|---|---|
| Chain w/ Tocris + L3 Browser | ~27 min, did not finish |
| Chain w/o Tocris + L3 Browser | ~22 cache rows/sec, projected ~6 min |
| Direct dispatch | **~5 min total** |

---

## Reproduction on a fresh box

```bash
# 0. clone + checkout
git clone https://github.com/Mkrolick/AIchemy.git && cd AIchemy
git checkout feat/pricing-scalability

# 1. raw data (~1 hr; PubChem dominates)
bash scripts/download_pubchem_substance.sh   # 84 GB
bash scripts/download_pubchem_compound.sh    # 108 GB
bash scripts/download_pubchem_sid_map.sh     # 3.5 GB
uv run aichemy fetch-raw --config configs/default.yaml
uv run python -c "import py7zr; py7zr.SevenZipFile('data/raw/uspto/grants_smiles.7z').extractall('data/raw/uspto/')"

# 2. fast resolver index (~5 min on 64-core)
uv run python scripts/build_pricing_index_fast.py

# 3. small-subset preprocessing
bash scripts/build_subset.sh
uv run aichemy ingest metanetx --config configs/default.yaml --override configs/subset.yaml
uv run aichemy ingest uspto    --config configs/default.yaml --override configs/subset.yaml
uv run aichemy normalize       --config configs/default.yaml --override configs/subset.yaml
uv run aichemy dedup molecules --config configs/default.yaml --override configs/subset.yaml

# 4. price the subset
export BROWSERBASE_API_KEY=...
uv run aichemy augment prices  --config configs/default.yaml --override configs/subset.yaml

# 5. read coverage
uv run python -c "
import polars as pl
df = pl.read_parquet('data_subset/interim/augmented/molecules_priced.parquet')
priced = df.filter(pl.col('price_per_gram').is_not_null())
print(f'{priced.height}/{df.height} priced ({100*priced.height/df.height:.1f}%)')"
```

---

## Pending decisions (handoff)

1. **Open / refresh PR.** Branch `feat/pricing-scalability` is 15 commits
   ahead of `origin/pricing-integration`. PR title suggestion:
   `feat(pricing): allowed_sources + parallel + direct DSN dispatch + 3-way JOIN`.
   The PR body can use the 15 commit messages as the skeleton.

2. **Merge `main` into the branch?** `origin/main` is 47 commits ahead with
   the licensing pipeline (`patents fetch / classify-cpc / classify-llm /
   augment_licenses`), `select_reactions`, MILP solver with royalties +
   sweep, and `29917e8 fix(solver): derive unpriced molecule defaults from
   empirical price distribution`. Merge dry-run is conflict-free — none of
   those commits touched the files this PR modified. Decision is whether
   the full `patents → augment_licenses → augment_prices → solver` chain
   should run from this branch or from `main`.

3. **Where to run the full pipeline?** Lambda has all raw data and the
   built index. Mac-mini has populated DVC interim from `main`. Three
   pragmatic paths:
   - **Lambda re-run from raw** — clean state, ~30–90 min full chain
     after merging main into the branch.
   - **rsync interim from Mac-mini → Lambda, run only pricing** — fast
     iff the upstream stages (ingest/normalize/dedup/balance/select) are
     untouched between branches. Note: the new dispatch only changes the
     `aichemy_pricing` subtree; it does not affect upstream parquets.
   - **Stay on Mac-mini** — slow (estimated 7+ hr for full pipeline vs
     30+ min on Lambda).

4. **Broken vendor parsers** (separate from this PR):
   - `TocrisVendor` — HTML restructure; needs new regex (see findings doc).
   - `MedChemExpressVendor` — 0/34 hits in the validation cycle.
   - `BrowserbaseFetchLookup` `chemcruz` parser — 0/117 hits; SCBT pages
     mostly 404 (de-listed SKUs?).
   - `BrowserbaseBrowserLookup` `enamine` parser — 3/177 hits; near-zero
     yield despite Enamine being the largest vendor in the index (5.2M
     rows). Worth investigating session-setup, parser regex, and SKU
     format.

5. **Missing parsers** for vendors present in the resolver index:
   - `Sigma-Aldrich` (256K rows) — no parser registered anywhere.
   - `Cayman Chemical` (DSN `843`, only 7 rows; effectively unusable).

---

## State at handoff

```
$ git log --oneline origin/pricing-integration..HEAD
859a0a3 feat(pricing): scripts/build_pricing_index_fast.py — SID-Map only + parallel
54704be feat(pricing): direct DSN -> backend dispatch in augment_prices
e01b93f docs(pricing): add Substance download script + empirical findings doc
b3cd783 fix(pricing): SID-Map is 4-column TSV not 2-column
d19567f fix(pricing): produce non-zero prices via PubChem 3-way JOIN
a09cb94 docs(pricing): scalability plan for 100K-compound runs
5161c40 fix(pricing): allowed_sources uses PubChem DSNs, not human names
7f23b80 feat(pricing): parallelize augment_prices via ThreadPoolExecutor
0a76dec fix(pricing): use is-not-None guard so allowed_sources=[] filters correctly
a2e7336 feat(pricing): plumb allowed_sources into PubChemSdfResolver.from_files
0260d1a fix(pricing): WAL + busy_timeout on CachedPriceLookup conns
41d5fba fix(pricing): per-thread SQLite conns in CachedPriceLookup
4af022e refine(pricing): tighten Task 2 — CWD-portable test, alphabetize vendors, strict assertions
366726b feat(pricing): default.yaml — curated allowed_sources + max_workers=100
dea4ec2 feat(pricing): add allowed_sources + max_workers to AichemyPricingConfig
```

`feat/pricing-scalability` is 15 commits ahead of `origin/pricing-integration`,
0 commits ahead of `origin/feat/pricing-scalability` (pushed clean).
