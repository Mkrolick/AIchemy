"""Tocris Bioscience — anonymous USD prices in SSR HTML.

Per CLAIM-25 corroboration:
  URL: https://www.tocris.com/products/{slug}_{itemID}
  Anti-bot: none; browser-UA HTTP GET returns the body with prices inline.

The caller passes `sku = "{slug}_{itemID}"`, e.g. "jw-642_4906". We extract
the cheapest visible (pack, price) pair from the pack-prices table via regex.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

_PACK_PRICE_RE = re.compile(
    r"([\d.]+)\s*(mg|g|kg|µg|ug|mcg)\b[^$]*\$\s*([\d,]+(?:\.\d+)?)",
    re.I,
)


class TocrisVendor:
    name = "tocris"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.tocris.com/products/{ref.sku}"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        # Strip MW / molarity tokens (g/mol, mg/mL) before regex search — without
        # this, the first "Molecular Weight: 308.4 g/mol" on the page is paired
        # with the first $price, producing a price ~3 orders of magnitude wrong.
        match = _PACK_PRICE_RE.search(strip_molarity_tokens(resp.text))
        if not match:
            return None
        try:
            size = float(match.group(1))
            unit = match.group(2).lower()
            price = float(match.group(3).replace(",", ""))
        except ValueError:
            return None
        return PriceQuote(
            vendor=self.name,
            sku=ref.sku,
            price=price,
            currency="USD",
            pack_size_g=pack_size_to_grams(size, unit),
            fetched_at=datetime.now(UTC),
            raw={"url": url},
        )
