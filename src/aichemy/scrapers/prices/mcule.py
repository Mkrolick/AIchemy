"""Mcule (mcule.com) price scraper via public REST API.

Mcule offers a free public REST API for compound search + pricing. No auth
required for basic queries. Used here as a replacement for Sigma (whose
HTML search is actively blocked by CloudFlare for automated clients).

API docs: https://mcule.com/api/v1/search/

Pipeline:
1. GET https://mcule.com/api/v1/search/exact/?query=<SMILES> — returns
   matching compound(s) with an mcule_id.
2. GET https://mcule.com/api/v1/compound/<mcule_id>/prices/ — returns
   price tiers in USD per pack size.
3. Compute median per-gram USD across tiers (same normalization pattern
   as the other scrapers).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.registry import register_scraper

log = logging.getLogger(__name__)

BASE = "https://mcule.com/api/v1"

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


class MculeScraper(PriceScraperBase):
    vendor_name = "mcule"

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        # Step 1: exact SMILES search
        search_url = f"{BASE}/search/exact/?query={quote(smiles, safe='')}"
        resp = self._get(search_url)
        if resp is None or resp.status_code != 200:
            return None
        try:
            results = resp.json().get("results", [])
        except Exception:
            return None
        if not results:
            return None

        mcule_id = results[0].get("mcule_id") or results[0].get("id")
        if not mcule_id:
            return None

        # Step 2: fetch price tiers for that compound
        # Mcule's newer API path; older is /compound/<id>/prices/. Try both.
        for endpoint in (
            f"{BASE}/compound/{mcule_id}/prices/",
            f"{BASE}/compound/{mcule_id}/",
        ):
            tier_resp = self._get(endpoint)
            if tier_resp is None or tier_resp.status_code != 200:
                continue
            try:
                body = tier_resp.json()
            except Exception:
                continue
            tiers = _extract_tiers(body)
            if not tiers:
                continue
            per_gram = _median_per_gram(tiers)
            if per_gram is None:
                continue
            return PriceQuote(
                smiles=smiles,
                price_per_gram_usd=per_gram,
                vendor=self.vendor_name,
                source_url=endpoint,
                fetched_at=datetime.now(UTC),
                extra={"mcule_id": str(mcule_id)},
            )
        return None


def _extract_tiers(body: Any) -> list[tuple[float, str]]:
    """Pull (price_usd, pack_size_str) tuples from a Mcule response body.

    Mcule's response shape varies by endpoint; defensively walk dicts/lists.
    """
    tiers: list[tuple[float, str]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            price = node.get("price") or node.get("price_usd") or node.get("amount")
            size = node.get("pack_size") or node.get("size") or node.get("amount_str")
            if isinstance(price, (int, float)) and isinstance(size, str):
                tiers.append((float(price), size))
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(body)
    return tiers


def _median_per_gram(tiers: list[tuple[float, str]]) -> float | None:
    per_gram: list[float] = []
    for price, size in tiers:
        m = _PACK.search(size)
        if not m:
            continue
        try:
            qty = float(m.group(1))
        except ValueError:
            continue
        factor = _UNIT_TO_GRAMS.get(m.group(2).lower(), 0.0)
        if factor <= 0:
            continue
        grams = qty * factor
        if grams <= 0:
            continue
        val = price / grams
        if 0.01 < val < 100_000:
            per_gram.append(val)
    if not per_gram:
        return None
    per_gram.sort()
    n = len(per_gram)
    return per_gram[n // 2] if n % 2 == 1 else (per_gram[n // 2 - 1] + per_gram[n // 2]) / 2.0


def _factory(**kwargs: Any) -> MculeScraper:
    return MculeScraper(**kwargs)


register_scraper("mcule", _factory)
