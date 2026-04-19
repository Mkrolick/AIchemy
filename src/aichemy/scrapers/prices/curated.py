"""Curated-catalog chemical-price lookup.

Returns per-gram USD prices for SMILES present in a committed JSON snapshot
of real vendor catalog prices. NOT a live web scraper — the JSON is
captured manually from public vendor listings (Sigma-Aldrich, TCI, Fisher
Scientific, Millipore) and updated via pull request.

Rationale: major commercial vendors (Sigma, Thermo) aggressively block
automated HTTP scraping (CloudFlare + bot detection). A curated snapshot
of real prices for common catalog molecules is the most reliable source
for the top-N bulk chemicals; web scrapers (ChemicalBook, Fisher) cover
the long tail.

Expanding the catalog: edit ``curated_prices.json`` and commit.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aichemy.preprocessing.chem.smiles import canonicalize, is_valid
from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.registry import register_scraper

log = logging.getLogger(__name__)

_CATALOG_PATH = Path(__file__).parent / "curated_prices.json"


def _load_catalog() -> dict[str, float]:
    """Load + canonicalize SMILES keys from the curated JSON."""
    if not _CATALOG_PATH.exists():
        log.warning("Curated prices JSON not found at %s", _CATALOG_PATH)
        return {}
    with open(_CATALOG_PATH) as f:
        raw = json.load(f)
    canonical_map: dict[str, float] = {}
    for smi, price in raw.items():
        if smi.startswith("_"):
            continue
        if not isinstance(price, (int, float)):
            continue
        if is_valid(smi):
            try:
                canonical = canonicalize(smi)
                canonical_map[canonical] = float(price)
            except Exception as exc:
                log.debug("Curated: skipping unparseable %s: %s", smi, exc)
        else:
            canonical_map[smi] = float(price)
    return canonical_map


class CuratedPriceScraper(PriceScraperBase):
    """Look up per-gram prices from the committed curated JSON catalog."""

    vendor_name = "curated"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._catalog = _load_catalog()
        log.info("Curated catalog loaded: %d molecules", len(self._catalog))

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        if not smiles:
            return None
        price = self._catalog.get(smiles)
        if price is None and is_valid(smiles):
            try:
                canonical = canonicalize(smiles)
                price = self._catalog.get(canonical)
            except Exception:
                return None
        if price is None:
            return None
        return PriceQuote(
            smiles=smiles,
            price_per_gram_usd=price,
            vendor=self.vendor_name,
            source_url=f"file://{_CATALOG_PATH}",
            fetched_at=datetime.now(UTC),
            extra={"catalog": "curated_prices.json"},
        )


def _factory(**kwargs: Any) -> CuratedPriceScraper:
    return CuratedPriceScraper(**kwargs)


register_scraper("curated", _factory)
