"""Molbase aggregator (~49M compounds, mostly Chinese suppliers).

Per CLAIM-18 (PARTIAL):
  Real URL: https://www.molbase.com/cas/{CAS}.html
  (Original report's /en/cas-{CAS}.html 404s 100%.)
  Anonymous list prices visible. SKU = CAS number.

Page is server-rendered HTML; we extract the first visible (currency, price,
pack) triple via targeted regex. Currency is captured because the majority
of Molbase suppliers are Chinese and price exclusively in CNY (¥) — defaulting
to USD would silently mis-label these.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import Currency, PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

# Capture group 1 = currency token; group 2 = numeric price.
_PRICE_RE = re.compile(r"(USD|US\$|\$|¥|CNY|RMB|EUR|€|GBP|£)\s*([\d,.]+)", re.I)
_PACK_RE = re.compile(r"\b([\d.]+)\s*(mg|g|kg)\b", re.I)

_TOKEN_TO_CURRENCY: dict[str, Currency] = {
    "USD": "USD",
    "US$": "USD",
    "$": "USD",
    "¥": "CNY",
    "CNY": "CNY",
    "RMB": "CNY",
    "EUR": "EUR",
    "€": "EUR",
    "GBP": "GBP",
    "£": "GBP",
}


def _normalize_currency(token: str) -> Currency | None:
    return _TOKEN_TO_CURRENCY.get(token.upper()) or _TOKEN_TO_CURRENCY.get(token)


class MolbaseVendor:
    name = "molbase"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.molbase.com/cas/{ref.sku}.html"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        text = strip_molarity_tokens(resp.text)
        m_price = _PRICE_RE.search(text)
        m_pack = _PACK_RE.search(text)
        if not (m_price and m_pack):
            return None
        currency = _normalize_currency(m_price.group(1))
        if currency is None:
            return None
        try:
            price = float(m_price.group(2).replace(",", ""))
            size = float(m_pack.group(1))
        except ValueError:
            return None
        unit = m_pack.group(2).lower()
        return PriceQuote(
            vendor=self.name,
            sku=ref.sku,
            price=price,
            currency=currency,
            pack_size_g=pack_size_to_grams(size, unit),
            fetched_at=datetime.now(UTC),
            raw={"url": url},
        )
