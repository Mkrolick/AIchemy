# Sub-Plan A: `aichemy-pricing` — Package Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Parent plan:** `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`
> **Verification source:** `experiments/chem-pricing-verification/CLAIMS.md` (29/29 claims verdict-ed)
> **Depends on:** nothing — this is the foundation
> **Delivers (interfaces consumed by sub-plans B–E):**
> - `aichemy_pricing.types`: `PriceQuote`, `VendorRef`, `ResolverHit`
> - `aichemy_pricing.protocol`: `PriceLookup`, `VendorResolver`
> - `aichemy_pricing.chain`: `ChainedPriceLookup`, `CachedPriceLookup`
> - `aichemy_pricing.ratelimit.TokenBucket`
> - `aichemy_pricing.http`: `make_plain_client()`, `make_cf_client()`
> - Console-script entry point `aichemy-price` (stub; populated in sub-plan E)
> - Standalone pytest suite `pytest src/aichemy_pricing/tests/` runs without aichemy.* imports

**Goal:** Bootstrap a standalone Python package `aichemy_pricing` (sibling to `aichemy`) with its own pyproject extra, console script, and test suite, plus the core types/protocols/chain/cache/HTTP/rate-limit primitives that all later sub-plans build on.

**Architecture:** `src/aichemy_pricing/` lives next to `src/aichemy/`. Zero imports from `aichemy.*` — the dependency arrow only goes the other way. The package is installable on its own with `uv sync --extra pricing`. Tests live under `src/aichemy_pricing/tests/` and are discovered alongside the package code so `pytest src/aichemy_pricing/tests/` works without the rest of AIchemy installed.

**Tech Stack:** Python 3.11+, `httpx`, `curl_cffi` (declared but not exercised until sub-plan D), `pydantic` v2, `typer`, `pytest` + `pytest-httpx`. `uv` build/sync.

**Pre-commit note (applies to every `git commit` step in sub-plans A–E):** the repo's `.pre-commit-config.yaml` runs `ruff` (auto-fix) and `ruff format` on staged files. If the hooks reformat your changes, `git commit` will refuse the commit and leave the working tree dirty. Re-stage the auto-fixed files and retry: `git add <files> && git commit ...`. Do NOT pass `--no-verify`. If a `ruff` rule legitimately disagrees with what a sub-plan asks you to write, fix the rule's complaint — don't override the hook.

---

## File Structure

```
pyproject.toml                                    # MODIFIED — add `pricing` extra + console script
src/aichemy_pricing/
├── __init__.py                                   # CREATE — re-exports (populated by E)
├── _version.py                                   # CREATE
├── py.typed                                      # CREATE — empty marker
├── types.py                                      # CREATE
├── protocol.py                                   # CREATE
├── ratelimit.py                                  # CREATE
├── chain.py                                      # CREATE
├── http.py                                       # CREATE
└── tests/
    ├── __init__.py                               # CREATE — empty
    ├── conftest.py                               # CREATE — `live` marker, fixture_dir
    ├── data/.gitkeep                             # CREATE
    ├── test_types.py                             # CREATE (3 tests)
    ├── test_ratelimit.py                         # CREATE (1 test)
    ├── test_chain.py                             # CREATE (2 tests)
    ├── test_cache.py                             # CREATE (2 tests)
    └── test_http.py                              # CREATE (2 tests)
```

---

## Task A0: `pyproject.toml` — `pricing` extra + console script

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current `[project.optional-dependencies]` and `[project.scripts]` blocks**

```bash
grep -n -A 30 '\[project.optional-dependencies\]\|\[project.scripts\]' pyproject.toml
```

- [ ] **Step 2: Add `pricing` extra**

In `[project.optional-dependencies]`:

```toml
pricing = [
  "httpx>=0.27",
  "curl_cffi>=0.7",
  "polars>=1.0",
  "pydantic>=2.6",
  "typer>=0.12",
  "rdkit>=2024.3",
]
```

- [ ] **Step 3: Add console script**

