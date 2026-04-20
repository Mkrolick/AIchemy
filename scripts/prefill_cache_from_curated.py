"""Pre-seed the price cache with curated catalog matches.

Canonicalizes every SMILES in data/processed/molecules.parquet via RDKit
and compares against the curated catalog's canonical SMILES. Every match
is written to the cache as a ``vendor=curated`` entry — no scraping,
immediate hit.

Run once after curated_prices.json is updated:
    uv run python scripts/prefill_cache_from_curated.py
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from aichemy.preprocessing.chem.smiles import canonicalize
from aichemy.scrapers.prices import PriceCache
from aichemy.scrapers.prices.base import PriceQuote
from aichemy.scrapers.prices.curated import _load_catalog


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s", stream=sys.stderr)
    log = logging.getLogger("prefill")

    root = Path(__file__).resolve().parents[1]
    mol_path = root / "data" / "processed" / "molecules.parquet"
    cache_path = root / "data" / "interim" / "prices_cache.sqlite"

    catalog = _load_catalog()
    log.info("Curated catalog: %d canonical SMILES", len(catalog))

    molecules = pl.read_parquet(mol_path)
    log.info("Scanning %d molecules", molecules.height)

    cache = PriceCache(cache_path, ttl_days=365)
    hits = 0
    tried = 0
    now = datetime.now(UTC)
    for smi in molecules.get_column("canonical_smiles").drop_nulls().to_list():
        tried += 1
        price = catalog.get(smi)
        if price is None:
            # Try canonicalizing the molecules-table SMILES (in case it's not already canonical)
            try:
                canonical = canonicalize(smi)
                price = catalog.get(canonical)
            except Exception:
                continue
        if price is None:
            continue
        quote = PriceQuote(
            smiles=smi,
            price_per_gram_usd=float(price),
            vendor="curated",
            source_url="file://curated_prices.json",
            fetched_at=now,
            extra={"catalog": "curated_prefill"},
        )
        cache.put(smi, "curated", quote)
        hits += 1
        if hits % 10 == 0:
            log.info("  Hits so far: %d (tried %d)", hits, tried)

    cache.close()
    log.info("DONE. Tried %d molecules; %d curated-catalog matches written.", tried, hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
