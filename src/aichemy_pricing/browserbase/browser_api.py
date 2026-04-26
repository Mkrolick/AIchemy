"""L3 Browser API path — Playwright + Browserbase Chrome session.

Use when L3 needs JavaScript execution: SPA vendors (Enamine, Cayman,
Sigma, Tocris) return their unhydrated shell to the Fetch path. Browser
API spins up a real Chrome session in the cloud, drives it via CDP, and
reads ``page.content()`` after hydration.

Each lookup is a one-shot session — no pooling. Cost: ~$0.10/hour billed
per minute, ~10s per lookup, ~$0.0003 each. Sessions close in a finally
block so an exception doesn't leak billable session time.

A vendor is supported only after empirical calibration of its
``WAIT_AFTER_LOAD_MS`` and parser regex; see ``browser_parsers/``.
"""

from __future__ import annotations

import logging

from aichemy_pricing.browserbase.browser_parsers import REGISTRY
from aichemy_pricing.browserbase.browser_session import browser_session
from aichemy_pricing.browserbase.client import _html_to_markdown
from aichemy_pricing.types import PriceQuote, VendorRef

log = logging.getLogger(__name__)


class BrowserbaseBrowserLookup:
    """L3 fallback that executes JavaScript via Browserbase Browser API."""

    name = "browserbase_browser"

    def __init__(
        self,
        api_key: str | None = None,
        project_id: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._project_id = project_id

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        parser = REGISTRY.get(ref.vendor)
        if parser is None:
            log.debug("no Browser API parser for vendor=%s; skipping", ref.vendor)
            return None
        url = parser.URL_TEMPLATE.format(sku=ref.sku)
        try:
            with browser_session(api_key=self._api_key, project_id=self._project_id) as page:
                if page is None:
                    return None  # API key not configured
                page.goto(url, wait_until="load")
                page.wait_for_timeout(parser.WAIT_AFTER_LOAD_MS)
                html = page.content()
        except Exception as exc:
            log.warning("Browser API navigation %s failed: %s", url, exc)
            return None
        markdown = _html_to_markdown(html)
        try:
            quote: PriceQuote | None = parser.parse(markdown, ref.sku)
            return quote
        except Exception as exc:
            log.warning("Browser API parser %s raised on sku=%s: %s", ref.vendor, ref.sku, exc)
            return None
