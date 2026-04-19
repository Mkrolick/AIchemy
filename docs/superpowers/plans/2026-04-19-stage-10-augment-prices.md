# Stage 10 — augment prices (federated lookup, ZINC-first)

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 10 COMPLETE`.
> **Design:** Federated multi-source `PriceLookup` with ZINC20 as the offline-safe primary baseline, PubChem as vendor-discovery, optional keyed vendor APIs, and opt-in scraping as last-resort. No single-vendor scraping baked into default config.

**Goal:** Populate `price_per_gram` on the deduped molecules table from a chained lookup of heterogeneous sources, with caching, rate limits, and ToS compliance built in from the start. Missing prices remain `None` (the MILP can still run).

**Status at foundation completion:** `StubPriceLookup` exists; no real implementation.

## Design rationale

A naive "scrape Sigma-Aldrich" approach fails on three counts: (1) most major chemical vendors' ToS prohibit automated access and enforce via CloudFlare + IP bans; (2) single-vendor coverage has gaps especially for enzymatic substrates; (3) scraped prices drift with no mechanism to refresh or detect staleness. The robust alternative is a layered federation where each layer is a `PriceLookup` implementation and the default stack never touches the public web.

### Four layers, tried in priority order

| Layer | Source | ToS status | Coverage | Freshness | Speed |
|---|---|---|---|---|---|
| 1. **ZINC20 bulk** | `zinc20.docking.org` purchasable subset (SDF download) | Explicitly free for research | Millions of purchasable compounds, wide | Updates ~annually | Instant after download |
| 2. **PubChem REST** | NCBI PubChem API | Public, free, no auth, rate-limited | Doesn't return prices directly — returns CID + vendor URLs | Real-time | ~5 req/s |
| 3. **Keyed vendor APIs** | ChemSpider (RSC), Mcule, Enamine REAL | Each vendor's free tier + API key | Drug-like / screening / specialty | Real-time | Per-vendor rate limit |
| 4. **Targeted scraping** | Opt-in allowlist of vendors | Per-vendor, per-ToS; OFF by default | Gap-fill only | Real-time | Heavily rate-limited |

### Why not start with scraping

- **Sigma-Aldrich, TCI, Acros, Alfa Aesar**: all explicitly prohibit automated access in their ToS and enforce via CloudFlare. Scraping risks: IP bans (easy), legal notice (rare but real), and an unpleasant maintenance burden as they change page structure.
- **ZINC is literally built to be the free answer to "give me a SMILES → price table"** — it aggregates vendor-reported prices *with vendor permission*. Use it first.
- **PubChem's vendor cross-links** get us the vendor URL without scraping the vendor — useful metadata even when we can't get a price.

Scraping is left in the design for a future opt-in path but should not be the default.

## Architecture

```
aichemy.preprocessing.augment.prices/
├── __init__.py              # public exports + make_lookup factory
├── protocol.py              # PriceLookup protocol, StubPriceLookup (existing)
├── cache.py                 # CachedPriceLookup (SQLite), ChainedPriceLookup
├── zinc.py                  # ZINCPriceLookup — parses ZINC SDF → lookup
├── pubchem.py               # PubChemVendorDiscovery — returns vendor URLs (not prices)
├── chemspider.py            # ChemSpiderPriceLookup — keyed API
├── mcule.py                 # MculePriceLookup — keyed API
└── scraping/
    ├── __init__.py
    ├── base.py              # rate-limit + robots.txt + backoff boilerplate
    └── sigma_aldrich.py     # opt-in; NOT wired into default chain
