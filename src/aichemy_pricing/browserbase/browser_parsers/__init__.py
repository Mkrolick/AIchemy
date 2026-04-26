"""Registry: vendor name → browser-parser config.

A browser parser is a module exposing:

* ``URL_TEMPLATE``: ``"https://...{sku}..."`` formatted with the VendorRef sku
* ``WAIT_AFTER_LOAD_MS``: milliseconds to wait after ``load`` event for SPA
  hydration before reading ``page.content()``. SPAs almost never reach
  ``networkidle``; use a fixed wait calibrated per vendor.
* ``parse(markdown, sku)``: same shape as ``parsers/`` modules — a
  PriceQuote or None. Browser parsers consume html2text-converted page
  HTML, so the same regex parsers can in principle be reused once the
  hydrated content is in scope.

Only vendors empirically validated on the Browser API live here. Adding
a vendor: probe with the live capture script, calibrate
WAIT_AFTER_LOAD_MS until prices appear, write the parser, register here.
"""

from __future__ import annotations

from types import ModuleType

from aichemy_pricing.browserbase.browser_parsers import enamine

REGISTRY: dict[str, ModuleType] = {
    "enamine": enamine,
}
