"""Sigma-Aldrich (sigmaaldrich.com) price scraper.

Sigma's search backend is GraphQL-based. The query used here is the same one
the public search UI hits when a user enters a search term. No auth required,
though Sigma may rate-limit / Cloudflare-challenge aggressive patterns.

Pipeline:
1. POST the GraphQL search query with the SMILES as the search term.
2. Pull the first product hit (productNumber + pricing tiers).
3. Compute per-gram USD from the cheapest tier.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.registry import register_scraper

log = logging.getLogger(__name__)

SEARCH_GQL_URL = "https://www.sigmaaldrich.com/api"
PRODUCT_URL_TMPL = "https://www.sigmaaldrich.com/US/en/product/sial/{product_number}"

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

SEARCH_QUERY = """
query ProductSearch($searchTerm: String!, $page: Int!, $perPage: Int!) {
  getProductSearchResults(
    input: {searchTerm: $searchTerm, page: $page, perPage: $perPage}
  ) {
    items {
      productNumber
      productName
      brand { key name }
    }
  }
}
"""


class SigmaAldrichScraper(PriceScraperBase):
    vendor_name = "sigma_aldrich"

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        payload = {
            "operationName": "ProductSearch",
            "query": SEARCH_QUERY,
            "variables": {"searchTerm": smiles, "page": 1, "perPage": 5},
        }
        headers = {
            "Content-Type": "application/json",
            "X-GQL-Access-Token": "",  # Some Sigma endpoints want this; empty often OK.
            "Accept": "application/json",
        }
        try:
            resp = self._client.post(
                SEARCH_GQL_URL,
                json=payload,
                headers=headers,
            )
        except Exception as exc:
            log.debug("sigma_aldrich: search POST failed: %s", exc)
            return None
        if resp.status_code != 200:
            log.debug("sigma_aldrich: search returned %d", resp.status_code)
            return None

        try:
            data = resp.json()
            items = data["data"]["getProductSearchResults"]["items"]
        except (KeyError, json.JSONDecodeError, TypeError):
            return None
        if not items:
            return None

        product_number = items[0].get("productNumber")
        if not product_number:
            return None

        # Fetch the product page, which embeds pricing tiers in JSON-LD.
        product_url = PRODUCT_URL_TMPL.format(product_number=product_number)
        page = self._get(product_url)
        if page is None or page.status_code != 200:
            return None

        price_per_gram = _extract_sigma_price_per_gram(page.text)
        if price_per_gram is None:
            return None

        return PriceQuote(
            smiles=smiles,
            price_per_gram_usd=price_per_gram,
            vendor=self.vendor_name,
            source_url=product_url,
            fetched_at=datetime.now(UTC),
            extra={"product_number": product_number},
        )


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
            if 0.0001 < per_gram < 100_000:
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
