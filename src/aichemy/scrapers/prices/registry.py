"""Registry of concrete price scrapers by vendor name.

Concrete scrapers import into this registry at module load via
`register_scraper`. The pipeline and config layer use it to instantiate
scrapers from a string name in the YAML chain config.
"""

from __future__ import annotations

from collections.abc import Callable

from aichemy.scrapers.prices.base import PriceScraperBase

# vendor_name -> factory callable taking kwargs and returning a scraper
_REGISTRY: dict[str, Callable[..., PriceScraperBase]] = {}


def register_scraper(name: str, factory: Callable[..., PriceScraperBase]) -> None:
    _REGISTRY[name] = factory


def get_scraper(name: str, **kwargs: object) -> PriceScraperBase | None:
    fn = _REGISTRY.get(name)
    if fn is None:
        return None
    return fn(**kwargs)


def known_scrapers() -> list[str]:
    return sorted(_REGISTRY.keys())
