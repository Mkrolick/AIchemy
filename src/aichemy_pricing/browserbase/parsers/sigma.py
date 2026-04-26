"""Sigma-Aldrich rendered-markdown parser. The L2 path can't reach Sigma
because of Akamai (CLAIM-13); Browserbase's stealth + residential IP pool
gets through the Fetch API.

URL_TEMPLATE defaults to the `aldrich` brand prefix; SKUs that come from
PubChem SDF resolution already include the brand prefix as a literal
substring, so `{sku}` substitution works for non-aldrich brands too. Brand-
qualified routing is out of scope for v1.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aichemy_pricing.types import PriceQuote
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

URL_TEMPLATE = "https://www.sigmaaldrich.com/US/en/product/aldrich/{sku}"

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
        vendor="sigma",
        sku=sku,
        price=price,
        currency="USD",
        pack_size_g=pack_size_to_grams(size, unit),
        fetched_at=datetime.now(UTC),
        raw={"source": "browserbase_fetch", "url_template": URL_TEMPLATE},
    )
