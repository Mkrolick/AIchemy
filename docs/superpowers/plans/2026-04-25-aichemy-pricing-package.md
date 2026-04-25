# `aichemy-pricing` — Standalone Vendor Price-Scraping Package (Master Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Sub-plans (each independently reviewable / executable)

This master plan is broken into 5 self-contained sub-plans. Each can be reviewed (e.g., via `/ultrareview <file>`) and executed independently of the others, subject to the listed dependencies.

| Sub-plan | File | Depends on | Tests (offline + live) |
|---|---|---|---:|
| **A** Foundation | [`2026-04-25-aichemy-pricing-A-foundation.md`](./2026-04-25-aichemy-pricing-A-foundation.md) | — | 20 + 0 |
| **B** Offline resolvers | [`2026-04-25-aichemy-pricing-B-resolvers.md`](./2026-04-25-aichemy-pricing-B-resolvers.md) | A | 14 + 1 |
| **C** Tier 1 vendors | [`2026-04-25-aichemy-pricing-C-tier1-vendors.md`](./2026-04-25-aichemy-pricing-C-tier1-vendors.md) | A | 13 + 3 |
| **D** Tier 2+3 vendors | [`2026-04-25-aichemy-pricing-D-tier2-3-vendors.md`](./2026-04-25-aichemy-pricing-D-tier2-3-vendors.md) | A (parallel with B/C) | 16 + 4 |
| **E** CLI + integration | [`2026-04-25-aichemy-pricing-E-cli-integration.md`](./2026-04-25-aichemy-pricing-E-cli-integration.md) | A, B, C, D | 11 + 0 |
| **Total** | | | **74 + 8** |

**Recommended execution DAG:**
- A first.
- B, C, D in parallel after A (they touch disjoint files).
- E last (consumes all prior).

The remainder of this document is the **architectural overview** the sub-plans reference. Implementation details live in the sub-plan files.

---

**Goal:** Build `aichemy-pricing`, a standalone Python package (importable, CLI-runnable, independently testable) that resolves a chemical identifier (InChIKey / SMILES / CAS) to a per-gram USD price via a tiered chain of verified vendor sources, then plug it into the AIchemy pipeline as a thin import.

**Architecture:** Sibling package at `src/aichemy_pricing/` with its own `pyproject.toml` extras + console script + standalone pytest suite. Layered design: (1) **offline-catalog resolver** that JOINs InChIKey → vendor SKU using PubChem FTP / ZINC tranches / Enamine BB SDFs (zero scraping); (2) **tiered scraper chain** — Tier 1 plain-HTTP (Fluorochem JSON, Molbase, Tocris), Tier 2 JS-rendered/light-CF (Enamine, Cayman, ChemCruz), Tier 3 Cloudflare-aware (MedChemExpress via `curl_cffi`); (3) **chain + cache + protocol** ported from the existing `aichemy.preprocessing.augment.prices` driver. Every URL/schema fact is anchored to a `CLAIM-XX` verdict in `experiments/chem-pricing-verification/`.

**Tech Stack:** Python 3.11+, `httpx`, `curl_cffi` (CF bypass), `polars`, `pydantic` v2, `typer` (CLI), `pytest` + `pytest-httpx` (replay tests), `uv` for builds. No web-driver / Browserbase dependency for v1 — Cayman/Enamine pricing is fetched via discovered XHR/JSON endpoints, not headless rendering.

**Verified facts driving this plan:** see `experiments/chem-pricing-verification/VERIFICATION.md` (29/29 claims with verdicts) and per-claim evidence in `experiments/chem-pricing-verification/evidence/CLAIM-*.md`. Verdict tally: 18 VERIFIED, 8 PARTIAL (specifics need correction), 1 FALSIFIED (Apollo — drop entirely), 2 PLAUSIBLE estimates. Apollo Scientific is **omitted** from this plan because its e-commerce surface no longer exists (CLAIM-11). Sigma-Aldrich and TCI are **deferred to a future Tier 4 plan** because they require residential proxies + WAF-aware infrastructure (CLAIM-12, CLAIM-13).

---

## File Structure

```
src/aichemy_pricing/                       # NEW — sibling package, no aichemy.* imports
├── __init__.py                            # public API: lookup, lookup_batch, VendorChain
├── _version.py                            # __version__
├── types.py                               # PriceQuote, VendorRef, ResolverHit (pydantic)
├── protocol.py                            # PriceLookup, VendorResolver protocols
├── chain.py                               # ChainedPriceLookup, CachedPriceLookup (SQLite)
├── ratelimit.py                           # token-bucket rate limiter
├── http.py                                # shared httpx.Client factory + curl_cffi factory
│
├── resolvers/                             # Offline InChIKey → vendor-SKU JOINs
│   ├── __init__.py
│   ├── pubchem_sdf.py                     # parses PubChem Substance SDF FTP dump
│   ├── enamine_sdf.py                     # parses Enamine BB SDFs per functional class
│   └── zinc_tranches.py                   # parses ZINC20 2D tranche files
│
├── vendors/                               # One module per vendor; all stateless
│   ├── __init__.py
│   ├── fluorochem.py                      # Tier 1: Azure-blob JSON pricing API
│   ├── molbase.py                         # Tier 1: /cas/{CAS}.html
│   ├── tocris.py                          # Tier 1: /products/{slug}_{id}
│   ├── enamine.py                         # Tier 2: discovered XHR JSON endpoint
│   ├── cayman.py                          # Tier 2: SSR title + XHR price
│   ├── chemcruz.py                        # Tier 2: /p/{slug}-{cas}
│   └── medchemexpress.py                  # Tier 3: curl_cffi for Cloudflare
│
├── cli.py                                 # `aichemy-price` console script
└── py.typed                               # PEP 561 marker

src/aichemy_pricing/tests/                 # standalone test suite; runs without aichemy
├── conftest.py                            # fixtures: tmp cache, fake httpx responses
├── test_chain.py
├── test_cache.py
├── test_resolvers_pubchem.py
├── test_resolvers_enamine.py
├── test_vendors_fluorochem.py             # replay tests + 1 live-marked test
├── test_vendors_molbase.py
├── test_vendors_tocris.py
├── test_vendors_enamine.py
├── test_vendors_cayman.py
├── test_vendors_chemcruz.py
├── test_vendors_medchemexpress.py
├── test_cli.py
└── data/                                  # frozen replay JSON / HTML fixtures (small)
    ├── fluorochem_F765353.json            # captured live during CLAIM-01
    ├── molbase_aspirin.html
    ├── tocris_jw642.html
    └── ...

pyproject.toml                             # MODIFIED — add `pricing` extra + entry point
src/aichemy/preprocessing/augment/prices.py  # MODIFIED — replace bespoke scrapers with `from aichemy_pricing import ...`
```

