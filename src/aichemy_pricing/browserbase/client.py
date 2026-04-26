"""Thin httpx wrapper around Browserbase's Fetch API.

Mechanics: one HTTPS POST to https://api.browserbase.com/v1/fetch with
`{"url": "..."}`. Returns the upstream HTTP response as JSON:

    {"id": "...", "statusCode": 200, "headers": {...},
     "content": "<!doctype html>...", ...}

The `content` field is the raw HTML — Fetch DOES NOT execute JavaScript.
We convert HTML → markdown via html2text so downstream parsers see a
stable text representation. SPA-only vendors (Sigma, Enamine, Cayman,
Tocris) return their unhydrated shell here and must be handled by the
Browser API path instead.

Auth via X-BB-API-Key from BROWSERBASE_API_KEY env var.

When the env var is unset, `is_configured()` returns False and
`fetch_markdown()` no-ops (returns None) instead of raising — this lets
the package be used without the L3 layer when the user hasn't provisioned
a Browserbase account.

Per https://www.browserbase.com/pricing : Fetch is $1/1K calls on Developer,
$0.50/1K on Startup. With proxies: $4/1K. We don't enable the proxy variant
in v1 — the default Fetch already includes residential IPs in their pool.
"""

from __future__ import annotations

import logging
import os

import html2text
import httpx

log = logging.getLogger(__name__)

_FETCH_URL = "https://api.browserbase.com/v1/fetch"
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _html_to_markdown(html: str) -> str:
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    h.ignore_emphasis = True
    return h.handle(html)


class BrowserbaseClient:
    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("BROWSERBASE_API_KEY")
        self._client = client or httpx.Client(timeout=_TIMEOUT)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def fetch_markdown(self, url: str) -> str | None:
        """POST to Fetch API, return HTML-as-markdown or None on any failure.

        Returns None (not raises) for: no API key, HTTP error, Browserbase
        non-200, upstream non-2xx, malformed JSON, empty content. The L3
        layer treats every miss as "this vendor didn't return a price"
        rather than aborting the whole chain.
        """
        if not self._api_key:
            log.debug("BrowserbaseClient: BROWSERBASE_API_KEY unset; skipping %s", url)
            return None
        try:
            resp = self._client.post(
                _FETCH_URL,
                headers={
                    "X-BB-API-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={"url": url},
            )
        except httpx.HTTPError as exc:
            log.warning("Browserbase fetch %s: HTTP error %s", url, exc)
            return None
        if resp.status_code != 200:
            log.warning("Browserbase fetch %s: status %d", url, resp.status_code)
            return None
        try:
            data = resp.json()
        except ValueError:
            log.warning("Browserbase fetch %s: non-JSON response", url)
            return None
        upstream_status = data.get("statusCode")
        if not isinstance(upstream_status, int) or not 200 <= upstream_status < 300:
            log.warning("Browserbase fetch %s: upstream status %r", url, upstream_status)
            return None
        html = data.get("content")
        if not isinstance(html, str) or not html:
            log.warning("Browserbase fetch %s: empty/missing content", url)
            return None
        return _html_to_markdown(html)
