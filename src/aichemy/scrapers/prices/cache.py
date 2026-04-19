"""SQLite cache for scraped price quotes.

Stores every successful scrape with:
- the canonical SMILES used as the key
- the scraped USD price per gram
- the vendor name + source URL (auditable provenance)
- the fetched timestamp (for TTL / staleness checks)
- the raw extra dict as JSON (for downstream analysis)

Misses are **also cached** with `price_per_gram_usd = NULL` so we don't
re-hammer vendors for molecules we just confirmed they don't have.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aichemy.scrapers.prices.base import PriceQuote


class PriceCache:
    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS price_quotes (
            smiles TEXT NOT NULL,
            vendor TEXT NOT NULL,
            price_per_gram_usd REAL,
            source_url TEXT,
            fetched_at TEXT NOT NULL,
            extra_json TEXT,
            PRIMARY KEY (smiles, vendor)
        );
        CREATE INDEX IF NOT EXISTS ix_quotes_smiles ON price_quotes(smiles);
    """

    def __init__(self, path: Path, ttl_days: int = 30) -> None:
        self._path = path
        self._ttl = timedelta(days=ttl_days)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get(self, smiles: str, vendor: str) -> PriceQuote | None | _Miss:
        """Return cached PriceQuote, _Miss() for cached negatives, or None if no cache entry.

        Expired entries are treated as no cache entry (caller will refetch).
        """
        cur = self._conn.execute(
            "SELECT price_per_gram_usd, source_url, fetched_at, extra_json "
            "FROM price_quotes WHERE smiles = ? AND vendor = ?",
            (smiles, vendor),
        )
        row = cur.fetchone()
        if row is None:
            return None
        price, source_url, fetched_at_iso, extra_json = row
        fetched_at = datetime.fromisoformat(fetched_at_iso)
        if datetime.now(UTC) - fetched_at >= self._ttl:
            return None  # expired
        if price is None:
            return _MISS
        extra: dict[str, str] = json.loads(extra_json) if extra_json else {}
        return PriceQuote(
            smiles=smiles,
            price_per_gram_usd=float(price),
            vendor=vendor,
            source_url=source_url or "",
            fetched_at=fetched_at,
            extra=extra,
        )

    def put(self, smiles: str, vendor: str, quote: PriceQuote | None) -> None:
        """Cache a hit (PriceQuote) or a miss (None)."""
        fetched_at = (quote.fetched_at if quote else datetime.now(UTC)).isoformat()
        price = quote.price_per_gram_usd if quote else None
        source_url = quote.source_url if quote else None
        extra_json = json.dumps(quote.extra) if quote and quote.extra else None
        self._conn.execute(
            "INSERT OR REPLACE INTO price_quotes "
            "(smiles, vendor, price_per_gram_usd, source_url, fetched_at, extra_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (smiles, vendor, price, source_url, fetched_at, extra_json),
        )
        self._conn.commit()

    def all_quotes_for(self, smiles: str) -> list[PriceQuote]:
        """Return every fresh (non-expired) hit across all vendors for this SMILES."""
        cur = self._conn.execute(
            "SELECT vendor, price_per_gram_usd, source_url, fetched_at, extra_json "
            "FROM price_quotes WHERE smiles = ? AND price_per_gram_usd IS NOT NULL",
            (smiles,),
        )
        out: list[PriceQuote] = []
        now = datetime.now(UTC)
        for vendor, price, source_url, fetched_at_iso, extra_json in cur.fetchall():
            fetched_at = datetime.fromisoformat(fetched_at_iso)
            if now - fetched_at >= self._ttl:
                continue
            extra = json.loads(extra_json) if extra_json else {}
            out.append(
                PriceQuote(
                    smiles=smiles,
                    price_per_gram_usd=float(price),
                    vendor=vendor,
                    source_url=source_url or "",
                    fetched_at=fetched_at,
                    extra=extra,
                )
            )
        return out


class _Miss:
    """Sentinel for cached negative lookups."""


_MISS = _Miss()
