"""STUB: Browser API path — full Playwright/CDP automation.

Use when L3 needs to click a "show price" button, navigate paginated
listings, fill an institutional-account login, or otherwise interact with
the page beyond a single rendered fetch. Browserbase Browser API spins up
a cloud Chrome session billed per minute.

NOT IMPLEMENTED in v1. The Fetch API path (fetch_lookup.py) covers all
verified L3 vendors — no vendor in scope requires multi-step automation.
"""

from __future__ import annotations

from aichemy_pricing.types import PriceQuote, VendorRef


class BrowserbaseBrowserLookup:
    name = "browserbase_browser"

    def __init__(self) -> None:
        raise NotImplementedError(
            "BrowserbaseBrowserLookup: not implemented in v1. The Fetch API "
            "path (BrowserbaseFetchLookup) covers all verified L3 vendors. "
            "Build this only when a vendor needs multi-step browser interaction "
            "that a single Fetch call cannot satisfy."
        )

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        raise NotImplementedError
