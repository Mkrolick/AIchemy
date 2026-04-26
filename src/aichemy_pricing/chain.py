"""ChainedPriceLookup falls through; CachedPriceLookup memoizes via SQLite."""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
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
                    ref.vendor,
                    ref.sku,
                    exc,
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

    Thread-safe: each calling thread gets its own `sqlite3.Connection` via
    `threading.local`. SQLite handles concurrent writers via its file-level
    lock; conflicts retry transparently because we use `isolation_level=None`
    (autocommit). Required for the parallel `augment_prices` dispatcher.

    Cache-miss races: two concurrent lookups for the same (vendor, sku) may
    both call the inner backend before either writes. INSERT OR REPLACE keeps
    storage consistent (last-write-wins), but the inner is called twice. For
    workloads where this matters, add a per-key lock at the dispatcher layer.
    """

    name = "cache"

    def __init__(self, inner: PriceLookup, db_path: Path | str, ttl_days: int = 30) -> None:
        self.inner = inner
        self.db_path = Path(db_path)
        self.ttl = timedelta(days=ttl_days)
        self._tls = threading.local()
        # Initialize schema once on the constructing thread; per-thread
        # connections opened lazily in `_conn()`.
        bootstrap = sqlite3.connect(str(self.db_path), isolation_level=None, timeout=30.0)
        try:
            bootstrap.execute("PRAGMA journal_mode=WAL")
            bootstrap.execute("PRAGMA synchronous=NORMAL")
            bootstrap.execute("PRAGMA busy_timeout=30000")
            bootstrap.executescript(_SCHEMA)
        finally:
            bootstrap.close()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), isolation_level=None, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
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
