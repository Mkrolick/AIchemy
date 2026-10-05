# `augment-prices` scalability — `allowed_sources` + parallel dispatch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `augment_prices` DVC stage feasible at 100K-reaction scale by (a) bounding `PubChemSdfResolver` memory via an `allowed_sources` filter, and (b) parallelizing `augment_prices()`'s SMILES-dispatch loop with a bounded thread pool.

**Architecture:** Two thin, additive changes plus one bug fix:
1. Thread a new `allowed_sources: list[str] | None` config field through `AichemyPricingConfig` → `make_lookup()` → `PubChemSdfResolver.from_files(..., allowed_sources=...)`. The resolver already accepts the kwarg; we just plumb it through.
2. Add `max_workers: int = 1` to `AichemyPricingConfig`. Rewrite `augment_prices()`'s dict-comprehension as a `concurrent.futures.ThreadPoolExecutor` map. `max_workers=1` matches today's serial behavior (back-compat).
3. Make `aichemy_pricing.chain.CachedPriceLookup` thread-safe — today it shares one `sqlite3.Connection` across calls, which raises `ProgrammingError` from non-init threads (Python's `sqlite3` defaults `check_same_thread=True`). Switch to one connection per thread via `threading.local()`. `TokenBucket` is already thread-safe; `LookupByInchikey`/`_InchikeyAdapter`/`ChainedPriceLookup` hold no shared mutable state and are fine.

**Why this scope:** The resolver docstring already says *"production runs MUST set `allowed_sources` to keep memory bounded"* (`pubchem_sdf.py:11`); the master plan's "30–40 min at 100 concurrent" wall-clock target is unreachable with today's serial dict-comp at `prices.py:457`. Together these two changes are the minimum diff to make 100K runs viable.

**Tech Stack:** Python 3.11+, `concurrent.futures.ThreadPoolExecutor`, `threading.local`, `sqlite3` per-thread connections, `pydantic` v2 (config), existing `aichemy_pricing` chain primitives (no new deps).

---

## File map

| File | Change |
|---|---|
| `src/aichemy/config.py` (`AichemyPricingConfig` @ line 110) | Add fields `allowed_sources: list[str] \| None = None` and `max_workers: int = 1` |
| `configs/default.yaml` (`prices.aichemy_pricing` @ lines 34-36) | Add `allowed_sources` (curated vendor list) + `max_workers: 100` |
| `src/aichemy_pricing/chain.py` (`CachedPriceLookup` @ line 61) | Replace shared `self._conn` with `threading.local()`-backed per-thread connections |
| `src/aichemy/preprocessing/augment/prices.py` (`make_lookup` @ line 385) | Pass `allowed_sources=cfg.aichemy_pricing.allowed_sources` to `PubChemSdfResolver.from_files()` |
| `src/aichemy/preprocessing/augment/prices.py` (`augment_prices` @ lines 443-464) | Replace dict-comp with `ThreadPoolExecutor.map`; accept `max_workers` argument |
| `src/aichemy/preprocessing/augment/__main__.py` (or wherever the CLI calls `augment_prices`) | Pass `cfg.prices.aichemy_pricing.max_workers` into the `augment_prices` call |
| `tests/unit/test_config.py` | Test new config fields default + custom values |
| `tests/unit/test_prices.py` | Test `make_lookup` plumbs `allowed_sources`; test `augment_prices` parallel dispatch correctness |
| `src/aichemy_pricing/tests/test_cache.py` | Test `CachedPriceLookup` thread safety under N-thread concurrent access |

---

## Task 1: Add `allowed_sources` and `max_workers` to `AichemyPricingConfig`

**Files:**
- Modify: `src/aichemy/config.py:110-122` (extend `AichemyPricingConfig`)
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_config.py`:

```python
def test_aichemy_pricing_config_allowed_sources_default_is_none() -> None:
    from aichemy.config import AichemyPricingConfig

    cfg = AichemyPricingConfig()
    assert cfg.allowed_sources is None
    assert cfg.max_workers == 1


def test_aichemy_pricing_config_accepts_allowed_sources_list_and_max_workers() -> None:
    from aichemy.config import AichemyPricingConfig

    cfg = AichemyPricingConfig.model_validate(
        {
            "allowed_sources": ["Fluorochem", "Enamine"],
            "max_workers": 100,
        }
    )
    assert cfg.allowed_sources == ["Fluorochem", "Enamine"]
    assert cfg.max_workers == 100


def test_aichemy_pricing_config_rejects_max_workers_below_one() -> None:
    import pytest
    from pydantic import ValidationError

    from aichemy.config import AichemyPricingConfig

    with pytest.raises(ValidationError):
        AichemyPricingConfig.model_validate({"max_workers": 0})
```

- [ ] **Step 2: Run test to verify it fails**

```
cd ~/.config/superpowers/worktrees/AIchemy-fresh/pricing-scale && uv run pytest tests/unit/test_config.py -k "aichemy_pricing_config" -v
```

Expected: all 3 FAIL. Specific failure modes vary — the first raises `AttributeError` on `cfg.allowed_sources`, the second raises `pydantic.ValidationError` because `extra="forbid"` rejects the unknown keys, and the third fails because `pydantic` doesn't raise (the field doesn't exist with the `ge=1` constraint yet).

- [ ] **Step 3: Implement**

Edit `src/aichemy/config.py:110-122` `AichemyPricingConfig`:

```python
class AichemyPricingConfig(BaseModel):
    """Backend-specific config for the standalone `aichemy_pricing` package.

    Path fields point at the offline catalog (PubChem SDF dir + a SQLite cache
    location). `allowed_sources` filters the in-memory InChIKey index to a
    vendor allowlist — REQUIRED for full-scale runs (491M SIDs OOM otherwise;
    see `aichemy_pricing.resolvers.pubchem_sdf` docstring). `max_workers`
    controls the `augment_prices` thread pool size (1 = today's serial
    behavior; 100 ~ master-plan target wall-clock for 100K compounds).
    """

    model_config = {"extra": "forbid"}

    catalog_dir: Path = Field(default_factory=lambda: Path("data/raw/pubchem_substance"))
    cache_path: Path = Field(
        default_factory=lambda: Path("data/interim/aichemy_pricing_cache.sqlite")
    )
    allowed_sources: list[str] | None = None
    max_workers: int = Field(default=1, ge=1)
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_config.py -k "aichemy_pricing_config" -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/config.py tests/unit/test_config.py
git commit -m "feat(pricing): add allowed_sources + max_workers to AichemyPricingConfig"
```

---

## Task 2: Update `configs/default.yaml` to set `allowed_sources` + `max_workers`

**Files:**
- Modify: `configs/default.yaml:34-36`
- Test: `tests/unit/test_config.py` (load+roundtrip)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_config.py`:

```python
def test_default_yaml_aichemy_pricing_block_has_curated_allowed_sources_and_workers(tmp_path) -> None:
    from pathlib import Path

    import yaml
    from aichemy.config import PreprocessingConfig

    raw = yaml.safe_load(Path("configs/default.yaml").read_text())
    cfg = PreprocessingConfig.model_validate(raw)
    aip = cfg.prices.aichemy_pricing
    # Curated vendor allowlist matches the L2/L3-priceable vendors we ship
    # parsers/clients for. Avoids loading 491M PubChem records into RAM.
    assert aip.allowed_sources is not None
    assert "Fluorochem" in aip.allowed_sources
    assert "Enamine" in aip.allowed_sources
    assert aip.max_workers >= 1
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/unit/test_config.py::test_default_yaml_aichemy_pricing_block_has_curated_allowed_sources_and_workers -v
```

Expected: FAIL — `aip.allowed_sources is None`.

- [ ] **Step 3: Implement**

Edit `configs/default.yaml` `prices.aichemy_pricing` block to:

```yaml
  aichemy_pricing:
    catalog_dir: data/raw/pubchem_substance
    cache_path: data/interim/aichemy_pricing_cache.sqlite
    # Vendor allowlist for the PubChem SDF resolver. PubChem Substance has 914
    # source tags; loading them all OOMs at full-corpus scale (491M SIDs). This
    # restricts the in-memory InChIKey index to vendors we actually price via
    # the L2/L3 chain. Names match `PUBCHEM_EXT_DATASOURCE_NAME` exactly.
    allowed_sources:
      - Fluorochem
      - MedChemExpress
      - Tocris Bioscience
      - Molbase
      - Enamine
      - Santa Cruz Biotechnology, Inc.
    max_workers: 100
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_config.py::test_default_yaml_aichemy_pricing_block_has_curated_allowed_sources_and_workers -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add configs/default.yaml tests/unit/test_config.py
git commit -m "feat(pricing): default.yaml — curated allowed_sources + max_workers=100"
```

---

## Task 3: Make `aichemy_pricing.chain.CachedPriceLookup` thread-safe

**Files:**
- Modify: `src/aichemy_pricing/chain.py:61-98` (`CachedPriceLookup`)
- Test: `src/aichemy_pricing/tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

Append to `src/aichemy_pricing/tests/test_cache.py`:

```python
def test_cached_lookup_is_thread_safe(tmp_path) -> None:
    """Many threads hitting the same CachedPriceLookup must not raise
    sqlite3.ProgrammingError ('SQLite objects created in a thread can only be
    used in that same thread.'). Regression guard for production
    parallelization in augment_prices."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from aichemy_pricing.chain import CachedPriceLookup
    from aichemy_pricing.types import PriceQuote, VendorRef

    class _StubInner:
        name = "stub"

        def lookup(self, ref: VendorRef) -> PriceQuote | None:
            return PriceQuote(
                vendor=ref.vendor,
                sku=ref.sku,
                price=1.0,
                currency="USD",
                pack_size_g=1.0,
                source_url="https://example/",
            )

    cache = CachedPriceLookup(_StubInner(), db_path=tmp_path / "c.sqlite", ttl_days=30)

    refs = [VendorRef(vendor="enamine", sku=f"EN-{i}") for i in range(100)]
    errors: list[BaseException] = []
    barrier = threading.Barrier(20)

    def _run(ref: VendorRef) -> None:
        try:
            barrier.wait()
            assert cache.lookup(ref) is not None
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(_run, refs))

    assert errors == [], f"thread-safety violations: {errors[:3]}"
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest src/aichemy_pricing/tests/test_cache.py::test_cached_lookup_is_thread_safe -v
```

Expected: FAIL with one of:
- `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread.`
- A torn read/write race producing wrong results.

- [ ] **Step 3: Implement**

Replace `CachedPriceLookup` in `src/aichemy_pricing/chain.py:61-98` with:

```python
class CachedPriceLookup:
    """Wraps an inner PriceLookup with a SQLite cache.

    Caches BOTH hits and misses (None), so a known-missing SKU isn't re-fetched.
    Entries older than `ttl_days` are treated as cache misses and re-fetched.

    Thread-safe: each calling thread gets its own `sqlite3.Connection` via
    `threading.local`. SQLite handles concurrent writers via its file-level
    lock; conflicts retry transparently because we use `isolation_level=None`
    (autocommit). Required for the parallel `augment_prices` dispatcher.
    """

    name = "cache"

    def __init__(self, inner: PriceLookup, db_path: Path | str, ttl_days: int = 30) -> None:
        self.inner = inner
        self.db_path = Path(db_path)
        self.ttl = timedelta(days=ttl_days)
        self._tls = threading.local()
        # Initialize schema once on the constructing thread; per-thread
        # connections opened lazily in `_conn()`.
        bootstrap = sqlite3.connect(str(self.db_path), isolation_level=None)
        try:
            bootstrap.executescript(_SCHEMA)
        finally:
            bootstrap.close()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), isolation_level=None)
            self._tls.conn = conn
        return conn

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT quote_json, fetched_at FROM quote_cache WHERE vendor=? AND sku=?",
            (ref.vendor, ref.sku),
        ).fetchone()
        if row is not None:
            quote_json, fetched_at_iso = row
            fetched = datetime.fromisoformat(fetched_at_iso)
            if datetime.now(UTC) - fetched < self.ttl:
                return None if quote_json is None else PriceQuote.model_validate_json(quote_json)
        result = self.inner.lookup(ref)
        conn.execute(
            "INSERT OR REPLACE INTO quote_cache(vendor, sku, quote_json, fetched_at) "
            "VALUES (?, ?, ?, ?)",
            (
                ref.vendor,
                ref.sku,
                result.model_dump_json() if result else None,
                datetime.now(UTC).isoformat(),
            ),
        )
        return result
```

Add the `import threading` to the top of `src/aichemy_pricing/chain.py` (next to `import sqlite3`).

- [ ] **Step 4: Run test to verify it passes (and existing tests still pass)**

```
uv run pytest src/aichemy_pricing/tests/test_cache.py -v
```

Expected: all PASS, including the existing offline cache tests and the new thread-safety test.

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/chain.py src/aichemy_pricing/tests/test_cache.py
git commit -m "fix(pricing): per-thread SQLite conns in CachedPriceLookup"
```

---

## Task 4: Thread `allowed_sources` through `make_lookup`

**Files:**
- Modify: `src/aichemy/preprocessing/augment/prices.py:368-387` (`make_lookup` `aichemy_pricing` branch)
- Test: `tests/unit/test_prices.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_prices.py`:

```python
def test_make_lookup_aichemy_pricing_passes_allowed_sources(monkeypatch, tmp_path) -> None:
    """make_lookup must thread cfg.aichemy_pricing.allowed_sources into
    PubChemSdfResolver.from_files(). Without this, full-corpus PubChem loads
    OOM regardless of the config setting."""
    from aichemy.config import (
        AichemyPricingConfig,
        PreprocessingConfig,
        PricesConfig,
    )
    from aichemy.preprocessing.augment import prices as prices_mod

    # Stage one fake SDF so the empty-catalog fallback doesn't short-circuit.
    sdf_dir = tmp_path / "pubchem"
    sdf_dir.mkdir()
    (sdf_dir / "stub.sdf").write_text("$$$$\n")  # empty record terminator only
    cache_path = tmp_path / "c.sqlite"

    captured: dict[str, object] = {}

    def fake_from_files(paths, allowed_sources=None):  # noqa: ANN001 — test stub
        captured["paths"] = list(paths)
        captured["allowed_sources"] = allowed_sources
        # return a resolver that resolves nothing
        from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver

        return PubChemSdfResolver()

    monkeypatch.setattr(
        "aichemy_pricing.resolvers.pubchem_sdf.PubChemSdfResolver.from_files",
        fake_from_files,
    )

    cfg = PreprocessingConfig(
        prices=PricesConfig(
            backend="aichemy_pricing",
            aichemy_pricing=AichemyPricingConfig(
                catalog_dir=sdf_dir,
                cache_path=cache_path,
                allowed_sources=["Fluorochem", "Enamine"],
                max_workers=4,
            ),
        ),
    )

    prices_mod.make_lookup(cfg)
    # Resolver's `from_files(allowed_sources=...)` signature takes `set[str] | None`,
    # so production code converts the YAML list. Compare as sets to be permissive.
    assert captured["allowed_sources"] == {"Fluorochem", "Enamine"}
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/unit/test_prices.py::test_make_lookup_aichemy_pricing_passes_allowed_sources -v
```

Expected: FAIL — `captured["allowed_sources"]` is `None`, not the list.

- [ ] **Step 3: Implement**

Edit `src/aichemy/preprocessing/augment/prices.py:385`:

```python
        resolver = PubChemSdfResolver.from_files(
            sdf_files,
            allowed_sources=set(cfg.aichemy_pricing.allowed_sources)
            if cfg.aichemy_pricing.allowed_sources
            else None,
        )
```

(The resolver expects `set[str] | None`; convert from the YAML list.)

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_prices.py::test_make_lookup_aichemy_pricing_passes_allowed_sources -v
```

Expected: PASS. The assertion compares to a `set` form; production code converts the YAML list at the resolver boundary.

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/preprocessing/augment/prices.py tests/unit/test_prices.py
git commit -m "feat(pricing): plumb allowed_sources into PubChemSdfResolver.from_files"
```

---

## Task 5: Parallelize `augment_prices` dispatch via `ThreadPoolExecutor`

**Files:**
- Modify: `src/aichemy/preprocessing/augment/prices.py:443-464` (`augment_prices`)
- Test: `tests/unit/test_prices.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_prices.py`:

```python
def test_augment_prices_serial_default_unchanged() -> None:
    """max_workers=1 must produce the same DataFrame as the prior serial
    implementation (back-compat for existing DVC runs)."""
    import polars as pl

    from aichemy.preprocessing.augment.prices import StubPriceLookup, augment_prices

    df = pl.DataFrame({"canonical_smiles": ["CCO", "CCO", "CCC", "O"]})
    lookup = StubPriceLookup({"CCO": 0.003, "CCC": None, "O": 0.0001})
    out = augment_prices(df, lookup, max_workers=1)
    assert out.get_column("price_per_gram").to_list() == [0.003, 0.003, None, 0.0001]


def test_augment_prices_parallel_dispatch_matches_serial() -> None:
    """With max_workers > 1, the result DataFrame must be identical to the
    serial result (deterministic regardless of thread scheduling)."""
    import polars as pl

    from aichemy.preprocessing.augment.prices import StubPriceLookup, augment_prices

    smiles_unique = [f"C{i}" for i in range(50)]  # 50 unique
    df = pl.DataFrame({"canonical_smiles": smiles_unique * 3})  # 150 rows, dedup → 50
    prices = {s: float(i) for i, s in enumerate(smiles_unique)}
    lookup = StubPriceLookup(prices)

    serial = augment_prices(df, lookup, max_workers=1)
    parallel = augment_prices(df, lookup, max_workers=10)
    assert serial.equals(parallel)


def test_augment_prices_parallel_actually_runs_concurrently() -> None:
    """Sanity-check that max_workers>1 actually parallelizes: a lookup with a
    100ms sleep should complete in <1s for 20 unique SMILES at max_workers=10
    (vs ~2s serial). Loose assertion to avoid flake."""
    import time

    import polars as pl

    from aichemy.preprocessing.augment.prices import augment_prices

    class _SlowLookup:
        def lookup(self, smiles: str) -> float | None:
            time.sleep(0.1)
            return 1.0

    df = pl.DataFrame({"canonical_smiles": [f"C{i}" for i in range(20)]})
    t0 = time.monotonic()
    augment_prices(df, _SlowLookup(), max_workers=10)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, f"parallel dispatch too slow: {elapsed:.2f}s (expected <1s)"
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/unit/test_prices.py -k "augment_prices_serial_default_unchanged or augment_prices_parallel" -v
```

Expected: FAIL — `augment_prices()` doesn't accept a `max_workers` kwarg yet (`TypeError: unexpected keyword argument 'max_workers'`).

- [ ] **Step 3: Implement**

Replace `augment_prices` in `src/aichemy/preprocessing/augment/prices.py:443-464` with:

```python
def augment_prices(
    molecules: pl.DataFrame,
    lookup: PriceLookup,
    max_workers: int = 1,
) -> pl.DataFrame:
    """Populate `price_per_gram` on a molecules DataFrame via the lookup.

    Iterates UNIQUE SMILES (so the cost scales with chemical diversity, not
    row count). With `max_workers=1` the dispatch is a serial loop — identical
    to prior behavior. With `max_workers>1` a `ThreadPoolExecutor` parallelizes
    the per-SMILES `lookup.lookup(...)` calls; required for 100K-compound runs
    where L3 Browserbase calls dominate wall-clock (~5–10s each). The lookup
    must be thread-safe at this scale (see `aichemy_pricing.chain.CachedPriceLookup`
    + `aichemy_pricing.ratelimit.TokenBucket`).

    Missing prices remain None — the downstream MILP can still run with
    partial pricing.
    """
    if "canonical_smiles" not in molecules.columns:
        raise ValueError("augment_prices requires a 'canonical_smiles' column")
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    unique_smiles: list[str] = molecules.get_column("canonical_smiles").unique().to_list()

    if max_workers == 1:
        prices: dict[str, float | None] = {s: lookup.lookup(s) for s in unique_smiles}
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            prices = dict(zip(unique_smiles, ex.map(lookup.lookup, unique_smiles), strict=True))

    return molecules.with_columns(
        pl.col("canonical_smiles")
        .map_elements(lambda s: prices.get(s), return_dtype=pl.Float64)
        .alias("price_per_gram"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/unit/test_prices.py -k "augment_prices_serial_default_unchanged or augment_prices_parallel" -v
```

Expected: 3 PASS.

- [ ] **Step 5: Wire `max_workers` from the CLI call site**

Find the call site (likely `src/aichemy/cli/__main__.py` or `src/aichemy/preprocessing/augment/__init__.py`):

```
grep -RnE "augment_prices\(" src/aichemy/ --include="*.py"
```

For the call(s) in production code (NOT tests), update:

```python
# Before:
out = augment_prices(molecules, lookup)

# After:
out = augment_prices(molecules, lookup, max_workers=cfg.prices.aichemy_pricing.max_workers)
```

(Only meaningful when `backend="aichemy_pricing"`. For other backends, max_workers stays 1 — the chained/stub backends don't benefit from parallel dispatch and may not be thread-safe.)

- [ ] **Step 6: Run full prices test module to confirm no regressions**

```
uv run pytest tests/unit/test_prices.py -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/aichemy/preprocessing/augment/prices.py tests/unit/test_prices.py src/aichemy/cli  # adjust per actual call-site path
git commit -m "feat(pricing): parallelize augment_prices via ThreadPoolExecutor"
```

---

## Task 6: Validation — run augment-prices on the 500-mol subset end-to-end

**Files (operational, not committed):**
- Download: `data/raw/pubchem_substance/Substance_*.sdf.gz` (~60 GB, 982 shards)
- Output: `data_subset/interim/augmented/molecules_priced.parquet`

- [ ] **Step 1: Download the PubChem Substance FTP dump**

```bash
mkdir -p data/raw/pubchem_substance
cd data/raw/pubchem_substance
# Parallel download with curl, 8 streams. ~15-25 min depending on link.
curl -sS https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/ \
  | grep -oE 'Substance_[0-9_]+\.sdf\.gz' | sort -u \
  | xargs -P 8 -I {} curl -sS -O https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/{}
ls -1 *.sdf.gz | wc -l   # expect 982
du -sh .                 # expect ~60 GB
```

- [ ] **Step 2: Build the subset (if not already present)**

```bash
ls data_subset/processed/molecules.parquet || ./scripts/build_subset.sh
```

- [ ] **Step 3: Run the augment-prices stage on the subset**

```bash
BROWSERBASE_API_KEY=<your-key> uv run aichemy augment prices \
  --config configs/default.yaml \
  --override configs/subset.yaml \
  --override <(cat <<'EOF'
prices:
  backend: aichemy_pricing
EOF
)
```

(Or — if the multi-override syntax isn't supported — temporarily edit `configs/subset.yaml` to set `prices.backend: aichemy_pricing` for this run and revert after.)

Expected wall-clock: a few minutes for 493 molecules with `max_workers=100`. Browserbase spend bounded by L3 hit rate (likely a few cents at this scale).

- [ ] **Step 4: Read out coverage stats**

```bash
uv run python -c "
import polars as pl
df = pl.read_parquet('data_subset/interim/augmented/molecules_priced.parquet')
print('total:', df.height)
priced = df.filter(pl.col('price_per_gram').is_not_null())
print('priced:', priced.height, f'({100*priced.height/df.height:.1f}%)')
print()
print('price summary (USD/g):')
print(priced.select('price_per_gram').describe())
print()
print('first 10 priced rows:')
print(priced.select(['inchi_key', 'canonical_smiles', 'price_per_gram']).head(10))
"
```

- [ ] **Step 5: Decide next steps based on coverage**

- If coverage > 30%: ship the PR; the scalability changes work.
- If coverage 5–30%: ship the PR; add a follow-up task to expand `allowed_sources` and/or layer Enamine BB SDFs.
- If coverage < 5%: don't block the PR (the changes are correct), but flag that the USPTO subset is mostly synthetic intermediates not in commercial vendor catalogs. Recommend running on a benchmark drug-like dataset to demonstrate end-to-end value.

(Operational task — no commit.)

---

## Task 7: Open the PR

- [ ] **Step 1: Run the full impacted test scope**

```
uv run pytest tests/unit/test_config.py tests/unit/test_prices.py src/aichemy_pricing/tests/test_cache.py -v
```

Expected: all PASS.

- [ ] **Step 2: Push and open draft PR**

```bash
git push -u origin feat/pricing-scalability
gh pr create --draft --base pricing-integration \
  --title "feat(pricing): allowed_sources + parallel augment_prices for 100K-scale runs" \
  --body "$(cat <<'EOF'
## Summary

Two minimum-diff changes that together make the `augment_prices` DVC stage
viable at 100K-reaction scale.

- **Memory:** `AichemyPricingConfig.allowed_sources` (vendor allowlist) is now
  threaded through `make_lookup()` into `PubChemSdfResolver.from_files()`.
  The resolver docstring already required this for production runs (491M
  PubChem SIDs OOM otherwise); the integration just wasn't passing it.
- **Wall-clock:** `augment_prices()` now accepts `max_workers` and dispatches
  via `ThreadPoolExecutor.map`. `max_workers=1` matches today's serial
  behavior (back-compat); `max_workers=100` is the default in `default.yaml`,
  matching the master plan's "30–40 min at 100 concurrent" target.
- **Thread safety:** `aichemy_pricing.chain.CachedPriceLookup` switched to
  per-thread SQLite connections (was raising `ProgrammingError` from worker
  threads under the old shared-connection model). `TokenBucket` was already
  thread-safe.

Validated end-to-end on the 500-molecule `data_subset/` with
`backend: aichemy_pricing` — see PR description for coverage numbers.

## Test plan

- [ ] Unit: `pytest tests/unit/test_config.py tests/unit/test_prices.py src/aichemy_pricing/tests/test_cache.py`
- [ ] Integration: `aichemy augment prices --override configs/subset.yaml` produces non-zero priced rows
- [ ] Confirm Browserbase spend stayed within budget on the validation run

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review

**Spec coverage:** Both blockers from the brainstorming round (memory via `allowed_sources`, wall-clock via thread-pool) have dedicated tasks. The third silent blocker (cache thread-safety) is addressed in Task 3 — without it, the parallel dispatch in Task 5 would crash in production. The validation in Task 6 closes the loop on the original "are molecules being priced?" question.

**Type consistency:** `allowed_sources` is `list[str] | None` in pydantic / yaml (lists are the natural YAML type) and converted to `set[str] | None` at the `PubChemSdfResolver.from_files()` boundary. `max_workers` is `int` everywhere. The new `max_workers` arg on `augment_prices` defaults to `1` for back-compat with any non-DVC callers.

**Out-of-scope (intentional):**
- The `chained` backend's `CachedPriceLookup` (in `src/aichemy/preprocessing/augment/prices.py`) is NOT made thread-safe here — it's only used by `backend="chained"`, which we're not scaling.
- The PubChem SDF download itself isn't checked into DVC; that's a separate operational decision and the path lives at `data/raw/pubchem_substance/` which is `.gitignore`d already.
- No changes to L3 Browserbase concurrency — the chain layer already supports concurrent calls (sessions are independent), and Browserbase plan limits are an account-level concern.
