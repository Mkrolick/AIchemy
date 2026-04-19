"""ChemicalBook.com price scraper.

ChemicalBook is a chemistry aggregator that lists products with per-pack
prices (USD) from dozens of Chinese/global suppliers. For each SMILES we:

1. Hit the search endpoint with the SMILES / name / CAS.
2. Follow the first matching product link.
3. Parse the supplier price table (HTML).
4. Compute the per-gram USD price (median across supplier rows).

Returns ``None`` if no parseable product page or no price column.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus, urljoin

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.registry import register_scraper

log = logging.getLogger(__name__)

BASE_URL = "https://www.chemicalbook.com"
SEARCH_URL = BASE_URL + "/Search_EN.aspx?keyword={query}"

# Match USD prices in various formats: $5.00, USD 10, $1,234.56/g, etc.
_PRICE_NUM = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
# Match pack-size + unit: "1g", "100 mg", "500 kg", "10 ml"
_PACK = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|g|mg|ug|µg|ng|l|ml|ul|µl)\b",
    re.IGNORECASE,
)

# Normalize unit → grams when possible (volumes assume density 1 g/mL which
# is coarse but acceptable for order-of-magnitude pricing; skip otherwise).
_UNIT_TO_GRAMS = {
    "kg": 1000.0,
    "g": 1.0,
    "mg": 1e-3,
    "ug": 1e-6,
    "µg": 1e-6,
    "ng": 1e-9,
    "l": 1000.0,  # assume density 1 — crude
    "ml": 1.0,
    "ul": 1e-3,
    "µl": 1e-3,
}


class ChemicalBookScraper(PriceScraperBase):
    vendor_name = "chemicalbook"

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        # ChemicalBook's search is name/CAS-based; SMILES rarely works directly.
        # We encode the SMILES; if search has 0 hits, bail. This is a cheap
        # implementation — smarter lookup would pre-convert SMILES -> CAS
        # via PubChem, then search by CAS.
        url = SEARCH_URL.format(query=quote_plus(smiles))
        resp = self._get(url)
        if resp is None or resp.status_code != 200:
            return None

        # Find the first product link (anchor tag with /CAS/ or /ProductCAS)
        product_url = self._extract_first_product_link(resp.text)
        if not product_url:
            return None

        prod_resp = self._get(product_url)
        if prod_resp is None or prod_resp.status_code != 200:
            return None

        price_per_gram = self._extract_price_per_gram(prod_resp.text)
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
        """Best-effort: pick the first absolute-ish URL that looks like a product page."""
        # ChemicalBook product links look like:
        #   /ProductChemicalProperties_CB1234567.aspx
        #   /ChemicalProductProperty_EN_CB1234567.htm
        m = re.search(
            r'href="(/[A-Za-z_]*(?:ChemicalProductProperty|ProductChemicalProperties)[^"]*)"',
            html,
        )
        if not m:
            return None
        return urljoin(BASE_URL, m.group(1))

    @staticmethod
    def _extract_price_per_gram(html: str) -> float | None:
        """Scan HTML for price-per-size pairs and return per-gram USD median."""
        lines = html.splitlines()
        per_gram_prices: list[float] = []
        for line in lines:
            price_match = _PRICE_NUM.search(line)
            pack_match = _PACK.search(line)
            if not price_match or not pack_match:
                continue
            try:
                price = float(price_match.group(1).replace(",", ""))
                pack_qty = float(pack_match.group(1))
                pack_unit = pack_match.group(2).lower()
            except (ValueError, AttributeError):
                continue
            grams = pack_qty * _UNIT_TO_GRAMS.get(pack_unit, 0.0)
            if grams <= 0:
                continue
            per_gram = price / grams
            # Clip absurd values (likely parsing errors)
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


def _factory(**kwargs: Any) -> ChemicalBookScraper:
    return ChemicalBookScraper(**kwargs)


register_scraper("chemicalbook", _factory)
