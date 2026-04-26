"""Registry: vendor name → parser module.

Keys must match the value each parser writes into `PriceQuote.vendor`. The
fetch-lookup tests round-trip this invariant.

Browserbase Fetch does not execute JavaScript, so SPA-only vendors return
their unhydrated shell (Sigma, Enamine, Cayman) or get blocked at the
edge (Tocris on Akamai, Molbase on >10s timeout). Only ChemCruz returns
SSR HTML with prices visible to the Fetch path. The other parsers live
on disk for the Browser API path (which DOES execute JavaScript) but are
not registered here.
"""

from __future__ import annotations

from types import ModuleType

from aichemy_pricing.browserbase.parsers import chemcruz

REGISTRY: dict[str, ModuleType] = {
    "chemcruz": chemcruz,
}
