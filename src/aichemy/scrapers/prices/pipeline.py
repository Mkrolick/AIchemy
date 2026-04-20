"""Price-scraping pipeline: iterate SMILES, try scrapers in order, cache results.

No vendor scrapers currently ship — the vendor-specific modules were torn
out while we reconsider the price-data source (JHU Reaxys / SciFinder are
the planned replacements). The pipeline infrastructure remains so a new
scraper implementing ``PriceScraperBase`` can be dropped in and registered
via ``aichemy.scrapers.prices.registry.register_scraper``.

Load pattern:
    from aichemy.scrapers.prices import PriceCache
    from aichemy.scrapers.prices.pipeline import PricePipeline

    pipeline = PricePipeline(
        scrapers=[...],  # instantiate whatever scrapers you register
        cache=PriceCache(Path("data/interim/prices_cache.sqlite")),
    )
    for smi in smiles_list:
        pipeline.get_price(smi)  # populates cache
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.cache import PriceCache, _Miss
from aichemy.scrapers.prices.registry import get_scraper

log = logging.getLogger(__name__)

DEFAULT_VENDOR_ORDER: list[str] = []


def default_scrapers(
    user_agent: str,
    order: Sequence[str] = tuple(DEFAULT_VENDOR_ORDER),
    rate_limit_seconds: float = 3.0,
    respect_robots_txt: bool = False,
) -> list[PriceScraperBase]:
    """Instantiate the named scrapers from the registry.

    Returns an empty list when no scrapers are registered (current state).
    """
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
        """Look up the first vendor that has a price; populate the cache on the way."""
        for scraper in self._scrapers:
            cached = self._cache.get(smiles, scraper.vendor_name)
            if isinstance(cached, PriceQuote):
                return cached
            if isinstance(cached, _Miss):
                continue

            quote = scraper.fetch(smiles)
            self._cache.put(smiles, scraper.vendor_name, quote)
            if quote is not None:
                return quote
        return None

    def get_all_prices(self, smiles: str) -> list[PriceQuote]:
        """Scrape every vendor for this SMILES; populate cache; return all hits."""
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
