"""Fluorochem Azure-blob JSON pricing vendor.

Per CLAIM-01 (PARTIAL — endpoint REAL, fields FABRICATED in original report):
  Endpoint: https://fluorochemcouk.blob.core.windows.net/pricing/{ProductCode}.json
  Auth:     none; anonymous read-only blob
  Coverage: F-prefix and BR-prefix SKUs only

The caller can pass either:
  - a full pack SKU like "F765353-1G" → vendor returns that exact pack's price
  - a bare product code like "F765353" → vendor returns the first pack found

There is NO `min_gbp`, `max_gbp`, or `has_stock_*` field in the response.
Stock data is not in this endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams

_BASE_URL = "https://fluorochemcouk.blob.core.windows.net/pricing"


def _split_sku(full_sku: str) -> tuple[str, str | None]:
    """`F765353-1G` → ("F765353", "F765353-1G"); `F765353` → ("F765353", None)."""
    if "-" not in full_sku:
        return full_sku, None
    head, _ = full_sku.rsplit("-", 1)
    return head, full_sku


class FluorochemVendor:
    name = "fluorochem"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        product_code, requested_pack = _split_sku(ref.sku)
        url = f"{_BASE_URL}/{product_code}.json"
        resp = self._client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        body = resp.json()
        product = body.get(product_code) or {}
        if not product:
            return None
        if requested_pack and requested_pack in product:
            pack_key = requested_pack
            pack = product[pack_key]
        else:
            pack_key, pack = next(iter(product.items()))
        gbp = pack.get("Pricing", {}).get("GBP", {})
        base = gbp.get("Base Price")
        if base is None:
            return None
        size = float(pack["Size"])
        unit = str(pack["Size Unit"])
        return PriceQuote(
            vendor=self.name,
            sku=pack_key,
            price=float(base),
            currency="GBP",
            pack_size_g=pack_size_to_grams(size, unit),
            fetched_at=datetime.now(UTC),
            raw=pack,
        )
