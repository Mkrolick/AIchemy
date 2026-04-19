"""Thermo Fisher Scientific (thermofisher.com) price scraper.

Thermo's product search exposes a public JSON endpoint used by their React
search UI:

    https://www.thermofisher.com/search-results?query=<TERM>

…and the product detail pages embed pricing tiers in a JSON blob that the
page's JavaScript consumes. We hit the search endpoint, pick the top product,
then parse pricing from the detail page.

Thermo occasionally serves interstitial pages or Cloudflare challenges on
high-volume scraping; when that happens we return None gracefully.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.registry import register_scraper

log = logging.getLogger(__name__)

BASE = "https://www.thermofisher.com"
# Thermo's search page returns HTML that embeds a JSON blob with hits.
SEARCH_URL = BASE + "/search-results?query={query}&page=1"

_PACK = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|g|mg|µg|ug|ng|l|ml|µl|ul)\b",
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


class ThermoFisherScraper(PriceScraperBase):
    vendor_name = "thermofisher"

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        url = SEARCH_URL.format(query=quote_plus(smiles))
        # Thermo's React UI requires a browser-like Accept header.
        resp = self._get(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        if resp is None or resp.status_code != 200:
            return None

        product_url = self._extract_first_product_link(resp.text)
        if not product_url:
            return None

        detail = self._get(product_url)
        if detail is None or detail.status_code != 200:
            return None

        price_per_gram = _extract_thermo_price_per_gram(detail.text)
        if price_per_gram is None:
            return None

        return PriceQuote(
            smiles=smiles,
            price_per_gram_usd=price_per_gram,
            vendor=self.vendor_name,
            source_url=product_url,
            fetched_at=datetime.now(UTC),
        )

    @staticmethod
    def _extract_first_product_link(html: str) -> str | None:
        # Thermo product pages follow the pattern:
        #   /order/catalog/product/XXXXXXX
        #   /us/en/home/.../product/XXXXXX
        m = re.search(
            r'href="(/order/catalog/product/[^"]+|/[^"]+/product/[^"]+)"',
            html,
        )
        if not m:
            return None
        href = m.group(1)
        if href.startswith("http"):
            return href
        return BASE + href


def _extract_thermo_price_per_gram(html: str) -> float | None:
    """Pull the cheapest per-gram USD from Thermo's embedded product JSON."""
    # Thermo embeds a __NEXT_DATA__ JSON blob on product pages.
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    per_gram_prices: list[float] = []
    if m:
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            data = None
        if data:
            for price, size in _walk_thermo_skus(data):
                grams = _size_to_grams(size)
                if grams is None or grams <= 0:
                    continue
                per_gram = price / grams
                if 0.0001 < per_gram < 100_000:
                    per_gram_prices.append(per_gram)

    # Fallback: look for JSON-LD Offer blocks
    if not per_gram_prices:
        ld_pattern = re.compile(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            re.DOTALL,
        )
        for ld in ld_pattern.finditer(html):
            try:
                node = json.loads(ld.group(1).strip())
            except json.JSONDecodeError:
                continue
            for price, size in _iter_offer_prices(node):
                grams = _size_to_grams(size)
                if grams is None or grams <= 0:
                    continue
                per_gram = price / grams
                if 0.0001 < per_gram < 100_000:
                    per_gram_prices.append(per_gram)

    if not per_gram_prices:
        return None
    per_gram_prices.sort()
    n = len(per_gram_prices)
    return (
        per_gram_prices[n // 2]
        if n % 2 == 1
        else (per_gram_prices[n // 2 - 1] + per_gram_prices[n // 2]) / 2.0
    )


def _walk_thermo_skus(node: Any):
    """Walk the Next.js page data looking for SKU price + pack-size pairs."""
    if isinstance(node, dict):
        # Thermo's product SKU objects typically have 'price' + 'unitSize' or 'size'
        price = node.get("price") or node.get("listPrice") or node.get("discountedPrice")
        size = node.get("unitSize") or node.get("size") or node.get("packSize")
        if isinstance(price, (int, float)) and size and isinstance(size, str):
            yield float(price), size
        for v in node.values():
            yield from _walk_thermo_skus(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_thermo_skus(item)


def _iter_offer_prices(node: Any):
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


def _factory(**kwargs: Any) -> ThermoFisherScraper:
    return ThermoFisherScraper(**kwargs)


register_scraper("thermofisher", _factory)
