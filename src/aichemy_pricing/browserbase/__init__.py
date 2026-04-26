"""L3 fallback layer — Browserbase Fetch + Browser APIs.

Public surface:

* ``BrowserbaseClient`` — one POST per page → rendered HTML→markdown (no JS)
* ``BrowserbaseFetchLookup`` — PriceLookup over the Fetch API (cheap, SSR vendors)
* ``BrowserbaseBrowserLookup`` — PriceLookup over a Playwright/CDP Chrome
  session (paid, JS-rendered SPA vendors)

Per-vendor parsers live under ``aichemy_pricing.browserbase.parsers`` (Fetch)
and ``aichemy_pricing.browserbase.browser_parsers`` (Browser API) — not
re-exported.
"""

from aichemy_pricing.browserbase.browser_api import BrowserbaseBrowserLookup
from aichemy_pricing.browserbase.client import BrowserbaseClient
from aichemy_pricing.browserbase.fetch_lookup import BrowserbaseFetchLookup

__all__ = [
    "BrowserbaseBrowserLookup",
    "BrowserbaseClient",
    "BrowserbaseFetchLookup",
]
