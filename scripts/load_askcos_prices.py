"""One-shot: load the ASKCOS buyables catalog into the price cache.

Canonicalizes 280k SMILES with RDKit (~30s cold, warm-cached afterwards)
and writes one ``price_quotes`` row per unique canonical SMILES with
vendor='askcos' and source_url pointing at the ASKCOS data repo.

Usage:
    uv run python scripts/load_askcos_prices.py
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from aichemy.scrapers.prices.askcos import SOURCE_URL, AskcosCatalog
from aichemy.scrapers.prices.base import PriceQuote
from aichemy.scrapers.prices.cache import PriceCache


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "interim" / "prices_cache.sqlite",
    )
    parser.add_argument("--ttl-days", type=int, default=365 * 10)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger("load_askcos")

    t0 = time.time()
    catalog = AskcosCatalog()
    log.info("Loaded %d unique canonical SMILES in %.1fs", catalog.size, time.time() - t0)

    cache = PriceCache(args.cache_path, ttl_days=args.ttl_days)
    now = datetime.now(UTC)
    written = 0
    try:
        for canon, entry in catalog._by_canon.items():
            quote = PriceQuote(
                smiles=canon,
                price_per_gram_usd=entry.ppg_usd,
                vendor="askcos",
                source_url=SOURCE_URL,
                fetched_at=now,
                extra={"askcos_source": entry.source, "raw_smiles": entry.raw_smiles},
            )
            cache.put(canon, "askcos", quote)
            written += 1
            if written % 10_000 == 0:
                log.info("wrote %d / %d", written, catalog.size)
    finally:
        cache.close()

    log.info("DONE. %d rows into %s in %.1fs", written, args.cache_path, time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
