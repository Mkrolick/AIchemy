"""Shared HTTP client factories.

Two flavours:
 - `make_plain_client()` — vanilla httpx with a desktop Chrome User-Agent.
   Used for Tier 1 (Fluorochem JSON, Molbase, Tocris) and Tier 2 (Enamine,
   Cayman, ChemCruz) where Cloudflare/Akamai are absent or pass with a UA.
 - `make_cf_client()` — curl_cffi impersonating Chrome 124. Used for Tier 3
   (MedChemExpress) where Cloudflare requires a real-browser TLS fingerprint.

Per CLAIM-15: MCE 403s any client without a real-browser TLS fingerprint,
even with the right User-Agent header.
"""

from __future__ import annotations

import httpx

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def make_plain_client() -> httpx.Client:
    return httpx.Client(
        headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True
    )


def make_cf_client():  # type: ignore[no-untyped-def]  # curl_cffi has no public type stubs
    """Returns a curl_cffi Session impersonating Chrome 124's TLS fingerprint."""
    from curl_cffi import requests as cf_requests

    return cf_requests.Session(impersonate="chrome124")
