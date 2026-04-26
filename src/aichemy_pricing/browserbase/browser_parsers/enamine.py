"""Enamine browser-parser config (L3 Browser API).

Empirically validated 2026-04-26: enaminestore.com is a CRA/SPA shell
("enable JavaScript" in the unhydrated body). Browserbase Browser API
hydrates it; Playwright reads ``page.content()`` after an 8s post-load
wait, html2text converts to markdown, and the regex below extracts pack
sizes + prices from the rendered catalog rows.

URL shape per CLAIM-07: ``enaminestore.com/catalog/EN300-{N}`` (NOT the
``enamine.net`` variant, which serves a different React route).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aichemy_pricing.types import PriceQuote
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

URL_TEMPLATE = "https://enaminestore.com/catalog/{sku}"
WAIT_AFTER_LOAD_MS = 8_000

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
        vendor="enamine",
        sku=sku,
        price=price,
        currency="USD",
        pack_size_g=pack_size_to_grams(size, unit),
        fetched_at=datetime.now(UTC),
        raw={"source": "browserbase_browser", "url_template": URL_TEMPLATE},
    )