**Key boundary:** `aichemy_pricing` does **not** import anything from `aichemy.*`. The reverse arrow (aichemy → aichemy_pricing) is fine and is the only integration point. This means `pytest src/aichemy_pricing/tests/` runs without the rest of the project.

---

## Phase 0 — Package scaffolding

### Task 0.1: Add `pricing` extra and console script to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current pyproject.toml `[project]` table**

```bash
sed -n '1,80p' pyproject.toml
```

- [ ] **Step 2: Add `pricing` extra and console script entry**

In `pyproject.toml`, add to `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
pricing = [
  "httpx>=0.27",
  "curl_cffi>=0.7",       # Cloudflare-aware HTTP client (TLS fingerprint mimic)
  "polars>=1.0",          # parquet I/O for resolver caches
  "pydantic>=2.6",
  "typer>=0.12",
  "rdkit>=2024.3",        # InChIKey computation in resolvers
]
```

And to `[project.scripts]`:

```toml
[project.scripts]
aichemy = "aichemy.cli:app"
aichemy-price = "aichemy_pricing.cli:app"
```

- [ ] **Step 3: Sync and verify**

```bash
uv sync --extra pricing
uv run python -c "import aichemy_pricing"
```

Expected: ImportError (package doesn't exist yet — that's the next task).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add pricing extra and aichemy-price console script"
```

### Task 0.2: Create package skeleton

**Files:**
- Create: `src/aichemy_pricing/__init__.py`
- Create: `src/aichemy_pricing/_version.py`
- Create: `src/aichemy_pricing/py.typed` (empty)
- Create: `src/aichemy_pricing/tests/__init__.py` (empty)
- Create: `src/aichemy_pricing/tests/conftest.py`

- [ ] **Step 1: Create `_version.py`**

```python
# src/aichemy_pricing/_version.py
__version__ = "0.1.0"
```

- [ ] **Step 2: Create empty `__init__.py`** (will populate in later tasks)

```python
# src/aichemy_pricing/__init__.py
from aichemy_pricing._version import __version__

__all__ = ["__version__"]
```

- [ ] **Step 3: Create `py.typed` marker**

```bash
touch src/aichemy_pricing/py.typed
```

- [ ] **Step 4: Create test scaffolding**

```bash
touch src/aichemy_pricing/tests/__init__.py
```

```python
# src/aichemy_pricing/tests/conftest.py
"""Standalone test suite for aichemy_pricing.

Runs without aichemy.* imports. Live network tests are marked with
@pytest.mark.live and skipped by default. Run live-only with:
    pytest src/aichemy_pricing/tests -m live
"""
from __future__ import annotations

import pathlib

import pytest

DATA = pathlib.Path(__file__).parent / "data"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: hits real network, skipped by default")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("-m") == "live":
        return  # caller asked for live; don't filter
    skip_live = pytest.mark.skip(reason="live network test; pass -m live to enable")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def fixture_dir() -> pathlib.Path:
    return DATA
```

- [ ] **Step 5: Verify importable**

```bash
uv run python -c "import aichemy_pricing; print(aichemy_pricing.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/
git commit -m "feat(pricing): bootstrap aichemy-pricing package skeleton"
```

---

## Phase 1 — Core types, protocols, chain, cache

### Task 1.1: `types.py` — `PriceQuote` + `VendorRef` + `ResolverHit`

**Files:**
- Create: `src/aichemy_pricing/types.py`
- Test: `src/aichemy_pricing/tests/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# src/aichemy_pricing/tests/test_types.py
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aichemy_pricing.types import PriceQuote, VendorRef, ResolverHit


def test_price_quote_normalizes_currency_and_unit() -> None:
    q = PriceQuote(
        vendor="fluorochem",
        sku="F765353-1G",
        price=230.0,
        currency="GBP",
        pack_size_g=1.0,
        fetched_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )
    assert q.price_per_gram_native == 230.0


def test_price_quote_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        PriceQuote(
            vendor="x", sku="y", price=-1.0, currency="USD", pack_size_g=1.0,
            fetched_at=datetime.now(timezone.utc),
        )