In `[project.scripts]`:

```toml
aichemy-price = "aichemy_pricing.cli:app"
```

- [ ] **Step 4: Verify dev tooling (no edit required)**

The repo already declares dev tooling under PEP 735 `[dependency-groups]` (NOT `[project.optional-dependencies]`):

```toml
[dependency-groups]
dev = ["pytest>=8.0", "pytest-cov", "pytest-httpx>=0.36", "ruff>=0.4", "mypy>=1.10",
       "pre-commit", "nbstripout", "dvc>=3.0"]
```

`pytest-httpx>=0.36` is already present and is **newer** than what this sub-plan needs — do NOT add a parallel `[project.optional-dependencies] dev`. That would create two competing `dev` definitions, drop pre-commit/nbstripout/dvc from the synced env, and downgrade pytest-httpx.

- [ ] **Step 5: Sync**

```bash
uv sync --extra pricing --group dev
```

Note: `--group dev` (PEP 735 group), not `--extra dev`. Expected: clean sync. `aichemy-price` will fail with ImportError because `cli.py` is empty — that is correct for now.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build(pricing): add pricing extra and aichemy-price console script"
```

---

## Task A1: Package skeleton + test scaffolding

**Files:**
- Create: `src/aichemy_pricing/__init__.py`
- Create: `src/aichemy_pricing/_version.py`
- Create: `src/aichemy_pricing/py.typed` (empty)
- Create: `src/aichemy_pricing/tests/__init__.py` (empty)
- Create: `src/aichemy_pricing/tests/conftest.py`
- Create: `src/aichemy_pricing/tests/data/.gitkeep`

- [ ] **Step 1: `_version.py`**

```python
# src/aichemy_pricing/_version.py
__version__ = "0.1.0"
```

- [ ] **Step 2: Stub `__init__.py`** (will be re-exported in sub-plan E)

```python
# src/aichemy_pricing/__init__.py
"""aichemy-pricing — chemical-vendor price resolution.

Public API is populated incrementally across sub-plans A–E. See
`docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md` for the parent plan.
"""
from aichemy_pricing._version import __version__

__all__ = ["__version__"]
```

- [ ] **Step 3: Empty marker files**

```bash
mkdir -p src/aichemy_pricing/tests/data
: > src/aichemy_pricing/py.typed
: > src/aichemy_pricing/tests/__init__.py
: > src/aichemy_pricing/tests/data/.gitkeep
```

- [ ] **Step 4: `conftest.py` — `live` marker + `fixture_dir`**

```python
# src/aichemy_pricing/tests/conftest.py
"""Standalone test suite for aichemy_pricing.

Runs without aichemy.* imports.

Live network tests are marked with @pytest.mark.live and skipped by default.
Run live-only with:  pytest src/aichemy_pricing/tests -m live
"""
from __future__ import annotations

import pathlib
import re

import pytest

DATA = pathlib.Path(__file__).parent / "data"

# `-m live` (or `-m "live or X"`) opts the user IN to live tests.
# `-m "not live"` (or default no `-m`) opts them OUT.
# The negative-lookbehind regex requires the literal 4 chars "not " before "live"
# to recognize the OPT-OUT case — but pytest accepts equivalent forms like
# "not (live)", "not(live)", or "not  live" (double space) that defeat the
# fixed-width lookbehind. We normalize the markexpr first: strip parentheses
# and collapse whitespace, so all of those canonicalize to "not live" before
# the regex runs and route correctly through the lookbehind.
_LIVE_OPT_IN = re.compile(r"(?<!not )\blive\b")


def _normalize_markexpr(raw: str) -> str:
    # Replace parens with spaces; pytest's marker grammar uses parens only for
    # grouping, never as part of a marker name, so this is safe.
    no_parens = raw.replace("(", " ").replace(")", " ")
    # Collapse runs of whitespace to a single space.
    return re.sub(r"\s+", " ", no_parens).strip()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: hits real network; skipped by default")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    markexpr = _normalize_markexpr(config.option.markexpr or "")
    if _LIVE_OPT_IN.search(markexpr):
        return  # caller asked for live; don't filter
    skip_live = pytest.mark.skip(reason="live network test; pass -m live to enable")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def fixture_dir() -> pathlib.Path:
    return DATA
