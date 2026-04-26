"""Molbase rendered-markdown parser (L3 fallback).

Separate module from `vendors/molbase.py`. Molbase aggregates Chinese
suppliers, so multi-currency support is mandatory — many CAS pages price
in CNY (¥) only. Per CLAIM-18.

The currency-token map below is duplicated from `vendors/molbase.py` —
promote to `vendors/_common.py` once we're sure both stay in sync. Keeping
them inline for v1 to avoid touching shipped sub-plan C code.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aichemy_pricing.types import Currency, PriceQuote
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

URL_TEMPLATE = "https://www.molbase.com/cas/{sku}.html"

# Capture group 1 = currency token; group 2 = numeric price.
_PRICE_RE = re.compile(r"(USD|US\$|\$|¥|CNY|RMB|EUR|€|GBP|£)\s*([\d,.]+)", re.I)
_PACK_RE = re.compile(r"\b([\d.]+)\s*(mg|g|kg)\b", re.I)

# duplicated from vendors/molbase.py — promote to _common.py once we're sure
# both stay in sync
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


def parse(markdown: str, sku: str) -> PriceQuote | None:
    text = strip_molarity_tokens(markdown)
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
        vendor="molbase",
        sku=sku,
        price=price,
        currency=currency,
        pack_size_g=pack_size_to_grams(size, unit),
        fetched_at=datetime.now(UTC),
        raw={"source": "browserbase_fetch", "url_template": URL_TEMPLATE},
    )