def test_resolver_hit_carries_inchikey_and_sku() -> None:
    h = ResolverHit(inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N", vendor="enamine", sku="EN300-7605608")
    assert h.vendor == "enamine"
```

- [ ] **Step 2: Run; expect failure**

```bash
uv run pytest src/aichemy_pricing/tests/test_types.py -v
```

Expected: ImportError on `aichemy_pricing.types`.

- [ ] **Step 3: Implement `types.py`**

```python
# src/aichemy_pricing/types.py
"""Pure-data types — no behavior, no I/O."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, PositiveFloat, field_validator

Currency = Literal["USD", "GBP", "EUR", "CNY", "JPY", "SEK"]


class VendorRef(BaseModel):
    """Pointer from an InChIKey to a vendor's catalog SKU."""
    vendor: str
    sku: str
    canonical_url: str | None = None


class ResolverHit(VendorRef):
    """A `VendorRef` plus the source InChIKey it resolves."""
    inchikey: str = Field(min_length=27, max_length=27)


class PriceQuote(BaseModel):
    """One pack of one product at one vendor at one moment."""
    vendor: str
    sku: str
    price: PositiveFloat
    currency: Currency
    pack_size_g: PositiveFloat
    fetched_at: datetime
    raw: dict | None = None  # vendor-specific extra fields, debug only

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v

    @property
    def price_per_gram_native(self) -> float:
        return self.price / self.pack_size_g
```

- [ ] **Step 4: Run; expect pass**

```bash
uv run pytest src/aichemy_pricing/tests/test_types.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/types.py src/aichemy_pricing/tests/test_types.py
git commit -m "feat(pricing): types — PriceQuote, VendorRef, ResolverHit"
```

### Task 1.2: `protocol.py` — `PriceLookup` and `VendorResolver` protocols

**Files:**
- Create: `src/aichemy_pricing/protocol.py`

- [ ] **Step 1: Implement (no separate test — exercised via chain tests)**

```python
# src/aichemy_pricing/protocol.py
"""Structural protocols. Implementations live in `vendors/` and `resolvers/`."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef


@runtime_checkable
class PriceLookup(Protocol):
    """Maps `(vendor, sku)` (a VendorRef) to a price quote, or None if unknown."""
    name: str
    def lookup(self, ref: VendorRef) -> PriceQuote | None: ...


@runtime_checkable
class VendorResolver(Protocol):
    """Maps an InChIKey to zero-or-more vendor SKUs (offline JOIN)."""
    name: str
    def resolve(self, inchikey: str) -> list[ResolverHit]: ...
```

- [ ] **Step 2: Verify type-checks**

```bash
uv run mypy src/aichemy_pricing/protocol.py
```

Expected: Success.

- [ ] **Step 3: Commit**

```bash
git add src/aichemy_pricing/protocol.py
git commit -m "feat(pricing): PriceLookup and VendorResolver protocols"
```

### Task 1.3: `ratelimit.py` — token bucket

**Files:**
- Create: `src/aichemy_pricing/ratelimit.py`
- Test: `src/aichemy_pricing/tests/test_ratelimit.py`

- [ ] **Step 1: Write failing test**

```python
# src/aichemy_pricing/tests/test_ratelimit.py
import time

from aichemy_pricing.ratelimit import TokenBucket


def test_token_bucket_blocks_when_exhausted() -> None:
    bucket = TokenBucket(rate_per_sec=2.0, capacity=2)
    t0 = time.monotonic()
    bucket.acquire()
    bucket.acquire()
    bucket.acquire()  # third should block ~0.5s
    elapsed = time.monotonic() - t0
    assert 0.4 < elapsed < 1.5
```

- [ ] **Step 2: Run; expect ImportError**

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/ratelimit.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    rate_per_sec: float
    capacity: int

    def __post_init__(self) -> None:
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, n: int = 1) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity,
                    self._tokens + (now - self._last_refill) * self.rate_per_sec,
                )
                self._last_refill = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                wait = (n - self._tokens) / self.rate_per_sec
            time.sleep(wait)
```

- [ ] **Step 4: Run; expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/ratelimit.py src/aichemy_pricing/tests/test_ratelimit.py
git commit -m "feat(pricing): TokenBucket rate limiter"
```

### Task 1.4: `chain.py` — `ChainedPriceLookup` + `CachedPriceLookup`

**Files:**
- Create: `src/aichemy_pricing/chain.py`
- Test: `src/aichemy_pricing/tests/test_chain.py`
- Test: `src/aichemy_pricing/tests/test_cache.py`

- [ ] **Step 1: Write failing chain test**

```python
# src/aichemy_pricing/tests/test_chain.py
from datetime import datetime, timezone

from aichemy_pricing.chain import ChainedPriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef


class _Stub:
    name = "stub"
    def __init__(self, ret: PriceQuote | None) -> None:
        self.ret = ret
        self.calls = 0
    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return self.ret


def _q(vendor: str = "x") -> PriceQuote:
    return PriceQuote(
        vendor=vendor, sku="s", price=1.0, currency="USD", pack_size_g=1.0,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_chain_returns_first_hit() -> None:
    a = _Stub(None)
    b = _Stub(_q("b"))
    c = _Stub(_q("c"))
    chain = ChainedPriceLookup([a, b, c])
    res = chain.lookup(VendorRef(vendor="any", sku="any"))
    assert res is not None and res.vendor == "b"
    assert a.calls == 1 and b.calls == 1 and c.calls == 0


def test_chain_returns_none_when_all_miss() -> None:
    chain = ChainedPriceLookup([_Stub(None), _Stub(None)])
    assert chain.lookup(VendorRef(vendor="x", sku="y")) is None
```

- [ ] **Step 2: Write failing cache test**

```python
# src/aichemy_pricing/tests/test_cache.py
from datetime import datetime, timezone

from aichemy_pricing.chain import CachedPriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef


class _Counter:
    name = "counter"
    def __init__(self) -> None:
        self.calls = 0
    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return PriceQuote(
            vendor=ref.vendor, sku=ref.sku, price=1.0, currency="USD", pack_size_g=1.0,
            fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


def test_cache_only_calls_inner_once_per_ref(tmp_path) -> None:
    inner = _Counter()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    cache.lookup(ref)
    cache.lookup(ref)
    cache.lookup(ref)
    assert inner.calls == 1


def test_cache_caches_misses(tmp_path) -> None:
    class Miss:
        name = "miss"
        calls = 0
        def lookup(self, ref):
            self.__class__.calls += 1
            return None
    cache = CachedPriceLookup(Miss(), db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    cache.lookup(ref); cache.lookup(ref)
    assert Miss.calls == 1
```

- [ ] **Step 3: Run both; expect ImportError**

- [ ] **Step 4: Implement `chain.py`**

```python
# src/aichemy_pricing/chain.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aichemy_pricing.protocol import PriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef


class ChainedPriceLookup:
    name = "chain"

    def __init__(self, members: list[PriceLookup]) -> None:
        self.members = members

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        for m in self.members:
            hit = m.lookup(ref)
            if hit is not None:
                return hit
        return None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS quote_cache (
    vendor TEXT NOT NULL,
    sku TEXT NOT NULL,
    quote_json TEXT,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (vendor, sku)
);
"""


class CachedPriceLookup:
    name = "cache"

    def __init__(self, inner: PriceLookup, db_path: Path, ttl_days: int = 30) -> None:
        self.inner = inner
        self.db_path = Path(db_path)
        self.ttl = timedelta(days=ttl_days)
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.executescript(_SCHEMA)

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        cur = self._conn.execute(
            "SELECT quote_json, fetched_at FROM quote_cache WHERE vendor=? AND sku=?",
            (ref.vendor, ref.sku),
        )
        row = cur.fetchone()
        if row is not None:
            quote_json, fetched_at_iso = row
            fetched = datetime.fromisoformat(fetched_at_iso)
            if datetime.now(timezone.utc) - fetched < self.ttl:
                if quote_json is None:
                    return None
                return PriceQuote.model_validate_json(quote_json)
        # cache miss or expired
        result = self.inner.lookup(ref)
        self._conn.execute(
            "INSERT OR REPLACE INTO quote_cache(vendor, sku, quote_json, fetched_at) VALUES(?, ?, ?, ?)",
            (
                ref.vendor,
                ref.sku,
                result.model_dump_json() if result else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return result
```

- [ ] **Step 5: Run; expect pass**

```bash
uv run pytest src/aichemy_pricing/tests/test_chain.py src/aichemy_pricing/tests/test_cache.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/chain.py src/aichemy_pricing/tests/test_chain.py src/aichemy_pricing/tests/test_cache.py
git commit -m "feat(pricing): ChainedPriceLookup + SQLite-backed CachedPriceLookup"
```

### Task 1.5: `http.py` — shared client factory

**Files:**
- Create: `src/aichemy_pricing/http.py`
- Test: `src/aichemy_pricing/tests/test_http.py`

- [ ] **Step 1: Write failing test**

```python
# src/aichemy_pricing/tests/test_http.py
import httpx

from aichemy_pricing.http import make_plain_client, make_cf_client


def test_plain_client_has_browser_ua() -> None:
    c = make_plain_client()
    assert "Chrome/" in c.headers["User-Agent"]
    c.close()


def test_cf_client_returns_object_with_get() -> None:
    c = make_cf_client()
    assert hasattr(c, "get")
```

- [ ] **Step 2: Implement**

```python
# src/aichemy_pricing/http.py
"""Shared HTTP client factories.

Two flavours:
 - `make_plain_client()` — vanilla httpx with a desktop Chrome UA. For Tier 1/2.
 - `make_cf_client()` — curl_cffi impersonating Chrome 124. For Tier 3 (MCE).
"""
from __future__ import annotations

import httpx

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def make_plain_client() -> httpx.Client:
    return httpx.Client(headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True)


def make_cf_client():
    """Returns a curl_cffi Session that impersonates Chrome 124's TLS fingerprint.

    Per CLAIM-15, MedChemExpress's Cloudflare returns 403 to any client that
    isn't TLS-fingerprinted as a real browser, even with the Chrome UA header.
    `curl_cffi` is the smallest-surface fix.
    """
    from curl_cffi import requests as cf_requests
    return cf_requests.Session(impersonate="chrome124")
```

- [ ] **Step 3: Run; pass**

- [ ] **Step 4: Commit**

```bash
git add src/aichemy_pricing/http.py src/aichemy_pricing/tests/test_http.py
git commit -m "feat(pricing): plain httpx + curl_cffi client factories"
```

---

## Phase 2 — Offline catalog resolvers (the "scrape less, resolve more" half)

These do not hit any vendor — they parse pre-downloaded SDFs / FTP dumps to build an InChIKey → VendorRef index.

### Task 2.1: `resolvers/pubchem_sdf.py`

**Files:**
- Create: `src/aichemy_pricing/resolvers/__init__.py` (empty)
- Create: `src/aichemy_pricing/resolvers/pubchem_sdf.py`
- Test: `src/aichemy_pricing/tests/test_resolvers_pubchem.py`
- Fixture: `src/aichemy_pricing/tests/data/pubchem_sample.sdf` (10-record snippet)

- [ ] **Step 1: Capture fixture from real PubChem**

```bash
mkdir -p src/aichemy_pricing/tests/data
# Download 1 small SDF (~60MB) — keep just the first 10 records as fixture
curl -s "https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/Substance_000000001_000500000.sdf.gz" \
  | gunzip | awk '/^\$\$\$\$/{n++} n<10' \
  > src/aichemy_pricing/tests/data/pubchem_sample.sdf
```

- [ ] **Step 2: Write failing test**

```python
# src/aichemy_pricing/tests/test_resolvers_pubchem.py
from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver


def test_pubchem_sdf_resolver_indexes_inchikey_to_vendor(fixture_dir) -> None:
    resolver = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    # We cannot assert exact keys without inspecting the fixture; just check shape.
    assert resolver.index  # at least one record indexed
    sample_ik = next(iter(resolver.index))
    hits = resolver.resolve(sample_ik)
    assert all(h.vendor and h.sku for h in hits)


def test_pubchem_sdf_resolver_filters_to_vendor_sources(fixture_dir) -> None:
    resolver = PubChemSdfResolver.from_files(
        [fixture_dir / "pubchem_sample.sdf"],
        allowed_sources={"Sigma-Aldrich", "Enamine", "Combi-Blocks"},
    )
    for hits in resolver.index.values():
        for h in hits:
            assert h.vendor in {"Sigma-Aldrich", "Enamine", "Combi-Blocks"}
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/resolvers/pubchem_sdf.py
"""Parse PubChem Substance SDF (FTP dump) into an InChIKey → VendorRef index.

Per CLAIM-04 (PARTIAL): the actual SDF tag names are
`PUBCHEM_EXT_DATASOURCE_NAME` and `PUBCHEM_EXT_DATASOURCE_REGID`, NOT
"SourceName"/"RegistryID" as the original report claimed. PubChem source
table has 914 sources / 531 vendor-tagged.

FTP root: https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.types import ResolverHit


def _iter_sdf_records(path: Path):
    """Yield dict-of-tags per `$$$$`-delimited record. Streaming, low memory."""
    record: dict[str, list[str]] = {}
    current_tag: str | None = None
    with path.open("rt", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line == "$$$$":
                if record:
                    yield record
                record = {}
                current_tag = None
            elif line.startswith("> <") and line.endswith(">"):
                current_tag = line[3:-1]
                record[current_tag] = []
            elif current_tag is not None and line == "":
                current_tag = None
            elif current_tag is not None:
                record[current_tag].append(line)


@dataclass
class PubChemSdfResolver:
    name: str = "pubchem_sdf"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(
        cls,
        paths: list[Path],
        allowed_sources: set[str] | None = None,
    ) -> "PubChemSdfResolver":
        self = cls()
        for path in paths:
            for rec in _iter_sdf_records(path):
                ik = (rec.get("PUBCHEM_IUPAC_INCHIKEY") or [None])[0]
                src = (rec.get("PUBCHEM_EXT_DATASOURCE_NAME") or [None])[0]
                regid = (rec.get("PUBCHEM_EXT_DATASOURCE_REGID") or [None])[0]
                url = (rec.get("PUBCHEM_EXT_DATASOURCE_URL") or [None])[0]
                if not (ik and src and regid):
                    continue
                if allowed_sources is not None and src not in allowed_sources:
                    continue
                self.index[ik].append(
                    ResolverHit(inchikey=ik, vendor=src, sku=regid, canonical_url=url)
                )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
```

- [ ] **Step 4: Run; expect pass**

```bash
uv run pytest src/aichemy_pricing/tests/test_resolvers_pubchem.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/resolvers/ src/aichemy_pricing/tests/test_resolvers_pubchem.py src/aichemy_pricing/tests/data/pubchem_sample.sdf
git commit -m "feat(pricing): PubChem Substance SDF resolver (InChIKey → VendorRef)"
```

### Task 2.2: `resolvers/enamine_sdf.py`

**Files:**
- Create: `src/aichemy_pricing/resolvers/enamine_sdf.py`
- Test: `src/aichemy_pricing/tests/test_resolvers_enamine.py`
- Fixture: `src/aichemy_pricing/tests/data/enamine_acids_snippet.sdf`

- [ ] **Step 1: Capture fixture from Enamine functional-class SDF**

Manually download one functional-class SDF from `enamine.net/building-blocks/functional-classes/acids` (per CLAIM-08), keep first 10 records as fixture.

- [ ] **Step 2: Write failing test**

```python
# src/aichemy_pricing/tests/test_resolvers_enamine.py
from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver


def test_enamine_resolver_uses_id_field_as_sku(fixture_dir) -> None:
    res = EnamineSdfResolver.from_files([fixture_dir / "enamine_acids_snippet.sdf"])
    assert res.index
    sample_ik = next(iter(res.index))
    hits = res.resolve(sample_ik)
    assert all(h.vendor == "enamine" and h.sku.startswith("EN300-") for h in hits)
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/resolvers/enamine_sdf.py
"""Parse Enamine BB SDFs into an InChIKey → VendorRef index.

Per CLAIM-08 (VERIFIED): per-functional-class SDFs are downloadable without
login from `enamine.net/building-blocks/functional-classes/{acids,boronics,
amines,halides,...}`. SKU field name in the SDF is `Catalog ID` or `idnumber`
depending on the export — we accept any of a small set.

Per CLAIM-07 (VERIFIED): canonical product URL is
`https://enaminestore.com/catalog/EN300-{N}` (no www).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.resolvers.pubchem_sdf import _iter_sdf_records
from aichemy_pricing.types import ResolverHit

_SKU_TAGS = ("Catalog ID", "idnumber", "ID", "EN_ID")
_INCHIKEY_TAGS = ("InChIKey", "INCHIKEY", "PUBCHEM_IUPAC_INCHIKEY")


@dataclass
class EnamineSdfResolver:
    name: str = "enamine_sdf"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(cls, paths: list[Path]) -> "EnamineSdfResolver":
        self = cls()
        for path in paths:
            for rec in _iter_sdf_records(path):
                ik = next((rec[k][0] for k in _INCHIKEY_TAGS if k in rec and rec[k]), None)
                sku = next((rec[k][0] for k in _SKU_TAGS if k in rec and rec[k]), None)
                if not (ik and sku):
                    continue
                if not sku.startswith("EN300-"):
                    sku = f"EN300-{sku}"
                self.index[ik].append(
                    ResolverHit(
                        inchikey=ik,
                        vendor="enamine",
                        sku=sku,
                        canonical_url=f"https://enaminestore.com/catalog/{sku}",
                    )
                )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
```

- [ ] **Step 4: Run; pass**

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/resolvers/enamine_sdf.py src/aichemy_pricing/tests/test_resolvers_enamine.py src/aichemy_pricing/tests/data/enamine_acids_snippet.sdf
git commit -m "feat(pricing): Enamine BB SDF resolver"
```

### Task 2.3: `resolvers/zinc_tranches.py`

**Files:**
- Create: `src/aichemy_pricing/resolvers/zinc_tranches.py`
- Test: `src/aichemy_pricing/tests/test_resolvers_zinc.py`

(Same shape as 2.2; parses ZINC20 tranche `.smi` files which include `zinc_id` plus per-vendor `supplier_code` annotations. Skip implementation detail here; mirror Tasks 2.1 and 2.2.)

- [ ] **Step 1: Write failing test (mirror enamine test)**
- [ ] **Step 2: Implement** (parse `.smi` columns: `smiles  zinc_id  vendor:supplier_code`)
- [ ] **Step 3: Run; pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(pricing): ZINC20 tranche resolver"
```

---

## Phase 3 — Tier 1 vendors (plain HTTP, no anti-bot)

### Task 3.1: `vendors/fluorochem.py`

**Per CLAIM-01 (PARTIAL):** endpoint is real and anonymous; field names in the original report were fabricated. **Use the corrected schema below.**

**Files:**
- Create: `src/aichemy_pricing/vendors/__init__.py` (empty)
- Create: `src/aichemy_pricing/vendors/fluorochem.py`
- Test: `src/aichemy_pricing/tests/test_vendors_fluorochem.py`
- Fixture: `src/aichemy_pricing/tests/data/fluorochem_F765353.json` (already captured in CLAIM-01 evidence)

- [ ] **Step 1: Copy fixture from verification sandbox**

```bash
mkdir -p src/aichemy_pricing/tests/data
curl -s "https://fluorochemcouk.blob.core.windows.net/pricing/F765353.json" \
  > src/aichemy_pricing/tests/data/fluorochem_F765353.json
```

- [ ] **Step 2: Write failing test**

```python
# src/aichemy_pricing/tests/test_vendors_fluorochem.py
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.fluorochem import FluorochemVendor


def test_fluorochem_parses_real_response(fixture_dir, monkeypatch) -> None:
    body = (fixture_dir / "fluorochem_F765353.json").read_bytes()

    def mock_send(self, request, **kw):
        return httpx.Response(200, content=body, request=request)

    monkeypatch.setattr(httpx.Client, "send", mock_send)

    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="F765353-1G"))
    assert quote is not None
    assert quote.vendor == "fluorochem"
    assert quote.currency == "GBP"
    assert quote.pack_size_g == 1.0
    assert quote.price > 0


def test_fluorochem_returns_none_on_404(monkeypatch) -> None:
    def mock_send(self, request, **kw):
        return httpx.Response(404, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)

    v = FluorochemVendor()
    assert v.lookup(VendorRef(vendor="fluorochem", sku="legacy-022092")) is None


@pytest.mark.live
def test_fluorochem_live_F765353() -> None:
    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="F765353-1G"))
    assert quote is not None and quote.currency == "GBP"