```

- [ ] **Step 5: Verify importable + tests can be collected**

```bash
uv run python -c "import aichemy_pricing; print(aichemy_pricing.__version__)"
uv run pytest src/aichemy_pricing/tests/ --collect-only -q
```

Expected: `0.1.0` printed; pytest reports "no tests ran" (no test files yet).

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/
git commit -m "feat(pricing): bootstrap aichemy-pricing package skeleton + test harness"
```

---

## Task A2: `types.py` — `PriceQuote`, `VendorRef`, `ResolverHit`

**Files:**
- Create: `src/aichemy_pricing/types.py`
- Create: `src/aichemy_pricing/tests/test_types.py`

- [ ] **Step 1: Failing test**

```python
# src/aichemy_pricing/tests/test_types.py
"""Unit tests for the data types. No I/O; pure pydantic."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef


def test_price_quote_normalizes_currency_uppercase() -> None:
    q = PriceQuote(
        vendor="fluorochem",
        sku="F765353-1G",
        price=230.0,
        currency="gbp",   # lowercase input
        pack_size_g=1.0,
        fetched_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )
    assert q.currency == "GBP"
    assert q.price_per_gram_native == 230.0


def test_price_quote_rejects_non_positive_price() -> None:
    base = dict(
        vendor="x", sku="y", currency="USD", pack_size_g=1.0,
        fetched_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError):
        PriceQuote(price=-1.0, **base)
    with pytest.raises(ValidationError):
        PriceQuote(price=0.0, **base)


def test_price_quote_rejects_non_positive_pack_size() -> None:
    with pytest.raises(ValidationError):
        PriceQuote(
            vendor="x", sku="y", price=1.0, currency="USD", pack_size_g=0.0,
            fetched_at=datetime.now(timezone.utc),
        )


def test_resolver_hit_carries_inchikey_vendor_sku() -> None:
    h = ResolverHit(
        inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        vendor="enamine",
        sku="EN300-7605608",
    )
    assert h.vendor == "enamine"
    assert h.sku == "EN300-7605608"


def test_resolver_hit_rejects_short_inchikey() -> None:
    with pytest.raises(ValidationError):
        ResolverHit(inchikey="too-short", vendor="x", sku="y")


def test_vendor_ref_does_not_require_url() -> None:
    r = VendorRef(vendor="fluorochem", sku="F765353-1G")
    assert r.canonical_url is None


def test_price_quote_per_gram_with_pack_size() -> None:
    q = PriceQuote(
        vendor="x", sku="y", price=300.0, currency="USD", pack_size_g=5.0,
        fetched_at=datetime.now(timezone.utc),
    )
    assert q.price_per_gram_native == 60.0
```

- [ ] **Step 2: Run; ImportError**

```bash
uv run pytest src/aichemy_pricing/tests/test_types.py -v
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/types.py
"""Pure-data types — no behavior, no I/O."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator

Currency = Literal["USD", "GBP", "EUR", "CNY", "JPY", "SEK"]


class VendorRef(BaseModel):
    """Pointer from an InChIKey to a vendor's catalog SKU."""
    model_config = ConfigDict(frozen=True)

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
    raw: dict[str, Any] | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v

    @property
    def price_per_gram_native(self) -> float:
        return self.price / self.pack_size_g
```

- [ ] **Step 4: Run; pass**

```bash
uv run pytest src/aichemy_pricing/tests/test_types.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/types.py src/aichemy_pricing/tests/test_types.py
git commit -m "feat(pricing): types — PriceQuote, VendorRef, ResolverHit"
```

---

## Task A3: `protocol.py` — `PriceLookup` and `VendorResolver`

**Files:**
- Create: `src/aichemy_pricing/protocol.py`

