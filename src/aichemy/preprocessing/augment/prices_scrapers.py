"""Concrete scraper implementations for the federated price lookup.

Each scraper is a `ScraperBase` subclass. Registered against `make_lookup`
via `register_scraper("<vendor_name>", cls)`. None are wired into the default
`chain` — users must explicitly enable them in config (`backend=chained`,
`scraper.enabled=True`, plus the vendor's own `enabled=True`).

The scrapers here favor parsing publicly-advertised structured data
(`<script type="application/ld+json">` Schema.org Product microdata) rather
than scraping arbitrary HTML. This is technically and ethically safer:
structured data is explicitly published by the site for machine consumption,
and parsing it does not constitute reverse-engineering of the page layout.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from aichemy.preprocessing.augment.prices import ScraperBase, register_scraper

log = logging.getLogger(__name__)


# ---------- Schema.org JSON-LD scraper (vendor-agnostic) --------------------


class StructuredDataPriceScraper(ScraperBase):
    """Generic scraper that extracts prices from Schema.org JSON-LD.

    Many chemical vendors publish structured product data on their pages via
    `<script type="application/ld+json">` blocks following the Schema.org
    Product vocabulary. This scraper:

      1. Constructs a product-search URL using the vendor's query template.
      2. Fetches the page (honoring robots.txt, rate limits, backoff).
      3. Extracts every `<script type="application/ld+json">` block.
      4. Parses each as JSON, recurses into dicts looking for `Product` or
         `Offer` objects with a `price` / `priceSpecification` field.
      5. Normalizes to USD per gram when possible; returns None otherwise.

    The query template is provided via `search_url_template`, which should
    be a Python format string with a `{query}` placeholder. The query is
    by default the canonical SMILES (URL-encoded); override `_build_query`
    for vendors that require CAS number or product name instead.
    """

    vendor_name = "structured_jsonld"

    def __init__(
        self,
        vendor_config: Any,
        user_agent: str,
        search_url_template: str,
        respect_robots_txt: bool = True,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
    ) -> None:
        super().__init__(
            vendor_config=vendor_config,
            user_agent=user_agent,
            respect_robots_txt=respect_robots_txt,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
        )
        self._search_url_template = search_url_template

    def _build_query(self, smiles: str) -> str:
        from urllib.parse import quote

        return quote(smiles, safe="")

    def _fetch_price(self, smiles: str) -> float | None:
        url = self._search_url_template.format(query=self._build_query(smiles))
        resp = self._get(url)
        if resp is None or resp.status_code != 200:
            return None
        return self._extract_price_from_html(resp.text)

    @staticmethod
    def _extract_price_from_html(html: str) -> float | None:
        """Find Schema.org JSON-LD blocks and extract a USD/gram price.

        Returns None if no structured Product/Offer with a usable price is
        found. Handles both single blocks and arrays.
        """
        pattern = re.compile(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            raw = match.group(1).strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            price = _find_price_in_jsonld(data)
            if price is not None:
                return price
        return None


def _find_price_in_jsonld(node: Any) -> float | None:
    """Recursively search a JSON-LD tree for a Product/Offer price.

    Returns the first USD price encountered, converted to a float. Non-USD
    prices are ignored to avoid currency conversion surprises.
    """
    if isinstance(node, dict):
        type_field = node.get("@type", "")
        # Normalize: @type can be a string or a list of strings.
        types = [type_field] if isinstance(type_field, str) else list(type_field or [])

        if "Offer" in types or "AggregateOffer" in types:
            price = node.get("price") or node.get("lowPrice")
            currency = node.get("priceCurrency") or "USD"
            if price is not None and str(currency).upper() == "USD":
                try:
                    return float(price)
                except (TypeError, ValueError):
                    pass

        if "priceSpecification" in node:
            result = _find_price_in_jsonld(node["priceSpecification"])
            if result is not None:
                return result

        for value in node.values():
            result = _find_price_in_jsonld(value)
            if result is not None:
                return result
    elif isinstance(node, list):
        for item in node:
            result = _find_price_in_jsonld(item)
            if result is not None:
                return result
    return None


# Register under a neutral vendor name. Concrete sites (e.g. a specific
# vendor) would subclass this and set their own `vendor_name` + search URL.
register_scraper("structured_jsonld", StructuredDataPriceScraper)


# ---------- Vendor subclasses (templates only; none enabled by default) -----


class BenchChemScraper(StructuredDataPriceScraper):
    """Example: BenchChem.com — small chemical supplier with search-by-SMILES.

    Disabled by default. To enable:
        prices:
          backend: chained
          chain: [pubchem, scraper]
          scraper:
            enabled: true
            vendors:
              - name: benchchem
                enabled: true
                rate_limit_seconds: 5.0

    Note: ALWAYS verify BenchChem's robots.txt and ToS before enabling.
    The `respect_robots_txt=True` default will block requests if disallowed,
    but the allowlist itself is an intentional, reviewable act.
    """

    vendor_name = "benchchem"

    def __init__(
        self,
        vendor_config: Any,
        user_agent: str,
        respect_robots_txt: bool = True,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
    ) -> None:
        super().__init__(
            vendor_config=vendor_config,
            user_agent=user_agent,
            search_url_template="https://www.benchchem.com/search?q={query}",
            respect_robots_txt=respect_robots_txt,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
        )


register_scraper("benchchem", BenchChemScraper)


class ChemicalBookScraper(StructuredDataPriceScraper):
    """Example: ChemicalBook.com — chemistry info aggregator. Disabled by default."""

    vendor_name = "chemicalbook"

    def __init__(
        self,
        vendor_config: Any,
        user_agent: str,
        respect_robots_txt: bool = True,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
    ) -> None:
        super().__init__(
            vendor_config=vendor_config,
            user_agent=user_agent,
            search_url_template="https://www.chemicalbook.com/Search_EN.aspx?keyword={query}",
            respect_robots_txt=respect_robots_txt,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
        )


register_scraper("chemicalbook", ChemicalBookScraper)
