"""Adapter exposing scraped prices as a ``PriceLookup`` for the preprocessing chain."""

from __future__ import annotations

import logging
from pathlib import Path

from aichemy.scrapers.prices.cache import PriceCache

log = logging.getLogger(__name__)


class ScrapedPriceLookup:
    """Reads prices from the scraper cache only (does not scrape on-demand).

    Keep scraping separate from pipeline execution: scrape offline via
    `scripts/scrape_prices_full.py`, then the pipeline's `augment prices`
    stage only reads the cache. This keeps CI/pipeline runs offline and
    deterministic.

    Aggregation: when multiple vendors have priced the same SMILES, returns
    the MEDIAN — more robust to outliers than min (one vendor's sale price)
    or max (one vendor's specialty premium).
    """

    def __init__(self, cache_path: Path, ttl_days: int = 30) -> None:
        self._cache = PriceCache(cache_path, ttl_days=ttl_days)

    def close(self) -> None:
        self._cache.close()

    def lookup(self, smiles: str) -> float | None:
        if not smiles:
            return None
        quotes = self._cache.all_quotes_for(smiles)
        if not quotes:
            return None
        prices = sorted(q.price_per_gram_usd for q in quotes)
        n = len(prices)
        if n % 2 == 1:
            return prices[n // 2]
        return (prices[n // 2 - 1] + prices[n // 2]) / 2.0