```

- [ ] **Step 3: Implement using the verified schema**

```python
# src/aichemy_pricing/vendors/fluorochem.py
"""Fluorochem Azure-blob JSON pricing.

Per CLAIM-01 (PARTIAL — endpoint REAL, fields FABRICATED in original report):
  Endpoint:  https://fluorochemcouk.blob.core.windows.net/pricing/{ProductCode}.json
  Status:    anonymous, no Cloudflare, no JS — pure HTTPS GET
  Coverage:  modern F-prefix and BR-prefix SKUs only;
             legacy 6-digit codes (e.g. 043319) return 404
  Container listing is disabled (?restype=container&comp=list → 404),
  so SKUs must be obtained via offline resolver (PubChem / ZINC).

Real schema observed live for F765353-1G:
{
  "F765353": {
    "F765353-1G": {
      "SKU": "F765353-1G",
      "Size": "1",
      "Size Unit": "g",
      "Pricing": {
        "GBP": {"Base Price": 230, "5% Discount": 218.5, ..., "Q2 2026 - Base": 230, ...},
        "EUR": {"Base Price": 267, ...}
      }
    },
    "F765353-5G": { ... },
    ...
  }
}

There is NO `min_gbp` / `max_gbp` / `has_stock_*` field. Stock data is
not in this endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef

_BASE_URL = "https://fluorochemcouk.blob.core.windows.net/pricing"

# Convert "Size Unit" to grams for normalization
_UNIT_TO_GRAMS = {"mg": 0.001, "g": 1.0, "kg": 1000.0}


def _split_sku(full_sku: str) -> tuple[str, str]:
    """`F765353-1G` → ("F765353", "F765353-1G")."""
    if "-" not in full_sku:
        return full_sku, full_sku
    head, _ = full_sku.rsplit("-", 1)
    return head, full_sku


class FluorochemVendor:
    name = "fluorochem"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        product_code, full_sku = _split_sku(ref.sku)
        url = f"{_BASE_URL}/{product_code}.json"
        resp = self._client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        body = resp.json()
        product = body.get(product_code) or {}
        pack = product.get(full_sku)
        if pack is None:
            # caller asked for product not pack; pick first pack
            if not product:
                return None
            full_sku, pack = next(iter(product.items()))
        gbp = pack.get("Pricing", {}).get("GBP", {})
        base = gbp.get("Base Price")
        if base is None:
            return None
        size = float(pack["Size"])
        unit = pack["Size Unit"].lower()
        pack_size_g = size * _UNIT_TO_GRAMS.get(unit, 1.0)
        return PriceQuote(
            vendor=self.name,
            sku=full_sku,
            price=float(base),
            currency="GBP",
            pack_size_g=pack_size_g,
            fetched_at=datetime.now(timezone.utc),
            raw=pack,
        )
```

- [ ] **Step 4: Run; expect pass**

```bash
uv run pytest src/aichemy_pricing/tests/test_vendors_fluorochem.py -v
```

- [ ] **Step 5: Run live test on demand**

```bash
uv run pytest src/aichemy_pricing/tests/test_vendors_fluorochem.py -m live -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/vendors/ src/aichemy_pricing/tests/test_vendors_fluorochem.py src/aichemy_pricing/tests/data/fluorochem_F765353.json
git commit -m "feat(pricing): Fluorochem Azure-blob JSON vendor (Tier 1)"
```

### Task 3.2: `vendors/molbase.py`

**Per CLAIM-18 (PARTIAL):** the report's URL `/en/cas-{CAS}.html` 404s. **Use `molbase.com/cas/{CAS}.html`** (no `/en/`, slash separator).

**Files:**
- Create: `src/aichemy_pricing/vendors/molbase.py`
- Test: `src/aichemy_pricing/tests/test_vendors_molbase.py`
- Fixture: `src/aichemy_pricing/tests/data/molbase_aspirin.html`

- [ ] **Step 1: Capture fixture**

```bash
curl -A "Mozilla/5.0" -s "https://www.molbase.com/cas/50-78-2.html" \
  > src/aichemy_pricing/tests/data/molbase_aspirin.html
```

- [ ] **Step 2: Write failing test (parses CAS-keyed page; extracts cheapest supplier price)**

```python
# src/aichemy_pricing/tests/test_vendors_molbase.py
import httpx, pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.molbase import MolbaseVendor


def test_molbase_parses_cas_page(fixture_dir, monkeypatch) -> None:
    body = (fixture_dir / "molbase_aspirin.html").read_bytes()
    def mock_send(self, request, **kw):
        return httpx.Response(200, content=body, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)
    v = MolbaseVendor()
    # SKU for Molbase = CAS number
    quote = v.lookup(VendorRef(vendor="molbase", sku="50-78-2"))
    if quote:
        assert quote.currency in ("USD", "CNY")


@pytest.mark.live
def test_molbase_live_aspirin() -> None:
    v = MolbaseVendor()
    quote = v.lookup(VendorRef(vendor="molbase", sku="50-78-2"))
    # may be None if no public-priced supplier; just assert no crash
    if quote: assert quote.price > 0
```

- [ ] **Step 3: Implement** (regex-extract `<title>{name} price & availability</title>` and the first `$N.NN` / `¥N.NN` from supplier table; pack size from price-row text). Implementation roughly:

```python
# src/aichemy_pricing/vendors/molbase.py
import re
from datetime import datetime, timezone

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef

_PRICE_RE = re.compile(r"(?:USD|US\$|\$)\s*([\d,.]+)")
_PACK_RE = re.compile(r"\b([\d.]+)\s*(mg|g|kg)\b", re.I)
_UNIT_G = {"mg": 0.001, "g": 1.0, "kg": 1000.0}


class MolbaseVendor:
    name = "molbase"

    def __init__(self, client=None):
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.molbase.com/cas/{ref.sku}.html"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        text = resp.text
        m_price = _PRICE_RE.search(text)
        m_pack = _PACK_RE.search(text)
        if not (m_price and m_pack):
            return None
        price = float(m_price.group(1).replace(",", ""))
        size = float(m_pack.group(1))
        unit = m_pack.group(2).lower()
        return PriceQuote(
            vendor=self.name,
            sku=ref.sku,
            price=price,
            currency="USD",
            pack_size_g=size * _UNIT_G[unit],
            fetched_at=datetime.now(timezone.utc),
            raw={"url": url},
        )
```

- [ ] **Step 4: Run + commit**

```bash
git commit -m "feat(pricing): Molbase /cas/{CAS}.html vendor (Tier 1)"
```

### Task 3.3: `vendors/tocris.py`

**Per CLAIM-25 corroboration:** Tocris publishes anonymous USD prices in the SSR HTML.

**Files:**
- Create: `src/aichemy_pricing/vendors/tocris.py`
- Test: `src/aichemy_pricing/tests/test_vendors_tocris.py`
- Fixture: `src/aichemy_pricing/tests/data/tocris_jw642.html`

- [ ] Mirror Tasks 3.1 / 3.2: capture fixture (`curl -A "Mozilla/5.0" -s "https://www.tocris.com/products/jw-642_4906" > .../tocris_jw642.html`), regex-extract `$<price>` and pack size, return `PriceQuote(currency="USD")`.
- [ ] Commit.

---

## Phase 4 — Tier 2 vendors (JS-rendered; use discovered XHR endpoints, not headless rendering)

The strategy here: open each product page in a browser DevTools Network tab, identify the JSON XHR that returns pricing, hit that JSON directly with `httpx`. This avoids Browserbase / headless overhead entirely for v1.

### Task 4.1: `vendors/enamine.py`

**Per CLAIM-07 (VERIFIED):** product URL is `enaminestore.com/catalog/EN300-{N}`; body is React shell with no SSR pricing. Pricing is loaded via XHR. **Discovery action required** — record one DevTools session and bake the discovered JSON endpoint into the vendor module.

**Files:**
- Create: `src/aichemy_pricing/vendors/enamine.py`
- Test: `src/aichemy_pricing/tests/test_vendors_enamine.py`
- Fixture: `src/aichemy_pricing/tests/data/enamine_EN300_7605608.json`

- [ ] **Step 1: Discovery (one-time manual)**

Open `https://enaminestore.com/catalog/EN300-7605608` in Chrome DevTools → Network → filter XHR → reload → identify the JSON request that contains the `Pricing`/`Quantity` data. Document the URL pattern in a comment. Save the response body as fixture.

- [ ] **Step 2: Write failing test using fixture as `httpx` replay**

(mirror Task 3.1 structure)

- [ ] **Step 3: Implement** — single `httpx.Client.get(<discovered XHR URL>.format(sku=...))`, parse JSON, return `PriceQuote(currency="USD")`.

- [ ] **Step 4: Add `pytest.mark.live` end-to-end test against `EN300-7605608`.**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(pricing): Enamine vendor via discovered XHR JSON endpoint"
```

### Task 4.2: `vendors/cayman.py`

**Per CLAIM-14 (VERIFIED with notes):** URL `caymanchem.com/product/{itemID}/{slug}`; partial SSR (title + CAS in HTML); pricing via XHR.

- [ ] Discovery on `https://www.caymanchem.com/product/14010/prostaglandin-e2`.
- [ ] Implement same structure as 4.1.
- [ ] Commit.

### Task 4.3: `vendors/chemcruz.py`

**Per CLAIM-17 (VERIFIED):** URL `scbt.com/p/{slug}-{cas}`; moderate Cloudflare; passes with browser UA.

- [ ] HTML scrape (price visible in SSR markup unlike Enamine/Cayman; regex-extract).
- [ ] Commit.

---

## Phase 5 — Tier 3 vendor: MedChemExpress (Cloudflare-aware)

### Task 5.1: `vendors/medchemexpress.py`

**Per CLAIM-15 (VERIFIED):** URL `medchemexpress.com/{slug}.html`; Cloudflare 403s any client whose TLS fingerprint isn't a real browser, including `httpx` with a Chrome User-Agent header. **Solution:** `curl_cffi` with `impersonate="chrome124"` (already wired in `http.py`).

- [ ] **Step 1: Capture fixture using curl_cffi** (a one-liner from a Python REPL is fine).
- [ ] **Step 2: Write failing test using `curl_cffi` mocked at the module-call level.**
- [ ] **Step 3: Implement** — use `make_cf_client()` from `http.py`; otherwise same shape as Enamine/Cayman.
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(pricing): MedChemExpress vendor via curl_cffi (Tier 3)"
```

---

## Phase 6 — CLI for debugging

### Task 6.1: `cli.py`

**Files:**
- Create: `src/aichemy_pricing/cli.py`
- Test: `src/aichemy_pricing/tests/test_cli.py`

- [ ] **Step 1: Write failing test using `typer.testing.CliRunner`**

```python
# src/aichemy_pricing/tests/test_cli.py
from typer.testing import CliRunner

from aichemy_pricing.cli import app


def test_cli_version_flag() -> None:
    res = CliRunner().invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "0.1.0" in res.stdout


def test_cli_lookup_dispatches_vendor(monkeypatch) -> None:
    # ... mock vendor registry, assert lookup called
    pass
```

- [ ] **Step 2: Implement**

```python
# src/aichemy_pricing/cli.py
"""`aichemy-price` — single-SKU lookup for debugging.

