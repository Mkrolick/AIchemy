"""Registry: vendor name → parser module.

Keys must match the value each parser writes into `PriceQuote.vendor`. The
fetch-lookup tests round-trip this invariant.
"""

from __future__ import annotations

from types import ModuleType

from aichemy_pricing.browserbase.parsers import (
    cayman,
    chemcruz,
    enamine,
    molbase,
    sigma,
    tocris,
)

REGISTRY: dict[str, ModuleType] = {
    "sigma": sigma,
    "enamine": enamine,
    "cayman": cayman,
    "chemcruz": chemcruz,
    "tocris": tocris,
    "molbase": molbase,
}
