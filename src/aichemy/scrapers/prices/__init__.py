"""Live chemical-price web scraping (scaffolding).

Current modules:
    - ``base``   — ``PriceScraperBase`` (robots.txt, rate limit, backoff)
                   and the ``PriceQuote`` dataclass.
    - ``cache``  — SQLite-backed cache with source-URL provenance.

Future modules (roadmap, not yet implemented): ``pubchem``, ``chemicalbook``,
``sigma``, ``mcule``, ``pipeline``, ``registry``. Until those land, the
active price lookup stack lives in
:mod:`aichemy.preprocessing.augment.prices`.
"""

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.cache import PriceCache

__all__ = [
    "PriceCache",
    "PriceQuote",
    "PriceScraperBase",
]
