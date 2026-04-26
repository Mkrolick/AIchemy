"""Tocris rendered-markdown parser (L3 fallback).

Separate module from `vendors/tocris.py`: that one talks to tocris.com via
plain httpx; this one parses already-rendered markdown returned by the
Browserbase Fetch API. Used as the fallback when the L2 httpx path is
blocked. SKU = `{slug}_{itemID}`, e.g. `jw-642_4906`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aichemy_pricing.types import PriceQuote
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

URL_TEMPLATE = "https://www.tocris.com/products/{sku}"

_PACK_PRICE_RE = re.compile(
    r"([\d.]+)\s*(mg|g|kg|µg|ug|mcg)\b[^$]{0,400}\$\s*([\d,]+(?:\.\d+)?)",
    re.I | re.S,
)


def parse(markdown: str, sku: str) -> PriceQuote | None:
    text = strip_molarity_tokens(markdown)
    m = _PACK_PRICE_RE.search(text)
    if not m:
        return None
    try:
        size = float(m.group(1))
        unit = m.group(2).lower()
        price = float(m.group(3).replace(",", ""))
    except ValueError:
        return None
    return PriceQuote(
        vendor="tocris",
        sku=sku,
        price=price,
        currency="USD",
        pack_size_g=pack_size_to_grams(size, unit),
        fetched_at=datetime.now(UTC),
        raw={"source": "browserbase_fetch", "url_template": URL_TEMPLATE},
    )
