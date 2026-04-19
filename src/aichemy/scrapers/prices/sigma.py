"""Sigma-Aldrich (sigmaaldrich.com) price scraper.

Sigma's GraphQL endpoint requires access tokens. The simpler public path
is the HTML search URL `https://www.sigmaaldrich.com/US/en/search/<CAS>`
which 302-redirects to the first matching product page. Product pages
embed pricing in JSON-LD `<script type="application/ld+json">` blocks.

Pipeline:
1. Resolve SMILES → CAS number via PubChem.
2. GET Sigma's search URL (auto-redirects to product page).
3. Parse JSON-LD Offer objects for (price, pack-size) → per-gram USD.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.pubchem import PubChemResolver
from aichemy.scrapers.prices.registry import register_scraper

log = logging.getLogger(__name__)

SEARCH_URL_TMPL = "https://www.sigmaaldrich.com/US/en/search/{query}?focus=products"

# Unit parsing for pricing tiers (same normalization as ChemicalBook).
_PACK = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|g|mg|ug|µg|ng|l|ml|ul|µl)\b",
    re.IGNORECASE,
)
_UNIT_TO_GRAMS = {
    "kg": 1000.0,
    "g": 1.0,
    "mg": 1e-3,
    "ug": 1e-6,
    "µg": 1e-6,
    "ng": 1e-9,
    "l": 1000.0,
    "ml": 1.0,
    "ul": 1e-3,
    "µl": 1e-3,
}


class SigmaAldrichScraper(PriceScraperBase):
    vendor_name = "sigma_aldrich"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pubchem = PubChemResolver()

    def close(self) -> None:
        super().close()
        self._pubchem.close()

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        # Sigma search is indexed by CAS, product name, and catalog number —
        # NOT by SMILES. Resolve via PubChem first.
        ids = self._pubchem.resolve(smiles)
        if ids is None:
            return None

        # Try CAS numbers first, fall back to IUPAC/common name.
        queries: list[str] = list(ids.cas)
        if ids.iupac_name:
            queries.append(ids.iupac_name)
        for syn in ids.synonyms[:3]:
            if syn not in queries:
                queries.append(syn)

        for query in queries:
            search_url = SEARCH_URL_TMPL.format(query=quote(query, safe=""))
            resp = self._get(search_url)
            if resp is None or resp.status_code != 200:
                continue
            # Redirect target may be the product page directly, or a results
            # page with a single top hit. Look for JSON-LD on the landing page.
            price_per_gram = _extract_sigma_price_per_gram(resp.text)
            if price_per_gram is None:
                continue
            return PriceQuote(
                smiles=smiles,
                price_per_gram_usd=price_per_gram,
                vendor=self.vendor_name,
                source_url=str(resp.url),
                fetched_at=datetime.now(UTC),
                extra={"query": query, "pubchem_cid": str(ids.cid)},
            )
        return None


def _extract_sigma_price_per_gram(html: str) -> float | None:
    """Pull the cheapest per-gram USD price from Sigma's product-page JSON-LD."""
    # Sigma embeds a <script type="application/ld+json"> with Product + Offer
    # objects. The Offer has `price` + `description` (size like "25 g").
    pattern = re.compile(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    per_gram_prices: list[float] = []
    for m in pattern.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        for price, size in _iter_offer_prices(data):
            grams = _size_to_grams(size)
            if grams is None or grams <= 0:
                continue
            per_gram = price / grams
            if 0.01 < per_gram < 100_000:
                per_gram_prices.append(per_gram)

    if not per_gram_prices:
        return None
    per_gram_prices.sort()
    # Median, not min — min often reflects a sale price tier.
    n = len(per_gram_prices)
    return (
        per_gram_prices[n // 2]
        if n % 2 == 1
        else (per_gram_prices[n // 2 - 1] + per_gram_prices[n // 2]) / 2.0
    )


def _iter_offer_prices(node: Any):
    """Recursively yield (price, description) pairs from JSON-LD Offer objects."""
    if isinstance(node, dict):
        typ = node.get("@type")
        types = [typ] if isinstance(typ, str) else list(typ or [])
        if "Offer" in types or "AggregateOffer" in types:
            price = node.get("price") or node.get("lowPrice")
            currency = node.get("priceCurrency") or "USD"
            desc = node.get("description") or node.get("name") or ""
            if price is not None and str(currency).upper() == "USD":
                with contextlib.suppress(TypeError, ValueError):
                    yield float(price), str(desc)
        for v in node.values():
            yield from _iter_offer_prices(v)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_offer_prices(item)


def _size_to_grams(size_str: str) -> float | None:
    m = _PACK.search(size_str)
    if not m:
        return None
    try:
        qty = float(m.group(1))
    except ValueError:
        return None
    factor = _UNIT_TO_GRAMS.get(m.group(2).lower(), 0.0)
    if factor <= 0:
        return None
    return qty * factor


def _factory(**kwargs: Any) -> SigmaAldrichScraper:
    return SigmaAldrichScraper(**kwargs)


register_scraper("sigma_aldrich", _factory)
