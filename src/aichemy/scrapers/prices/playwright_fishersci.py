"""Playwright-based Fisher Scientific price scraper.

fishersci.com search returns real product URLs in plain HTML. Product pages
load prices via JS; a headless browser lets us wait for them to render.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import quote

from aichemy.scrapers.prices.base import PriceQuote
from aichemy.scrapers.prices.pubchem import PubChemResolver

log = logging.getLogger(__name__)

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


class PlaywrightFisherScraper:
    vendor_name = "fisher_scientific"

    def __init__(self, user_agent: str | None = None) -> None:
        from playwright.sync_api import sync_playwright

        self._p = sync_playwright().start()
        self._browser = self._p.chromium.launch(headless=True)
        ua = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._context = self._browser.new_context(user_agent=ua)
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
        candidates: list[str] = []
        if ids.iupac_name:
            candidates.append(ids.iupac_name)
        for syn in ids.synonyms[:3]:
            if syn not in candidates:
                candidates.append(syn)
        if ids.cas:
            candidates.append(ids.cas[0])

        for query in candidates:
            q = quote(query, safe="")
            search_url = f"https://www.fishersci.com/us/en/catalog/search/products?keyword={q}"
            try:
                # Use 'domcontentloaded' instead of 'load'/'networkidle' — faster;
                # search results are in the initial HTML.
                self._page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
            except Exception as exc:
                log.debug("fisher: search goto failed: %s", exc)
                continue

            # Find product hrefs on search results
            try:
                hrefs = self._page.locator('a[href*="/shop/products/"]').all()
            except Exception:
                hrefs = []
            if not hrefs:
                continue
            product_url = None
            for h in hrefs[:5]:
                try:
                    href = h.get_attribute("href", timeout=2000)
                except Exception:
                    continue
                if href:
                    product_url = (
                        "https://www.fishersci.com" + href if href.startswith("/") else href
                    )
                    break
            if not product_url:
                continue

            try:
                self._page.goto(product_url, timeout=20000, wait_until="domcontentloaded")
            except Exception as exc:
                log.debug("fisher: product goto failed: %s", exc)
                continue

            # Brief wait for prices to appear in JS-rendered product page
            import contextlib

            with contextlib.suppress(Exception):
                self._page.wait_for_selector("text=/\\$\\s*\\d/", timeout=5000)

            html = self._page.content()
            price_per_gram = _extract_fisher_price_per_gram(html)
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


def _extract_fisher_price_per_gram(html: str) -> float | None:
    # Fisher's product pages have pack size + USD price in proximity.
    # Find all $ prices then look for pack sizes within 200 chars.
    price_matches = list(re.finditer(r"\$\s*([\d,]+(?:\.\d{2})?)", html))
    per_gram_prices: list[float] = []
    for pm in price_matches:
        try:
            price = float(pm.group(1).replace(",", ""))
        except ValueError:
            continue
        # Scan neighborhood for pack size
        start = max(0, pm.start() - 400)
        end = min(len(html), pm.end() + 400)
        nbhd = html[start:end]
        size_match = _PACK.search(nbhd)
        if not size_match:
            continue
        try:
            qty = float(size_match.group(1))
        except ValueError:
            continue
        factor = _UNIT_TO_GRAMS.get(size_match.group(2).lower(), 0.0)
        if factor <= 0:
            continue
        grams = qty * factor
        if grams <= 0:
            continue
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