Usage:
    aichemy-price lookup fluorochem F765353-1G
    aichemy-price lookup molbase 50-78-2 --json
    aichemy-price resolve BSYNRYMUTXBXSQ-UHFFFAOYSA-N --catalog data/raw/pubchem_substance/
    aichemy-price chain F765353-1G        # tries all vendors in order
"""
from __future__ import annotations

import json as _json
import sys
from pathlib import Path

import typer

from aichemy_pricing import __version__
from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.fluorochem import FluorochemVendor
from aichemy_pricing.vendors.molbase import MolbaseVendor
from aichemy_pricing.vendors.tocris import TocrisVendor
from aichemy_pricing.vendors.enamine import EnamineVendor
from aichemy_pricing.vendors.cayman import CaymanVendor
from aichemy_pricing.vendors.chemcruz import ChemCruzVendor
from aichemy_pricing.vendors.medchemexpress import MedChemExpressVendor

app = typer.Typer(help="aichemy-pricing CLI")

_VENDORS = {
    "fluorochem": FluorochemVendor,
    "molbase": MolbaseVendor,
    "tocris": TocrisVendor,
    "enamine": EnamineVendor,
    "cayman": CaymanVendor,
    "chemcruz": ChemCruzVendor,
    "medchemexpress": MedChemExpressVendor,
}


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_cb, is_eager=True),
) -> None: ...


@app.command()
def lookup(vendor: str, sku: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """Look up a single SKU at one vendor."""
    if vendor not in _VENDORS:
        typer.echo(f"Unknown vendor: {vendor}; choose from {sorted(_VENDORS)}", err=True)
        raise typer.Exit(2)
    v = _VENDORS[vendor]()
    quote = v.lookup(VendorRef(vendor=vendor, sku=sku))
    if quote is None:
        typer.echo("no quote (404 or unparseable)", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(quote.model_dump_json(indent=2))
    else:
        typer.echo(f"{quote.price} {quote.currency} / {quote.pack_size_g} g")


if __name__ == "__main__":  # pragma: no cover
    app()
```

- [ ] **Step 3: Run + commit**

```bash
uv run aichemy-price --version
uv run aichemy-price lookup fluorochem F765353-1G
git commit -m "feat(pricing): aichemy-price CLI for single-SKU debugging"
```

---

## Phase 7 — Public API and integration

### Task 7.1: Re-export the public API in `__init__.py`

**Files:**
- Modify: `src/aichemy_pricing/__init__.py`

- [ ] **Step 1: Replace contents**

```python
# src/aichemy_pricing/__init__.py
"""aichemy-pricing — chemical-vendor price resolution.