- [ ] **Step 1: Implement (no separate test — exercised via chain tests in A5)**

```python
# src/aichemy_pricing/protocol.py
"""Structural protocols. Implementations live in `vendors/` and `resolvers/`."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef


@runtime_checkable
class PriceLookup(Protocol):
    """Maps a `VendorRef` to a `PriceQuote`, or None if unknown."""
    name: str
    def lookup(self, ref: VendorRef) -> PriceQuote | None: ...


@runtime_checkable
class VendorResolver(Protocol):
    """Maps an InChIKey to zero-or-more vendor SKUs (offline JOIN, no network)."""
    name: str
    def resolve(self, inchikey: str) -> list[ResolverHit]: ...
```

- [ ] **Step 2: Type-check**

```bash
uv run mypy src/aichemy_pricing/protocol.py
```

Expected: Success.

- [ ] **Step 3: Commit**

```bash
git add src/aichemy_pricing/protocol.py
git commit -m "feat(pricing): PriceLookup and VendorResolver protocols"
```

---

## Task A4: `ratelimit.py` — token bucket

**Files:**
- Create: `src/aichemy_pricing/ratelimit.py`
- Create: `src/aichemy_pricing/tests/test_ratelimit.py`

- [ ] **Step 1: Failing test**

```python
# src/aichemy_pricing/tests/test_ratelimit.py
"""Unit tests for TokenBucket. Uses small rate to keep test wall-time ≤2s."""
from __future__ import annotations

import time

import pytest

from aichemy_pricing.ratelimit import TokenBucket


def test_token_bucket_initial_tokens_do_not_block() -> None:
    bucket = TokenBucket(rate_per_sec=2.0, capacity=2)
    t0 = time.monotonic()
    bucket.acquire()
    bucket.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.1


def test_token_bucket_blocks_after_exhaustion() -> None:
    bucket = TokenBucket(rate_per_sec=4.0, capacity=2)  # 0.25s per token after exhaustion
    t0 = time.monotonic()
    bucket.acquire(); bucket.acquire()  # consume capacity
    bucket.acquire()                    # third should block ~0.25s
    elapsed = time.monotonic() - t0
    assert 0.2 < elapsed < 1.0


def test_token_bucket_rejects_invalid_acquire() -> None:
    bucket = TokenBucket(rate_per_sec=1.0, capacity=1)
    with pytest.raises(ValueError):
        bucket.acquire(0)
    with pytest.raises(ValueError):
        bucket.acquire(-1)
```

- [ ] **Step 2: Run; ImportError**

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/ratelimit.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    """Simple thread-safe token bucket. Use one per upstream rate-limited host."""
    rate_per_sec: float
    capacity: int

    def __post_init__(self) -> None:
        if self.rate_per_sec <= 0 or self.capacity <= 0:
            raise ValueError("rate_per_sec and capacity must be positive")
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, n: int = 1) -> None:
        if n <= 0:
            raise ValueError("acquire(n) requires n >= 1")
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

- [ ] **Step 4: Run; pass (3 tests)**

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/ratelimit.py src/aichemy_pricing/tests/test_ratelimit.py
git commit -m "feat(pricing): TokenBucket rate limiter"
```

---

## Task A5: `chain.py` — `ChainedPriceLookup` + `CachedPriceLookup`

**Files:**
- Create: `src/aichemy_pricing/chain.py`
- Create: `src/aichemy_pricing/tests/test_chain.py`
- Create: `src/aichemy_pricing/tests/test_cache.py`

- [ ] **Step 1: Failing chain tests**

```python
# src/aichemy_pricing/tests/test_chain.py
"""Unit tests for ChainedPriceLookup."""
from __future__ import annotations

from datetime import datetime, timezone

from aichemy_pricing.chain import ChainedPriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef


