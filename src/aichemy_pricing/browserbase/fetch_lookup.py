"""L3 PriceLookup that routes through Browserbase Fetch API.

Lookup flow:
  1. Look up the vendor's markdown parser in REGISTRY by ref.vendor.
  2. If no parser exists for this vendor → return None (debug log; not an
     error — caller should add a parser).
  3. Build the URL via parser.URL_TEMPLATE.format(sku=ref.sku).
  4. client.fetch_markdown(url) → markdown or None.
  5. parser.parse(markdown, sku) → PriceQuote or None.

Any exception from a parser is caught + logged + returns None — a parser
bug must not abort the whole chain.
"""

from __future__ import annotations

import logging

from aichemy_pricing.browserbase.client import BrowserbaseClient
from aichemy_pricing.browserbase.parsers import REGISTRY
from aichemy_pricing.types import PriceQuote, VendorRef

log = logging.getLogger(__name__)


class BrowserbaseFetchLookup:
    """L3 fallback: render the vendor product page via Browserbase Fetch API,
    parse the price out of the returned markdown."""

    name = "browserbase_fetch"

    def __init__(self, client: BrowserbaseClient | None = None) -> None:
        self._client = client or BrowserbaseClient()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        parser = REGISTRY.get(ref.vendor)
        if parser is None:
            log.debug("no L3 parser for vendor=%s; skipping", ref.vendor)
            return None
        url = parser.URL_TEMPLATE.format(sku=ref.sku)
        markdown = self._client.fetch_markdown(url)
        if markdown is None:
            return None
        try:
            quote: PriceQuote | None = parser.parse(markdown, ref.sku)
            return quote
        except Exception as exc:  # never let a parser bug abort the chain
            log.warning("L3 parser %s raised on sku=%s: %s", ref.vendor, ref.sku, exc)
            return None
