"""MedChemExpress — Cloudflare-aware via curl_cffi.

Per CLAIM-15: medchemexpress.com/{slug}.html. Plain httpx with Chrome UA still
gets 403; passing requires curl_cffi's TLS fingerprint (impersonate="chrome124").
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aichemy_pricing.http import make_cf_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

_PACK_PRICE_RE = re.compile(
    r"([\d.]+)\s*(mg|g|kg|µg|ug|mcg)\b[^$]{0,200}\$\s*([\d,]+(?:\.\d+)?)",
    re.I | re.S,
)


class MedChemExpressVendor:
    name = "medchemexpress"

    def __init__(self, client=None) -> None:  # type: ignore[no-untyped-def]
        self._client = client if client is not None else make_cf_client()  # type: ignore[no-untyped-call]

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.medchemexpress.com/{ref.sku}.html"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        m = _PACK_PRICE_RE.search(strip_molarity_tokens(resp.text))
        if not m:
            return None
        try:
            size = float(m.group(1))
            unit = m.group(2).lower()
            price = float(m.group(3).replace(",", ""))
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
