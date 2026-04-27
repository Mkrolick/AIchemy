# PubChem Resolver — Empirical Findings (2026-04-26 / 27)

This document captures findings from the validation cycle that produced
the `feat/pricing-scalability` branch. Most of these are upstream PubChem
data-format / behavior facts that are **not documented** in PubChem's own
README files but were discovered by direct inspection. Future
contributors and downstream maintainers should consult this doc before
trusting PubChem's published format claims.

---

## TL;DR

1. **PubChem Substance vendor records do NOT contain `PUBCHEM_IUPAC_INCHIKEY`.**
   The InChIKey lives on the linked Compound record (CID), not the
   Substance record (SID). The original `PubChemSdfResolver` required
   the field on Substance and so produced an empty index for every
   vendor-deposited record. (CLAIM-04 in
   `experiments/chem-pricing-verification/CLAIMS.md` was tagged PARTIAL
   for exactly this reason but the implementation shipped anyway.) Fixed
   by `PubChemCompoundResolver` (3-way JOIN: Substance → SID-Map →
   Compound).

2. **PubChem `SID-Map.gz` is a 4-column TSV, not the 2-column TSV the
   FTP README documents.** Real format:
   `SID<TAB>SourceName<TAB>SourceRegID<TAB>CID`. CID column is *omitted
   entirely* (no trailing tab) when the SID has no standardized Compound
   association. Fixed in commit `b3cd783`. The 4-column format is
   significant beyond the bug fix: the source-name + reg-ID columns are
   identical to what Substance SDFs carry, which means a future resolver
   can skip the 90-min Substance scan entirely (see "Optimization
   opportunities" below).

3. **PubChem uses three different vendor-naming conventions across
   three different files.** `Source-Names` (the registry) is `DSN<TAB>
   DisplayName<TAB>Date`. Substance SDFs store the **DSN** (column 1) in
   `PUBCHEM_EXT_DATASOURCE_NAME` — usually a numeric source ID like
   `'959'` (MedChemExpress), but a few legacy depositors use a string
   DSN like `'Sigma-Aldrich'`. SID-Map stores the **display name**
   (column 2) — `'Molecular Imaging Database (MOLI)'`,
   `'MedChemexpress MCE'`, etc. Any resolver that filters on vendors
   must match the right column for its data source.

4. **Vendor records cluster across SID ranges; uniform sampling misses
   them.** The 6 curated vendors in our allowlist together have ~5.85M
   live substances out of ~527M total SIDs (~1.1%). A 5-shard sample
   (each shard = 500K SIDs) has roughly a 5% chance of finding any
   given vendor in any given shard. To verify "is vendor X present in
   the corpus" you need at least 30+ spread shards or a targeted scan.

5. **Disk: full PubChem Compound is ~300 GB, not the ~30 GB our master
   plan estimated.** Confirmed by extrapolating from 110 GB at 357 of
   982 shards.

6. **Concurrent FTP downloads: -P 12 fails ~30% of shards** (server
   serves HTML error pages instead of gzip). -P 4 has been empirically
   reliable. The download scripts in `scripts/download_pubchem_*.sh`
   default to -P 4.

---

## Architectural finding: the original resolver was unfixable as designed

`PubChemSdfResolver` (still in the package, kept for backward compat)
walks Substance SDFs and indexes records that have all three of:
`PUBCHEM_IUPAC_INCHIKEY`, `PUBCHEM_EXT_DATASOURCE_NAME`,
`PUBCHEM_EXT_DATASOURCE_REGID`. This works for **PubChem-curated**
sources (DTP/NCI, NIAID, KEGG, MMDB) which DO include InChIKey on the
Substance side. But it never works for **vendor-deposited** records,
which carry only the structure (molfile inline) and the vendor
metadata. PubChem's standardization pipeline computes the InChIKey
later and stores it on the Compound (CID) side.

Concrete example — a real MedChemExpress record:
```
PUBCHEM_EXT_DATASOURCE_NAME    = 959
PUBCHEM_EXT_DATASOURCE_REGID   = HY-100005A
PUBCHEM_EXT_DATASOURCE_URL     = https://www.medchemexpress.com/
PUBCHEM_EXT_SUBSTANCE_URL      = https://www.medchemexpress.com/...html
PUBCHEM_SUBSTANCE_ID           = 317226072
PUBCHEM_CID_ASSOCIATIONS       = 121596089  1
PUBCHEM_SUBSTANCE_SYNONYM      = Fumarate hydratase-IN-2 (sodium salt)
+ molfile structure (atoms/bonds inline)
```
No InChIKey field. CID 121596089 is on the Compound side; that record
DOES have `PUBCHEM_IUPAC_INCHIKEY`.

**Fix:** `PubChemCompoundResolver` does the 3-way JOIN:
- Pass 1: Substance SDFs → `SID → (vendor, SKU, URL)` filtered by
  `allowed_sources`.
- Pass 2: `SID-Map.gz` → drop SIDs without CIDs, produce
  `CID → [(vendor, SKU, URL), ...]`.
- Pass 3: Compound SDFs → look up CID, read InChIKey, emit
  `ResolverHit`.

Persists final index to parquet
(`data/interim/aichemy_pricing_index.parquet`) so re-runs deserialize
in ~5 sec instead of rebuilding for ~3 hr.

---

## Vendor → DSN mapping (verified against `Source-Names`)

| Vendor | DSN (in `PUBCHEM_EXT_DATASOURCE_NAME`) | Live substances |
|---|---|---:|
| Enamine | `"822"` | 5,199,173 |
| Sigma-Aldrich | `"Sigma-Aldrich"` (string DSN — legacy) | 258,063 |
| Santa Cruz Biotechnology, Inc. | `"25659"` | 174,341 |
| MedChemexpress MCE | `"959"` | 116,897 |
| Fluorochem | `"29665"` | 96,024 |
| Tocris Bioscience | `"10600"` | 5,166 |
| Cayman Chemical | `"843"` | 7 (effectively unindexed) |
| **Total ours** | | **~5.85M** |

**Vendors absent from PubChem entirely** (Substance SDFs do not contain
their products under any DSN): **Molbase**. They appear to have no
PubChem deposit pipeline. To resolve InChIKey → Molbase SKU we would
need an alternate source (their own catalog dump or the Chinese-vendor
aggregators that do mirror them).

The full source registry is at
https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/Extras/Source-Names
(~1431 sources total, ~531 vendor-tagged). Format is
`DSN<TAB>DisplayName<TAB>Date`.

---

## Performance numbers (single-threaded, M-series Mac)

Measured on `Apple Silicon` workstation, single-threaded SDF parsing.

| Phase | Throughput | Wall-clock for full corpus |
|---|---:|---:|
| Substance scan (982 shards, ~491M records) | ~11 shards/min → ~75K records/sec | ~90 min |
| SID-Map walk (3.3 GB compressed, ~527M lines) | ~1M lines/sec | ~10 min |
| Compound scan (982 shards, ~120M CIDs) | ~5 shards/min → ~40K records/sec | ~75 min total (we observed ~50 min for 357 partial shards = ~1.4 min/shard) |
| Parquet persist (~6M rows) | ~1M rows/sec | <30 sec |
| **Total resolver build** | | **~3 hr** (single-threaded) |

The augment dispatch step itself is fast: with `max_workers=100` and
~99% L1 cache hit on subsequent runs, 100K compounds take ~30-60 min
on the first pass (dominated by L3 Browserbase calls when L2 misses)
and **~5-10 min** on cached re-runs.

Memory peak during pass 1: **~1.2 GB RSS** with the 6-vendor
allowlist holding ~6M records. Without `allowed_sources` filter,
extrapolation says ~75-100 GB RSS — well into OOM territory on
typical workstations, fine on a 450-GB-RAM Lambda node.

---

## Optimization opportunities (not in this PR)

### 1. Skip the Substance scan entirely (Task 8a, ~50 LOC)

The 4-column SID-Map format (Finding #2) means the Substance scan can
be eliminated. SID-Map has the `(SID, source_name, source_reg_id,
CID)` tuple inline. A single SID-Map walk produces everything pass 1
+ pass 2 produced in the current 3-pass design.

**Caveat:** SID-Map column 2 is the **display name** (column 2 of
`Source-Names`), not the DSN (column 1) that Substance SDFs use. So a
SID-Map-only resolver needs `allowed_sources` to be display names, not
DSNs. Either translate at config load time, or accept both formats.

**Caveat 2:** SID-Map does not have `PUBCHEM_EXT_DATASOURCE_URL` or
`PUBCHEM_EXT_SUBSTANCE_URL` — only the source registration ID. If the
canonical product URL matters (it's stored in `ResolverHit.canonical_url`
and surfaced through to `PriceQuote.source_url`), the Substance scan is
still needed for URL enrichment.

**Wall-clock improvement:** drops 3 hr → ~10 min for the resolver
build. The single biggest win available without parallelization.

### 2. Parallelize pass 1 + pass 3 across cores (Task 8b, ~30 LOC)

Both passes are embarrassingly parallel — each shard parses
independently and contributes to a final dict. Use
`concurrent.futures.ProcessPoolExecutor` to fan out across cores.
Worker workers return `dict[InChIKey, list[ResolverHit]]` chunks; the
main process merges them.

**Wall-clock improvement:** with 52 cores (Lambda config), each pass
drops to ~2 min single-shard wall-clock. Combined with #1: ~5 min
total resolver build. Combined without #1: ~30 min total.

### 3. Targeted Compound download (Task 8c, ~20 LOC)

After pass 2 (CID set known), only download Compound shards whose
filename CID range overlaps the needed CIDs. PubChem Compound shard
naming is `Compound_NNNNNNNNN_NNNNNNNNN.sdf.gz` with explicit CID
ranges. For a 6-vendor allowlist, expected to cut Compound from
~300 GB → ~50 GB.

Useful only if disk is tight (not relevant on Lambda's 5.5 TB SSD).

---

## Operational gotchas

### 1. Concurrent FTP downloads must use `-P 4`, not higher

PubChem's FTP server starts serving HTML error pages instead of gzip
data when overwhelmed. We hit ~30% corrupt rate at `-P 12`; `-P 4`
has been clean. The `scripts/download_pubchem_*.sh` scripts default
to `-P 4` for this reason. After download, always `gzip -t *.sdf.gz`
to verify integrity before any pipeline run depends on the data.

### 2. macOS reports compressed memory as low RSS

During pass 2 of the resolver, RSS dropped from 1.19 GB → 7 MB while
the in-memory dicts were still alive. macOS aggressively compresses
idle pages and reports only uncompressed RSS in `ps`. The pages get
decompressed on next access. Don't interpret a low-RSS read as
"the dict was freed" without verifying with `vm_stat` or process
memory introspection.

### 3. Tocris HTML restructure (separate from the resolver issue)

`TocrisVendor` (`src/aichemy_pricing/vendors/tocris.py`) regex no
longer matches the current Tocris product pages. The page returns
200 OK with prices clearly visible, but the `Pack Size` / `List Price`
/ `product-pricing` markers the regex looks for have been replaced.
Not a regression we introduced — content drift on Tocris's side. The
parser needs a new regex against the current layout. Open follow-up.

### 4. `BROWSERBASE_API_KEY` env var

L3 Browserbase tests + production runs are silently no-ops without
the env var. `BrowserbaseClient.is_configured()` returns False and
`fetch_markdown()` returns None. **For 100K production runs the key
must be present** or you'll get the L3 fallback skipped and many
compounds will end up with no price.

### 5. Sampling pitfalls when probing PubChem distribution

Vendors cluster within specific SID ranges (Enamine bulk uploads
in particular concentrate in contiguous high-SID blocks). A 5- or
10-shard sample drawn from the corpus has only a few percent chance
of hitting any given vendor. Whenever asking "is vendor X in this
data?", sample at least 30 spread shards before concluding "no".

---

## What this PR DID prove (despite the 0% coverage final run)

- The scalability infrastructure is correct: per-thread SQLite, WAL
  pragmas, ThreadPoolExecutor dispatch, `allowed_sources` filter all
  work as designed against unit-test fixtures.
- The 3-way JOIN architecture is correct: with the corrected SID-Map
  parser (commit `b3cd783`), the `PubChemCompoundResolver` produces
  the expected `InChIKey → ResolverHit` mapping on synthetic
  fixtures (12/12 tests pass).
- The pipeline runs end-to-end without errors at the scale of 982
  Substance shards + 357 Compound shards on a 450-row dataset.
- Pass 1 RSS spike to 1.19 GB (RSS, ignoring compressed pages) at
  ~97% confirms the Substance scan IS finding vendor records — the
  earlier 0-match result was the SID-Map parser bug, not a genuine
  data gap.

## What this PR did NOT prove

- Real-data coverage on actual USPTO/MetaNetX molecules — the bug
  fix landed after the 3 hr validation run completed with 0%. A
  fresh re-run with the corrected parser is the next step.
- The exact fraction of the 6-vendor allowlist that overlaps with
  USPTO+MetaNetX chemistry. Likely high for common reagents
  (Sigma-Aldrich, MCE), lower for synthetic intermediates that may
  not be in any commercial vendor catalog.

---

## How to validate going forward

1. Pull the data (~60 min in parallel):
   ```bash
   bash scripts/download_pubchem_substance.sh   # ~54 GB
   bash scripts/download_pubchem_compound.sh    # ~300 GB
   bash scripts/download_pubchem_sid_map.sh     # ~3 GB
   ```
2. Set the API key: `export BROWSERBASE_API_KEY=...`
3. Build the data subset (one-time, ~5 min):
   `bash scripts/build_subset.sh`
4. Run end-to-end:
   ```bash
   cat > /tmp/_validate_overrides.yaml <<'EOF'
   paths:
     data_dir: data_subset
   EOF
   uv run aichemy augment prices \
     --config configs/default.yaml \
     --override /tmp/_validate_overrides.yaml
   ```
5. Read coverage stats:
   ```bash
   uv run python -c "
   import polars as pl
   df = pl.read_parquet('data_subset/interim/augmented/molecules_priced.parquet')
   priced = df.filter(pl.col('price_per_gram').is_not_null())
   print(f'priced: {priced.height} of {df.height} ({100*priced.height/df.height:.1f}%)')
   print(priced.head(20))
   "
   ```

Expected wall-clock on a 52-vCPU Lambda node:
- First run with the current (single-threaded) resolver: ~3 hr
- After Task 8a (SID-Map-only): ~30 min
- After Task 8a + Task 8b (parallel): ~5–10 min
- Subsequent runs (parquet cache hit): ~5–10 min