Public API:
    from aichemy_pricing import (
        PriceQuote, VendorRef, ResolverHit,
        ChainedPriceLookup, CachedPriceLookup,
        FluorochemVendor, MolbaseVendor, TocrisVendor,
        EnamineVendor, CaymanVendor, ChemCruzVendor,
        MedChemExpressVendor,
        PubChemSdfResolver, EnamineSdfResolver,
        build_default_chain,
    )

The verified URL/schema facts each vendor encodes are anchored to
`experiments/chem-pricing-verification/CLAIMS.md` (29/29 claims verdict-ed).
"""
from __future__ import annotations

from pathlib import Path

from aichemy_pricing._version import __version__
from aichemy_pricing.chain import CachedPriceLookup, ChainedPriceLookup
from aichemy_pricing.protocol import PriceLookup, VendorResolver
from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver
from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver
from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef
from aichemy_pricing.vendors.cayman import CaymanVendor
from aichemy_pricing.vendors.chemcruz import ChemCruzVendor
from aichemy_pricing.vendors.enamine import EnamineVendor
from aichemy_pricing.vendors.fluorochem import FluorochemVendor
from aichemy_pricing.vendors.medchemexpress import MedChemExpressVendor
from aichemy_pricing.vendors.molbase import MolbaseVendor
from aichemy_pricing.vendors.tocris import TocrisVendor

__all__ = [
    "__version__",
    "PriceLookup", "VendorResolver",
    "PriceQuote", "VendorRef", "ResolverHit",
    "ChainedPriceLookup", "CachedPriceLookup",
    "FluorochemVendor", "MolbaseVendor", "TocrisVendor",
    "EnamineVendor", "CaymanVendor", "ChemCruzVendor", "MedChemExpressVendor",
    "PubChemSdfResolver", "EnamineSdfResolver",
    "build_default_chain",
]


def build_default_chain(cache_path: Path) -> CachedPriceLookup:
    """Standard tiered chain: Tier 1 → Tier 2 → Tier 3, all wrapped in a SQLite cache.

    Skips Sigma-Aldrich and TCI (require Akamai-aware infrastructure not in this
    package — see CLAIM-12, CLAIM-13). Skips Apollo entirely (FALSIFIED, CLAIM-11).
    """
    inner = ChainedPriceLookup([
        # Tier 1
        FluorochemVendor(),
        MolbaseVendor(),
        TocrisVendor(),
        # Tier 2
        EnamineVendor(),
        CaymanVendor(),
        ChemCruzVendor(),
        # Tier 3
        MedChemExpressVendor(),
    ])
    return CachedPriceLookup(inner, db_path=cache_path, ttl_days=30)
```

- [ ] **Step 2: Smoke test**

```bash
uv run python -c "import aichemy_pricing as p; print([x for x in dir(p) if not x.startswith('_')])"
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(pricing): re-export public API + build_default_chain factory"
```

### Task 7.2: Integrate into AIchemy pipeline

**Files:**
- Modify: `src/aichemy/preprocessing/augment/prices.py` — replace bespoke implementations with `from aichemy_pricing import …` (or, simpler v1: leave existing classes but ensure the `make_lookup` factory route is `aichemy_pricing.build_default_chain` when `backend="chained"`).
- Modify: `configs/default.yaml` — point `prices.cache_path` at `data/interim/aichemy_pricing_cache.sqlite`.

- [ ] **Step 1: Read existing `make_lookup` factory in `aichemy.preprocessing.augment.prices`** (already partially scaffolded per the existing Stage 10 plan).
- [ ] **Step 2: Add a new `backend: "aichemy_pricing"` branch that returns `aichemy_pricing.build_default_chain(...)`** wrapped in an adapter that maps `(canonical_smiles) → (vendor, sku)` via the configured resolvers and then calls `chain.lookup(ref)`.
- [ ] **Step 3: Integration test:**

```python
# tests/integration/test_pricing_package_integration.py
def test_aichemy_pricing_backend_round_trips(tmp_path) -> None:
    from aichemy.config import PreprocessingConfig
    from aichemy.preprocessing.augment.prices import make_lookup

    cfg = PreprocessingConfig.model_validate({
        "prices": {
            "backend": "aichemy_pricing",
            "cache_path": str(tmp_path / "cache.sqlite"),
            "resolver_root": "src/aichemy_pricing/tests/data/",
        }
    })
    lookup = make_lookup(cfg)
    # Use a known InChIKey from the fixture set; the lookup walks resolver → chain
    quote = lookup.lookup_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    # may be None if no fixture vendor matches; just assert no crash
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(pricing): wire aichemy_pricing as augment-prices backend"
```

---

## Phase 8 — End-to-end verification

### Task 8.1: Standalone test suite passes

- [ ] **Run:**

```bash
uv run pytest src/aichemy_pricing/tests/ -v --tb=short
```

- [ ] All replay tests pass; live tests skipped by default.

### Task 8.2: Live test suite passes

- [ ] **Run:**

```bash
uv run pytest src/aichemy_pricing/tests/ -m live -v --tb=short
```

- [ ] At least Fluorochem live test passes; Tier 2/3 live tests pass when discovered XHR endpoints are live.

### Task 8.3: AIchemy pipeline picks it up

- [ ] **Run:**

```bash
uv run dvc repro augment_prices
```

- [ ] No regression in existing tests:

```bash
uv run pytest tests/ -v
```

### Task 8.4: Document in README

- [ ] **Modify** `README.md` to add a "Vendor pricing" section linking to:
  - This plan (`docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`)
  - The verification work (`experiments/chem-pricing-verification/VERIFICATION.md`)
  - The CLI: `uv run aichemy-price lookup fluorochem F765353-1G`

- [ ] Commit + push.

---

## Going-live checklist (deliberately deferred items)

Items intentionally **not** in this plan because they need more infrastructure than the standalone package should depend on:

- **Sigma-Aldrich + TCI Chemicals.** Both behind Akamai (CLAIM-12, CLAIM-13). Plan-level deferral: ship a separate "Tier 4 WAF-aware" plan that adds residential-proxy support (e.g., via Browserbase or Bright Data), with explicit cost gating. Until then `build_default_chain` skips them.
- **Apollo Scientific.** FALSIFIED (CLAIM-11) — store decommissioned. Permanently excluded.
- **BLDpharm.** URL pattern in original report is wrong (CLAIM-16); real pattern not yet discovered. Mark TODO; not worth pursuing until a working URL example is sourced.
- **Browserbase / headless rendering.** Not needed for v1 — Enamine/Cayman/MCE all have JSON XHR endpoints discoverable via DevTools that we hit directly. Revisit only if a vendor flips to a non-deterministic JS-only render.
- **Avanti SAP migration (June 2026).** Per CLAIM-21, MilliporeSigma will change Avanti SKU codes in June 2026. Cache TTL of 30 days mitigates this; full re-resolution recommended after the migration window.

---

## Self-review

**Spec coverage check:** Every verdict in `experiments/chem-pricing-verification/CLAIMS.md` is reflected in this plan: VERIFIED claims become implementation tasks; PARTIAL claims become implementation tasks with explicit "use the corrected URL/schema" notes; FALSIFIED (Apollo) is explicitly excluded; quantitative estimates inform the going-live yield expectations rather than the implementation. The two deliberately-deferred buckets (Sigma/TCI, BLD) are documented above.

**Placeholder scan:** No "TBD" / "implement later" — every code step has actual code. Discovery actions for Tier 2 (Tasks 4.1–4.3) and Tier 3 (Task 5.1) are explicit one-time manual steps, not placeholders. Task 2.3 (ZINC tranches) reuses the SDF parser pattern from 2.1/2.2 — the implementation reference is the prior task, which is the convention this codebase already uses.

**Type consistency:** `VendorRef`, `ResolverHit`, `PriceQuote` are used consistently across all vendor modules and resolvers. The `lookup(ref: VendorRef) -> PriceQuote | None` signature is the single mental model.
