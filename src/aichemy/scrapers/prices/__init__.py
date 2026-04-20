"""Chemical-price scraping scaffolding.

Currently shipping:
    - ``base``      — ``PriceScraperBase`` (robots.txt, rate limit, backoff)
                      and the ``PriceQuote`` dataclass.
    - ``cache``     — SQLite-backed cache with source-URL provenance.
    - ``pubchem``   — SMILES -> CID/CAS/IUPAC/synonyms resolver.
    - ``registry``  — vendor-name -> scraper factory registration.
    - ``pipeline``  — multi-vendor orchestrator.
    - ``lookup``    — ``ScrapedPriceLookup`` adapter for preprocessing.

No vendor scrapers are bundled right now — register new ones via
``register_scraper``.
"""

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.cache import PriceCache

__all__ = [
    "PriceCache",
    "PriceQuote",
    "PriceScraperBase",
]