```

`make_lookup(config) -> PriceLookup` builds the chain per config:

```python
def make_lookup(config: PreprocessingConfig) -> PriceLookup:
    if config.prices.backend == "stub":
        return StubPriceLookup()

    inner_lookups = []
    for name in config.prices.chain:
        if name == "zinc":
            inner_lookups.append(ZINCPriceLookup(config.prices.zinc.data_path))
        elif name == "pubchem":
            # Doesn't return prices; populates vendor_urls sidecar
            continue
        elif name == "chemspider" and config.prices.chemspider.api_key:
            inner_lookups.append(ChemSpiderPriceLookup(api_key=...))
        elif name == "mcule" and config.prices.mcule.api_key:
            inner_lookups.append(MculePriceLookup(api_key=...))
        elif name == "scraper" and config.prices.scraper.enabled:
            inner_lookups.append(make_scraper_stack(config.prices.scraper))

    return CachedPriceLookup(
        ChainedPriceLookup(inner_lookups),
        cache_path=config.prices.cache_path,
        ttl_days=config.prices.cache_ttl_days,
    )
```

## Config additions (`configs/default.yaml`)

```yaml
prices:
  backend: chained             # stub | chained
  chain: [zinc]                # default: ZINC only, fully offline, deterministic
  cache_path: data/interim/prices_cache.sqlite
  cache_ttl_days: 30

  zinc:
    data_path: data/raw/zinc/zinc20_purchasable.parquet   # populated by fetch-raw once
    # Fetched from a ZINC bulk download and pre-parsed; see Open Item 11 for the fetch plan

  chemspider:
    api_key: null              # set in .env-backed override or profile; null disables
  mcule:
    api_key: null

  scraper:
    enabled: false             # MUST be explicitly true to enable any web scraping
    vendors: []                # allowlist; e.g. ["mcule_public_page"]
    rate_limit_seconds: 5.0
    user_agent: "AIchemy-research/0.1 (malcolm.krolick@gmail.com)"
    cache_path: data/interim/scraper_prices.sqlite
    respect_robots_txt: true
