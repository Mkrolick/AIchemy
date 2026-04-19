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
from aichemy.scrapers.prices.pubchem import PubChemResolver
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

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Shared PubChem resolver for SMILES -> CAS
        self._pubchem = PubChemResolver()

    def close(self) -> None:
        super().close()
        self._pubchem.close()

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        # Step 1: SMILES -> identifiers via PubChem.
        ids = self._pubchem.resolve(smiles)
        if ids is None:
            return None

        # Empirically, ChemicalBook's /Search_EN.aspx blocks CAS-number
        # searches with 503; name-based search (IUPAC or common name) works.
        # Try IUPAC first, then bulk synonyms, then CAS as last resort.
        candidates: list[str] = []
        if ids.iupac_name:
            candidates.append(ids.iupac_name)
        for syn in ids.synonyms[:5]:
            if syn and syn not in candidates:
                candidates.append(syn)
        for cas in ids.cas:
            if cas not in candidates:
                candidates.append(cas)

        product_url: str | None = None
        used_query: str | None = None
        for query in candidates:
            url = SEARCH_URL.format(query=quote_plus(query))
            resp = self._get(url)
            if resp is None or resp.status_code != 200:
                continue
            candidate_url = self._extract_first_product_link(resp.text)
            if candidate_url:
                product_url = candidate_url
                used_query = query
                break

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
            extra={"query": used_query or "", "pubchem_cid": str(ids.cid)},
        )

    @staticmethod
    def _extract_first_product_link(html: str) -> str | None:
        """Pick a product link INSIDE the search-results section, not sidebar.

        ChemicalBook's layout puts sidebar "popular products" (a perpetual
        ethanol link in particular) before search results. Prefer links
        that appear after a search-results heading.
        """
        all_matches = list(
            re.finditer(
                r'href="(/[A-Za-z_]*(?:ChemicalProductProperty|ProductChemicalProperties)[^"]*)"',
                html,
            )
        )
        if not all_matches:
            return None

        heading_idx = max(
            html.find("Search Results"),
            html.find("Product Information"),
            html.find("ProductList"),
            html.find('id="ContentPlaceHolder1"'),
        )
        if heading_idx >= 0:
            for m in all_matches:
                if m.start() > heading_idx:
                    return urljoin(BASE_URL, m.group(1))

        # Fallback: skip the first 2 matches (presumed sidebar) if we have ≥3.
        pick = all_matches[min(2, len(all_matches) - 1)]
        return urljoin(BASE_URL, pick.group(1))

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
            # Clip absurd values. Commodity bulk (ethanol, methanol) can
            # legitimately be <$0.001/g when sold by the ton, so the floor
            # has to be very low. $0 matches (from e.g. "Min. Order: $0")
            # are excluded by requiring strictly > 0.
            if 0.0 < per_gram < 100_000:
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
