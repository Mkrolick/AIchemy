"""Price-scraping pipeline: iterate SMILES, try scrapers in order, cache results.

Load pattern:
    from aichemy.scrapers.prices import PriceCache
    from aichemy.scrapers.prices.pipeline import PricePipeline, default_scrapers

    pipeline = PricePipeline(
        scrapers=default_scrapers("Aichemy-research/0.1 (contact@example.com)"),
        cache=PriceCache(Path("data/interim/prices_cache.sqlite")),
    )
    for smi in smiles_list:
        pipeline.get_price(smi)  # populates cache
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

# Trigger registry registration on import.
from aichemy.scrapers.prices import chemicalbook as _cb  # noqa: F401
from aichemy.scrapers.prices import curated as _cur  # noqa: F401
from aichemy.scrapers.prices import mcule as _mc  # noqa: F401
from aichemy.scrapers.prices import playwright_fishersci as _pw_fs  # noqa: F401
from aichemy.scrapers.prices import sigma as _sig  # noqa: F401
from aichemy.scrapers.prices import thermofisher as _tf  # noqa: F401
from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.cache import PriceCache, _Miss
from aichemy.scrapers.prices.registry import get_scraper

log = logging.getLogger(__name__)

DEFAULT_VENDOR_ORDER = ["curated", "chemicalbook", "fisher_scientific"]


def default_scrapers(
    user_agent: str,
    order: Sequence[str] = tuple(DEFAULT_VENDOR_ORDER),
    rate_limit_seconds: float = 3.0,
    respect_robots_txt: bool = False,
) -> list[PriceScraperBase]:
    """Build the default stack of concrete scrapers."""
    scrapers: list[PriceScraperBase] = []
    for name in order:
        s = get_scraper(
            name,
            user_agent=user_agent,
            rate_limit_seconds=rate_limit_seconds,
            respect_robots_txt=respect_robots_txt,
        )
        if s is None:
            log.warning("No scraper registered for %r; skipping.", name)
            continue
        scrapers.append(s)
    return scrapers


class PricePipeline:
    """Coordinate multiple scrapers and a single cache for a batch of SMILES."""

    def __init__(self, scrapers: Iterable[PriceScraperBase], cache: PriceCache) -> None:
        self._scrapers = list(scrapers)
        self._cache = cache

    def close(self) -> None:
        for s in self._scrapers:
            s.close()
        self._cache.close()

    def get_price(self, smiles: str) -> PriceQuote | None:
        """Look up the first vendor that has a price; populate the cache on the way.

        Cache semantics:
        - Hit returned immediately from cache (no HTTP).
        - Miss cached too — we won't retry that vendor for this SMILES
          until the cache entry expires.
        """
        for scraper in self._scrapers:
            cached = self._cache.get(smiles, scraper.vendor_name)
            if isinstance(cached, PriceQuote):
                return cached
            if isinstance(cached, _Miss):
                continue  # known miss, try next vendor

            # Fresh fetch
            quote = scraper.fetch(smiles)
            self._cache.put(smiles, scraper.vendor_name, quote)
            if quote is not None:
                return quote
        return None

    def get_all_prices(self, smiles: str) -> list[PriceQuote]:
        """Scrape EVERY vendor for this SMILES (populates cache, returns all hits)."""
        hits: list[PriceQuote] = []
        for scraper in self._scrapers:
            cached = self._cache.get(smiles, scraper.vendor_name)
            if isinstance(cached, PriceQuote):
                hits.append(cached)
                continue
            if isinstance(cached, _Miss):
                continue
            quote = scraper.fetch(smiles)
            self._cache.put(smiles, scraper.vendor_name, quote)
            if quote is not None:
                hits.append(quote)
        return hits
