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
            "INSERT OR REPLACE INTO quote_cache(vendor, sku, quote_json, fetched_at) "
            "VALUES (?, ?, ?, ?)",
            (
                ref.vendor,
                ref.sku,
                result.model_dump_json() if result else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return result
