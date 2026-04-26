"""L3 fallback layer — Browserbase Fetch API.

Public surface is `BrowserbaseClient` (one POST per page → rendered markdown)
and `BrowserbaseFetchLookup` (the `PriceLookup` impl that the default chain
in sub-plan E composes after the L2 httpx vendors).

Per-vendor markdown parsers are an internal registry concern under
`aichemy_pricing.browserbase.parsers` — not re-exported.
"""

from aichemy_pricing.browserbase.client import BrowserbaseClient
from aichemy_pricing.browserbase.fetch_lookup import BrowserbaseFetchLookup

__all__ = ["BrowserbaseClient", "BrowserbaseFetchLookup"]