```

`configs/profiles/prices_with_keys.yaml` (gitignored if it holds secrets, or reference env vars) can override api_keys. A separate `configs/profiles/prices_with_scraping.yaml` explicitly flips scraping on — a user must point `--override` at it.

## Tasks

### T1: Restructure config model for layered prices

- [ ] Extend `PricesConfig` with nested `zinc`, `chemspider`, `mcule`, `scraper` sub-configs
- [ ] Change `backend: Literal["chemprize", "stub"]` → `Literal["stub", "chained"]`
- [ ] Add `chain: list[str]` validator ensuring values are known lookup names
- [ ] Unit tests covering defaults (`chain = ["zinc"]`, `backend = "chained"`, `scraper.enabled = False`)
- [ ] Commit

### T2: `CachedPriceLookup` + `ChainedPriceLookup`

- [ ] Failing test: `ChainedPriceLookup([A, B])` where A returns None and B returns 1.23 returns 1.23; A is called first; once A returns None, B is tried
- [ ] Failing test: `CachedPriceLookup` wraps an inner lookup, first call hits inner, second call hits cache (inner not called again)
- [ ] Failing test: cache TTL expiry re-queries inner
- [ ] Implement with SQLite (stdlib `sqlite3`) — `prices(canonical_smiles PRIMARY KEY, price_per_gram REAL NULL, fetched_at TIMESTAMP)`; cache misses (None) are cached too so we don't re-query
- [ ] Commit

### T3: `ZINCPriceLookup` — offline, primary

- [ ] Failing test: with a tiny ZINC parquet fixture (3 rows: SMILES + price_per_gram), lookup returns known prices and None for unknown SMILES
- [ ] Implement: on init, load parquet into an in-memory dict keyed by canonical SMILES (or lazy scan)
- [ ] Test: memoryfootprint acceptable for full ZINC (~15M compounds at ~50B each = ~750MB; consider DuckDB / polars lazy scan for prod)
- [ ] Commit

### T4: `PubChemVendorDiscovery` — returns vendor URLs, not prices

- [ ] This is *not* a `PriceLookup`; introduce a sibling `VendorDiscovery` protocol with `find_vendors(smiles: str) -> list[dict]`
- [ ] Use PubChem REST API (`pubchem.ncbi.nlm.nih.gov/rest/pug`) with `httpx` + rate limiter (5 req/s)
- [ ] Failing test via `pytest-httpx` replay: ethanol SMILES → CID 702 → vendor cross-links list
- [ ] Integrate into `augment_prices` as a sidecar that populates a `vendor_urls: list[str]` column on the molecules table (even when price_per_gram is None)
- [ ] Commit

### T5: Keyed vendor lookups (skeleton, disabled-by-default)

- [ ] `ChemSpiderPriceLookup(api_key)` — stub implementation with a `lookup` that returns None when `api_key is None`. Real HTTP calls gated on API key presence
- [ ] Same for `MculePriceLookup(api_key)`
- [ ] Failing tests: without api_key, always returns None (no HTTP made)
- [ ] With `pytest-httpx` replay mocking one real response each, verify parsing
- [ ] Commit

### T6: Scraping stack — opt-in, behind `scraper.enabled`

- [ ] `aichemy.preprocessing.augment.prices.scraping.base.ScraperBase` — applies rate limit, robots.txt check, User-Agent, exponential backoff on 429/503
- [ ] `SigmaAldrichScraper(ScraperBase)` — disabled unless `scraper.enabled=True` AND vendor in `scraper.vendors` allowlist. Raises at construction time if ToS guard fails. Cache all hits.
- [ ] Failing tests: when `enabled=False`, calling `.lookup()` returns None with no HTTP; when enabled, record/replay via `pytest-httpx` verifies parsing
- [ ] Manual enablement is a conscious act — log a prominent banner on construction
- [ ] Commit

### T7: `make_lookup(config)` factory

- [ ] Failing test: `backend=stub` returns StubPriceLookup
- [ ] Failing test: `backend=chained, chain=["zinc"]` returns `CachedPriceLookup(ChainedPriceLookup([ZINCPriceLookup]))`
- [ ] Failing test: `chain=["zinc", "scraper"]` with `scraper.enabled=False` filters scraper out (no scraper in the chain)
- [ ] Implement the factory
- [ ] Commit

### T8: `augment_prices` orchestrator

- [ ] Failing integration test: molecules df with 3 SMILES, StubPriceLookup pre-populated for 2 → output has 2 priced + 1 with null price_per_gram
- [ ] Implement: for each row, call `lookup.lookup(canonical_smiles)`, write to new column
- [ ] Add `vendor_urls` column populated via PubChemVendorDiscovery where available
- [ ] Commit

### T9: Wire CLI

- [ ] Replace `augment_prices` stub in `cli.py` to call `make_lookup(config)` + orchestrator
- [ ] Integration test with `backend=stub` + populated stub
- [ ] Commit

### T10: ZINC fetch path (depends on Open Item 04)

- [ ] Plan only — do not implement here. Document the ZINC download flow (bulk SDF from `zinc20.docking.org`, parse once into `data/raw/zinc/zinc20_purchasable.parquet`, subsequent runs just read the parquet). Ship in Stage 01 (fetch-raw) when URLs pin.
- [ ] Commit (documentation only)

### T11: End-to-end verification

- [ ] `uv run dvc repro augment_prices` — uses stub by default, runs clean
- [ ] `uv run pytest` — all green, including pytest-httpx replays for API/scraper layers
- [ ] Update README to document the multi-source strategy + how to enable scraping
- [ ] Commit + push

## Going-live checklist (for the user when the time comes)

1. ZINC bulk download via Stage 01 (fetch-raw) once URLs are pinned in Open Item 04.
2. `configs/profiles/prices_zinc.yaml` with `chain: [zinc, pubchem]` for online vendor-URL enrichment.
3. Decide whether to pursue ChemSpider / Mcule API keys; if yes, obtain keys, add to `.env.local` or similar; `configs/profiles/prices_all_apis.yaml` enables the full chain minus scraping.
4. If vendor scraping becomes necessary, do a ToS review per vendor, then `configs/profiles/prices_with_scraping.yaml` enables `scraper.enabled=True` with an explicit vendor allowlist.
