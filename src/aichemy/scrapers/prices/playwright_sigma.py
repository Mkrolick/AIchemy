"""Playwright-based Sigma-Aldrich price scraper.

Uses a real headless Chromium so we inherit the session cookies and JS
execution the plain-httpx scrapers can't. Much slower per-request (seconds)
but passes anti-bot checks that Sigma's GraphQL+HTML require.

Usage in a subprocess / script — not the same lifecycle as the httpx
``PriceScraperBase``. We expose a ``scrape()`` helper that takes a SMILES
and returns a ``PriceQuote`` or None.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from aichemy.scrapers.prices.base import PriceQuote
from aichemy.scrapers.prices.pubchem import PubChemResolver

log = logging.getLogger(__name__)

# Match pack-size + unit inside Offer.description
_PACK = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|g|mg|ug|µg|ng|l|ml|ul|µl)\b",
    re.IGNORECASE,
)
_UNIT_TO_GRAMS = {
    "kg": 1000.0,
    "g": 1.0,
    "mg": 1e-3,
    "ug": 1e-6,
    "µg": 1e-6,
    "ng": 1e-9,
    "l": 1000.0,
    "ml": 1.0,
    "ul": 1e-3,
    "µl": 1e-3,
}


class PlaywrightSigmaScraper:
    """Headless-browser scraper for sigmaaldrich.com.

    Keeps a single browser context open across calls so we reuse cookies
    + fingerprint. Close with `.close()` when done.
    """

    vendor_name = "sigma_aldrich_playwright"

    def __init__(self, user_agent: str = "Mozilla/5.0 AIchemy-research") -> None:
        from playwright.sync_api import sync_playwright

        self._p = sync_playwright().start()
        self._browser = self._p.chromium.launch(headless=True)
        self._context = self._browser.new_context(user_agent=user_agent)
        self._page = self._context.new_page()
        self._pubchem = PubChemResolver()

    def close(self) -> None:
        self._context.close()
        self._browser.close()
        self._p.stop()
        self._pubchem.close()

    def scrape(self, smiles: str) -> PriceQuote | None:
        ids = self._pubchem.resolve(smiles)
        if ids is None:
            return None
        # Sigma's search accepts CAS and compound names.
        candidates: list[str] = []
        if ids.cas:
            candidates.append(ids.cas[0])
        if ids.iupac_name:
            candidates.append(ids.iupac_name)
        for syn in ids.synonyms[:5]:
            if syn not in candidates:
                candidates.append(syn)

        for query in candidates:
            url = (
                "https://www.sigmaaldrich.com/US/en/search/"
                + _url_encode(query)
                + "?focus=products&page=1&perpage=5&sort=relevance&term="
                + _url_encode(query)
                + "&type=product"
            )
            try:
                self._page.goto(url, timeout=30000, wait_until="networkidle")
            except Exception as exc:
                log.debug("sigma playwright: goto failed: %s", exc)
                continue

            # Grab the first product link from search results
            try:
                first_link = self._page.locator('a[href*="/product/"]').first.get_attribute(
                    "href", timeout=5000
                )
            except Exception:
                first_link = None
            if not first_link:
                continue
            if first_link.startswith("/"):
                product_url = "https://www.sigmaaldrich.com" + first_link
            else:
                product_url = first_link

            # Visit product page
            try:
                self._page.goto(product_url, timeout=30000, wait_until="networkidle")
            except Exception as exc:
                log.debug("sigma playwright: product goto failed: %s", exc)
                continue

            html = self._page.content()
            price_per_gram = _extract_sigma_price_per_gram(html)
            if price_per_gram is None:
                continue

            return PriceQuote(
                smiles=smiles,
                price_per_gram_usd=price_per_gram,
                vendor=self.vendor_name,
                source_url=product_url,
                fetched_at=datetime.now(UTC),
                extra={"query": query, "pubchem_cid": str(ids.cid)},
            )
        return None


def _url_encode(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


def _extract_sigma_price_per_gram(html: str) -> float | None:
    """Pull per-gram USD from Sigma's product-page JSON-LD."""
    pattern = re.compile(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    per_gram_prices: list[float] = []
    for m in pattern.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        for price, size in _iter_offer_prices(data):
            grams = _size_to_grams(size)
            if grams is None or grams <= 0:
                continue
            per_gram = price / grams
            if 0.0001 < per_gram < 100_000:
                per_gram_prices.append(per_gram)
    if not per_gram_prices:
        # Fallback: scan full HTML for price + size proximity pairs.
        for m in re.finditer(
            r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?.{0,200}?"description"\s*:\s*"([^"]+)"',
            html,
            re.DOTALL,
        ):
            try:
                price = float(m.group(1))
            except ValueError:
                continue
            grams = _size_to_grams(m.group(2))
            if grams and grams > 0:
                pg = price / grams
                if 0.0001 < pg < 100_000:
                    per_gram_prices.append(pg)

    if not per_gram_prices:
        return None
    per_gram_prices.sort()
    n = len(per_gram_prices)
    return (
        per_gram_prices[n // 2]
        if n % 2 == 1
        else (per_gram_prices[n // 2 - 1] + per_gram_prices[n // 2]) / 2.0
    )


def _iter_offer_prices(node):
    if isinstance(node, dict):
        typ = node.get("@type")
        types = [typ] if isinstance(typ, str) else list(typ or [])
        if "Offer" in types or "AggregateOffer" in types:
            price = node.get("price") or node.get("lowPrice")
            currency = node.get("priceCurrency") or "USD"
            desc = node.get("description") or node.get("name") or ""
            if price is not None and str(currency).upper() == "USD":
                import contextlib

                with contextlib.suppress(TypeError, ValueError):
                    yield float(price), str(desc)
        for v in node.values():
            yield from _iter_offer_prices(v)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_offer_prices(item)


def _size_to_grams(size_str: str) -> float | None:
    m = _PACK.search(size_str)
    if not m:
        return None
    try:
        qty = float(m.group(1))
    except ValueError:
        return None
    factor = _UNIT_TO_GRAMS.get(m.group(2).lower(), 0.0)
    if factor <= 0:
        return None
    return qty * factor