def _q(vendor: str = "x") -> PriceQuote:
    return PriceQuote(
        vendor=vendor, sku="s", price=1.0, currency="USD", pack_size_g=1.0,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class _Stub:
    def __init__(self, name: str, ret: PriceQuote | None) -> None:
        self.name = name
        self.ret = ret
        self.calls = 0
    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return self.ret


def test_chain_returns_first_hit_and_short_circuits() -> None:
    a = _Stub("a", None)
    b = _Stub("b", _q("b"))
    c = _Stub("c", _q("c"))
    chain = ChainedPriceLookup([a, b, c])
    res = chain.lookup(VendorRef(vendor="any", sku="any"))
    assert res is not None and res.vendor == "b"
    assert (a.calls, b.calls, c.calls) == (1, 1, 0)


def test_chain_returns_none_when_all_miss() -> None:
    a = _Stub("a", None)
    b = _Stub("b", None)
    chain = ChainedPriceLookup([a, b])
    assert chain.lookup(VendorRef(vendor="x", sku="y")) is None
    assert (a.calls, b.calls) == (1, 1)


def test_chain_with_empty_members_returns_none() -> None:
    chain = ChainedPriceLookup([])
    assert chain.lookup(VendorRef(vendor="x", sku="y")) is None


def test_chain_swallows_per_member_exceptions_and_continues() -> None:
    """Mirrors the existing aichemy.preprocessing.augment.prices.ChainedPriceLookup
    contract: 'one source failing shouldn't kill the chain'. A transient
    httpx.ConnectError or similar from any vendor must not abort the dict-comp
    in `augment_prices` — the chain logs it and falls through to the next
    member."""
    class _Boom:
        name = "boom"
        calls = 0
        def lookup(self, ref):
            self.__class__.calls += 1
            raise RuntimeError("simulated transient failure")

    boom = _Boom()
    survivor = _Stub("survivor", _q("survivor"))
    chain = ChainedPriceLookup([boom, survivor])
    out = chain.lookup(VendorRef(vendor="x", sku="y"))
    assert out is not None and out.vendor == "survivor"
    assert _Boom.calls == 1 and survivor.calls == 1
```

- [ ] **Step 2: Failing cache tests**

```python
# src/aichemy_pricing/tests/test_cache.py
"""Unit tests for CachedPriceLookup (SQLite-backed)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aichemy_pricing.chain import CachedPriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef


class _HitOnce:
    name = "hit-once"
    def __init__(self) -> None:
        self.calls = 0
    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return PriceQuote(
            vendor=ref.vendor, sku=ref.sku, price=1.0, currency="USD", pack_size_g=1.0,
            fetched_at=datetime.now(timezone.utc),
        )


class _AlwaysMiss:
    name = "miss"
    def __init__(self) -> None:
        self.calls = 0
    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return None


def test_cache_only_calls_inner_once_per_ref(tmp_path) -> None:
    inner = _HitOnce()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    cache.lookup(ref); cache.lookup(ref); cache.lookup(ref)
    assert inner.calls == 1


def test_cache_caches_misses(tmp_path) -> None:
    inner = _AlwaysMiss()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    assert cache.lookup(ref) is None
    assert cache.lookup(ref) is None
    assert inner.calls == 1


def test_cache_ttl_expiry_re_queries_inner(tmp_path) -> None:
    inner = _HitOnce()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    cache.lookup(ref)
    # Manually rewind the cached fetched_at by 60 days
    past = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    cache._conn.execute("UPDATE quote_cache SET fetched_at = ?", (past,))
    cache.lookup(ref)
    assert inner.calls == 2


def test_cache_round_trips_pricequote_fields(tmp_path) -> None:
    inner = _HitOnce()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="vx", sku="sx")
    a = cache.lookup(ref)
    b = cache.lookup(ref)  # served from cache
    assert a is not None and b is not None
    assert (b.vendor, b.sku, b.price, b.currency) == (a.vendor, a.sku, a.price, a.currency)
```

- [ ] **Step 3: Run both; ImportError**

- [ ] **Step 4: Implement `chain.py`**

```python
# src/aichemy_pricing/chain.py
"""ChainedPriceLookup falls through; CachedPriceLookup memoizes via SQLite."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aichemy_pricing.protocol import PriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef

log = logging.getLogger(__name__)


class ChainedPriceLookup:
    """Tries members in order; returns first non-None or None if all miss.

    Mirrors the contract of `aichemy.preprocessing.augment.prices.ChainedPriceLookup`:
    one member raising must NOT abort the whole chain. A transient
    `httpx.ConnectError` (or similar) from any vendor is logged and skipped;
    the chain continues to the next member. Without this guard, a single
    network blip aborts `augment_prices`' dict-comp over all input SMILES.
    """
    name = "chain"

    def __init__(self, members: list[PriceLookup]) -> None:
        self.members = list(members)

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        for m in self.members:
            try:
                hit = m.lookup(ref)
            except Exception as exc:  # one source failing shouldn't kill the chain
                log.warning(
                    "Price lookup backend %r raised on %s/%s: %s",
                    getattr(m, "name", type(m).__name__),
                    ref.vendor, ref.sku, exc,
                )
                continue
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
CREATE INDEX IF NOT EXISTS idx_quote_cache_fetched ON quote_cache(fetched_at);
"""


class CachedPriceLookup:
    """Wraps an inner PriceLookup with a SQLite cache.

    Caches BOTH hits and misses (None), so a known-missing SKU isn't re-fetched.
    Entries older than `ttl_days` are treated as cache misses and re-fetched.
    """
    name = "cache"

    def __init__(self, inner: PriceLookup, db_path: Path | str, ttl_days: int = 30) -> None:
        self.inner = inner
        self.db_path = Path(db_path)
        self.ttl = timedelta(days=ttl_days)
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.executescript(_SCHEMA)

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        row = self._conn.execute(
            "SELECT quote_json, fetched_at FROM quote_cache WHERE vendor=? AND sku=?",
            (ref.vendor, ref.sku),
        ).fetchone()
        if row is not None:
            quote_json, fetched_at_iso = row
            fetched = datetime.fromisoformat(fetched_at_iso)
            if datetime.now(timezone.utc) - fetched < self.ttl:
                return None if quote_json is None else PriceQuote.model_validate_json(quote_json)
        result = self.inner.lookup(ref)
        self._conn.execute(
            "INSERT OR REPLACE INTO quote_cache(vendor, sku, quote_json, fetched_at) VALUES (?, ?, ?, ?)",
            (
                ref.vendor,
                ref.sku,
                result.model_dump_json() if result else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return result
```

- [ ] **Step 5: Run; pass**

```bash
uv run pytest src/aichemy_pricing/tests/test_chain.py src/aichemy_pricing/tests/test_cache.py -v
```

Expected: 3 chain + 4 cache = 7 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/chain.py src/aichemy_pricing/tests/test_chain.py src/aichemy_pricing/tests/test_cache.py
git commit -m "feat(pricing): ChainedPriceLookup + SQLite-backed CachedPriceLookup"
```

---

## Task A6: `http.py` — shared client factories

**Files:**
- Create: `src/aichemy_pricing/http.py`
- Create: `src/aichemy_pricing/tests/test_http.py`

- [ ] **Step 1: Failing test**

```python
# src/aichemy_pricing/tests/test_http.py
"""Unit tests for client factories."""
from __future__ import annotations

import httpx

from aichemy_pricing.http import CHROME_UA, make_cf_client, make_plain_client


def test_plain_client_uses_browser_ua() -> None:
    c = make_plain_client()
    try:
        assert c.headers["User-Agent"] == CHROME_UA
        assert "Accept" in c.headers
    finally:
        c.close()


def test_plain_client_follows_redirects() -> None:
    c = make_plain_client()
    try:
        assert c.follow_redirects is True
    finally:
        c.close()


def test_cf_client_returns_object_with_get(monkeypatch) -> None:
    """We don't actually make a network call here; just verify the factory hands
    back something with the curl_cffi.requests.Session shape."""
    c = make_cf_client()
    assert hasattr(c, "get") and callable(c.get)
```

- [ ] **Step 2: Implement**

```python
# src/aichemy_pricing/http.py
"""Shared HTTP client factories.

Two flavours:
 - `make_plain_client()` — vanilla httpx with a desktop Chrome User-Agent.
   Used for Tier 1 (Fluorochem JSON, Molbase, Tocris) and Tier 2 (Enamine,
   Cayman, ChemCruz) where Cloudflare/Akamai are absent or pass with a UA.
 - `make_cf_client()` — curl_cffi impersonating Chrome 124. Used for Tier 3
   (MedChemExpress) where Cloudflare requires a real-browser TLS fingerprint.

Per CLAIM-15: MCE 403s any client without a real-browser TLS fingerprint,
even with the right User-Agent header.
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


def make_cf_client():  # type: ignore[no-untyped-def]  # curl_cffi has no public type stubs
    """Returns a curl_cffi Session impersonating Chrome 124's TLS fingerprint."""
    from curl_cffi import requests as cf_requests
    return cf_requests.Session(impersonate="chrome124")
```

- [ ] **Step 3: Run; pass (3 tests)**

- [ ] **Step 4: Commit**

```bash
git add src/aichemy_pricing/http.py src/aichemy_pricing/tests/test_http.py
git commit -m "feat(pricing): plain httpx + curl_cffi client factories"
```

---

## Task A7: `_capture.py` — shared fixture-capture helper

**Why:** Sub-plans B, C, D each instruct an engineer to download a live response and save it to `tests/data/`. Without validation, a 403/redirect/CF-challenge response gets written and silently poisons the test suite (a fixture full of "Just a moment..." passes JSON-shape tests for the wrong reason). This task gives every vendor capture step a single validated entry point.

**Files:**
- Create: `src/aichemy_pricing/tests/data/_capture.py`
- (No tests — this is a developer one-shot script, not part of the runtime; exercised manually during fixture capture.)

- [ ] **Step 1: Implement**

```python
# src/aichemy_pricing/tests/data/_capture.py
"""Shared fixture-capture validator. Writes the response body to disk only if
all sanity checks pass — a corrupted/blocked response cannot poison the test
suite.

Usage (typical, plain HTTP):
    uv run python -m aichemy_pricing.tests.data._capture \\
        --url https://www.tocris.com/products/jw-642_4906 \\
        --out  src/aichemy_pricing/tests/data/tocris_jw642.html \\
        --min-size 5000 --required-marker 'JW 642'

Usage (Cloudflare-aware, via curl_cffi):
    uv run python -m aichemy_pricing.tests.data._capture \\
        --url https://www.medchemexpress.com/acetyl-coenzyme-a.html \\
        --out  src/aichemy_pricing/tests/data/mce_acetyl_coa.html \\
        --client cf --impersonate chrome124 \\
        --min-size 5000 --required-marker 'Acetyl'
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Markers that mean we got a Cloudflare/Akamai challenge instead of real HTML.
BAD_MARKERS = (
    "Just a moment...",
    "cf-browser-verification",
    "challenge-platform",
    "Checking your browser",
    "Enable JavaScript and cookies",
    "Access denied",
    "Reference #18.",            # Akamai reference-id template
)


def _fetch_plain(url: str) -> tuple[int, bytes]:
    import httpx
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as c:
        r = c.get(url)
        return r.status_code, r.content


def _fetch_cf(url: str, impersonate: str) -> tuple[int, bytes]:
    from curl_cffi import requests as cf_requests
    sess = cf_requests.Session(impersonate=impersonate)
    r = sess.get(url)
    return r.status_code, r.content


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Capture a fixture for vendor tests.")
    p.add_argument("--url", required=True)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--client", choices=["plain", "cf"], default="plain")
    p.add_argument("--impersonate", default="chrome124", help="curl_cffi impersonate token (cf only)")
    p.add_argument("--min-size", type=int, default=2_000, help="reject body smaller than this many bytes")
    p.add_argument(
        "--required-marker", action="append", default=[],
        help="substring that MUST appear in the body (repeatable)",
    )
    args = p.parse_args(argv)

    if args.client == "cf":
        status, body = _fetch_cf(args.url, args.impersonate)
    else:
        status, body = _fetch_plain(args.url)

    text = body.decode("utf-8", "replace")
    problems: list[str] = []
    if status != 200:
        problems.append(f"status_code={status} (expected 200)")
    if len(body) < args.min_size:
        problems.append(f"body_len={len(body)} (expected ≥ {args.min_size})")
    bad = [m for m in BAD_MARKERS if m in text]
    if bad:
        problems.append(f"challenge marker(s) present: {bad}")
    missing = [m for m in args.required_marker if m not in text]
    if missing:
        problems.append(f"required marker(s) missing: {missing}")

    if problems:
        print(f"FIXTURE CAPTURE FAILED for {args.url}:", file=sys.stderr)
        for x in problems:
            print(f"  - {x}", file=sys.stderr)
        print(
            "\nDo not retry by relaxing the checks; investigate why the vendor "
            "didn't return its real HTML/JSON (residential IP? CF token rotation? "
            "redirect change?).",
            file=sys.stderr,
        )
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(body)
    print(f"OK: wrote {len(body)} bytes to {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test with a known-good URL**

```bash
uv run python -m aichemy_pricing.tests.data._capture \
  --url https://fluorochemcouk.blob.core.windows.net/pricing/F765353.json \
  --out /tmp/_capture_smoke.json \
  --min-size 100 --required-marker 'Base Price'
```

Expected: prints `OK: wrote NNNN bytes to /tmp/_capture_smoke.json`.

- [ ] **Step 3: Commit**

```bash
git add src/aichemy_pricing/tests/data/_capture.py
git commit -m "feat(pricing): shared fixture-capture validator (_capture.py)"
```

---

## Unit Tests Summary (Sub-Plan A)

| Test file | Test count | Notes |
|---|---:|---|
| `test_types.py` | 7 | Currency normalization, positivity validators, InChIKey length, per-gram math |
| `test_ratelimit.py` | 3 | No-block under capacity; blocks after exhaustion; rejects invalid args |
| `test_chain.py` | 4 | First-hit short-circuit; all-miss → None; empty-members → None; **per-member exception swallowed + continues** |
| `test_cache.py` | 4 | Inner called once per ref; cache misses; TTL expiry; field round-trip |
| `test_http.py` | 3 | Browser UA on plain client; redirects; curl_cffi factory shape |
| **Total** | **21** | All offline; no `live` markers in this sub-plan. |

**All-tests command:**
```bash
uv run pytest src/aichemy_pricing/tests/ -v
```
Expected: 20 passed in <3s.

**Type-check:**
```bash
uv run mypy src/aichemy_pricing/
```
Expected: Success.

---

## Self-review

**Spec coverage:** Every interface promised in the header (`PriceQuote`, `VendorRef`, `ResolverHit`, `PriceLookup`, `VendorResolver`, `ChainedPriceLookup`, `CachedPriceLookup`, `TokenBucket`, `make_plain_client`, `make_cf_client`, `aichemy-price` script entry) has at least one task that creates it. Sub-plans B–E import only from these symbols.

**Placeholder scan:** No "TBD" or "implement later" — every code step has actual code. The only deferred item is `aichemy-price` CLI behavior, which is intentional for this sub-plan (sub-plan E populates `cli.py`); the entry point is wired in `pyproject.toml` here so later sub-plans don't need to touch build config.

**Type consistency:** `PriceLookup` requires `name: str` and `lookup(VendorRef) -> PriceQuote | None` everywhere. `VendorResolver` requires `name: str` and `resolve(str) -> list[ResolverHit]`. Both are exercised by the chain tests' `_Stub` / `_HitOnce` / `_AlwaysMiss` mocks, so any later sub-plan that fails to set `name` or returns the wrong type will fail this sub-plan's tests too once integrated.
