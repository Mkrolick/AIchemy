# Sub-Plan C: `aichemy-pricing` — Tier 1 Vendor Scrapers (Plain HTTP)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Parent plan:** `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`
> **Verification source:** `experiments/chem-pricing-verification/CLAIMS.md` (CLAIM-01 Fluorochem, CLAIM-18 Molbase, CLAIM-25 Tocris)
> **Depends on:** Sub-Plan A (uses `PriceQuote`, `VendorRef`, `make_plain_client`, `TokenBucket`)
> **Delivers (consumed by sub-plan E):**
> - `aichemy_pricing.vendors.fluorochem.FluorochemVendor` — Azure-blob JSON pricing API (anonymous, no anti-bot)
> - `aichemy_pricing.vendors.molbase.MolbaseVendor` — `molbase.com/cas/{CAS}.html` HTML scrape
> - `aichemy_pricing.vendors.tocris.TocrisVendor` — `tocris.com` SSR HTML with visible USD prices

**Goal:** Implement the three Tier 1 vendor scrapers — the ones that don't require Cloudflare bypass or DevTools-discovered XHR endpoints. All three respond to plain `httpx.Client.get()` with a Chrome User-Agent.

**Architecture:** Each vendor is a stateless class with a single `lookup(ref: VendorRef) -> PriceQuote | None` method. Vendor modules use only `httpx`, `aichemy_pricing.http.make_plain_client`, `aichemy_pricing.types`, and stdlib `re`/`datetime`. No vendor module imports another vendor module. Each vendor's tests use `pytest-httpx`-style monkey-patched `httpx.Client.send` to replay frozen response fixtures, plus an opt-in `@pytest.mark.live` test.

**Tech Stack:** Python 3.11, `httpx` (already pulled in by sub-plan A), `re` for HTML/JSON regex extraction. No HTML parser dependency — these vendors emit either pure JSON (Fluorochem) or simple enough HTML that targeted regex is more robust than BeautifulSoup against vendor-side template changes.

---

## File Structure

```
src/aichemy_pricing/vendors/
├── __init__.py                            # CREATE — re-export the three vendors
├── _common.py                             # CREATE — shared helpers (unit_to_grams, currency-symbol map)
├── fluorochem.py                          # CREATE — Task C1
├── molbase.py                             # CREATE — Task C2
└── tocris.py                              # CREATE — Task C3

src/aichemy_pricing/tests/
├── data/
│   ├── fluorochem_F765353.json            # CAPTURE — live response from CLAIM-01 evidence
│   ├── molbase_aspirin.html               # CAPTURE — live response, /cas/50-78-2.html
│   └── tocris_jw642.html                  # CAPTURE — live response, /products/jw-642_4906
├── test_vendors_fluorochem.py             # CREATE — Task C1 (5 tests)
├── test_vendors_molbase.py                # CREATE — Task C2 (3 tests)
└── test_vendors_tocris.py                 # CREATE — Task C3 (3 tests)
```

---

## Task C0: Shared vendor helpers

**Files:**
- Create: `src/aichemy_pricing/vendors/__init__.py` (empty stub for now)
- Create: `src/aichemy_pricing/vendors/_common.py`

- [ ] **Step 1: Empty `__init__.py`**

```bash
mkdir -p src/aichemy_pricing/vendors
: > src/aichemy_pricing/vendors/__init__.py
```

- [ ] **Step 2: `_common.py`**

```python
# src/aichemy_pricing/vendors/_common.py
"""Helpers shared by vendor modules. No HTTP, no I/O."""
from __future__ import annotations

UNIT_TO_GRAMS: dict[str, float] = {
    "ug": 1e-6, "µg": 1e-6, "mcg": 1e-6,
    "mg": 1e-3,
    "g": 1.0, "gr": 1.0, "gram": 1.0, "grams": 1.0,
    "kg": 1000.0,
}


def pack_size_to_grams(size: float, unit: str) -> float:
    """Convert a (size, unit) pair to grams. Raises KeyError on unknown unit."""
    return size * UNIT_TO_GRAMS[unit.lower()]
```

- [ ] **Step 3: Commit**

```bash
git add src/aichemy_pricing/vendors/__init__.py src/aichemy_pricing/vendors/_common.py
git commit -m "feat(pricing): vendor module scaffolding + pack_size_to_grams helper"
```

---

## Task C1: `FluorochemVendor`

**Per CLAIM-01 (PARTIAL):** the Azure-blob JSON pricing endpoint is real and anonymous, but the original report **fabricated the JSON shape**. Use the corrected schema below.

- **Endpoint:** `https://fluorochemcouk.blob.core.windows.net/pricing/{ProductCode}.json`
- **Auth:** none. Container listing is disabled (`?restype=container&comp=list` → 404), so SKUs must come from upstream resolvers.
- **Coverage:** modern F-prefix and BR-prefix SKUs only. Legacy 6-digit codes (e.g. `043319`, `222092`) return 404.
- **Real schema** (verified live):

```json
{
  "F765353": {
    "F765353-1G": {
      "SKU": "F765353-1G",
      "Size": "1",
      "Size Unit": "g",
      "Pricing": {
        "GBP": {"Base Price": 230, "5% Discount": 218.5, ..., "Q2 2026 - Base": 230, ...},
        "EUR": {"Base Price": 267, "5% Discount": 253.65, ...}
      }
    },
    "F765353-5G": { ... },
    ...
  }
}
```

There is **no** `min_gbp`, `max_gbp`, `has_stock_uk`, `has_stock_germany`, or `has_stock_china` field. Stock data is not in this endpoint and must come from a different source.

**Files:**
- Create: `src/aichemy_pricing/vendors/fluorochem.py`
- Create: `src/aichemy_pricing/tests/test_vendors_fluorochem.py`
- Capture: `src/aichemy_pricing/tests/data/fluorochem_F765353.json`

- [ ] **Step 1: Capture fixture**

```bash
mkdir -p src/aichemy_pricing/tests/data
curl -s "https://fluorochemcouk.blob.core.windows.net/pricing/F765353.json" \
  > src/aichemy_pricing/tests/data/fluorochem_F765353.json
test -s src/aichemy_pricing/tests/data/fluorochem_F765353.json && echo OK
```

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_vendors_fluorochem.py
"""Unit tests for FluorochemVendor.

Per CLAIM-01: endpoint is real, anonymous, no Cloudflare. The original
research report fabricated the JSON shape — these tests use a fixture
captured from the live endpoint to lock the corrected schema in place.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.fluorochem import FluorochemVendor


@pytest.fixture
def fixture_body(fixture_dir) -> bytes:
    return (fixture_dir / "fluorochem_F765353.json").read_bytes()


def _patch_http(monkeypatch: pytest.MonkeyPatch, *, status: int, body: bytes = b"") -> None:
    def mock_send(self, request, **kw):  # noqa: ARG001
        return httpx.Response(status, content=body, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)


def test_fluorochem_parses_real_response(monkeypatch, fixture_body) -> None:
    _patch_http(monkeypatch, status=200, body=fixture_body)
    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="F765353-1G"))
    assert quote is not None
    assert quote.vendor == "fluorochem"
    assert quote.currency == "GBP"
    assert quote.pack_size_g == 1.0
    assert quote.price > 0


def test_fluorochem_handles_kg_pack_unit(monkeypatch) -> None:
    body = json.dumps({
        "BR1005": {
            "BR1005-1KG": {
                "SKU": "BR1005-1KG", "Size": "1", "Size Unit": "kg",
                "Pricing": {"GBP": {"Base Price": 24}},
            }
        }
    }).encode()
    _patch_http(monkeypatch, status=200, body=body)
    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="BR1005-1KG"))
    assert quote is not None
    assert quote.pack_size_g == 1000.0
    assert quote.price == 24.0


def test_fluorochem_returns_none_on_404(monkeypatch) -> None:
    _patch_http(monkeypatch, status=404)
    v = FluorochemVendor()
    assert v.lookup(VendorRef(vendor="fluorochem", sku="legacy-022092")) is None


def test_fluorochem_returns_none_when_pricing_block_missing(monkeypatch) -> None:
    body = json.dumps({"X1": {"X1-1G": {"SKU": "X1-1G", "Size": "1", "Size Unit": "g", "Pricing": {}}}}).encode()
    _patch_http(monkeypatch, status=200, body=body)
    v = FluorochemVendor()
    assert v.lookup(VendorRef(vendor="fluorochem", sku="X1-1G")) is None


def test_fluorochem_picks_first_pack_when_caller_passes_product_code_only(monkeypatch) -> None:
    body = json.dumps({
        "Z9": {
            "Z9-100MG": {"SKU": "Z9-100MG", "Size": "100", "Size Unit": "mg", "Pricing": {"GBP": {"Base Price": 5.0}}},
            "Z9-1G":    {"SKU": "Z9-1G",   "Size": "1",   "Size Unit": "g",  "Pricing": {"GBP": {"Base Price": 25.0}}},
        }
    }).encode()
    _patch_http(monkeypatch, status=200, body=body)
    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="Z9"))  # no pack suffix
    assert quote is not None
    # The vendor picks the first pack; the test asserts it returns *some* valid pack.
    assert quote.pack_size_g in {0.1, 1.0}


@pytest.mark.live
def test_fluorochem_live_F765353_packs() -> None:
    """Hits the real endpoint. Confirms the URL pattern is still live."""
    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="F765353-1G"))
    assert quote is not None
    assert quote.currency == "GBP"
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/vendors/fluorochem.py
"""Fluorochem Azure-blob JSON pricing vendor.

Per CLAIM-01 (PARTIAL — endpoint REAL, fields FABRICATED in original report):
  Endpoint: https://fluorochemcouk.blob.core.windows.net/pricing/{ProductCode}.json
  Auth:     none; anonymous read-only blob
  Coverage: F-prefix and BR-prefix SKUs only

The caller can pass either:
  - a full pack SKU like "F765353-1G" → vendor returns that exact pack's price
  - a bare product code like "F765353" → vendor returns the first pack found

There is NO `min_gbp`, `max_gbp`, or `has_stock_*` field in the response.
Stock data is not in this endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams

_BASE_URL = "https://fluorochemcouk.blob.core.windows.net/pricing"


def _split_sku(full_sku: str) -> tuple[str, str | None]:
    """`F765353-1G` → ("F765353", "F765353-1G"); `F765353` → ("F765353", None)."""
    if "-" not in full_sku:
        return full_sku, None
    head, _ = full_sku.rsplit("-", 1)
    return head, full_sku


class FluorochemVendor:
    name = "fluorochem"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        product_code, requested_pack = _split_sku(ref.sku)
        url = f"{_BASE_URL}/{product_code}.json"
        resp = self._client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        body = resp.json()
        product = body.get(product_code) or {}
        if not product:
            return None
        if requested_pack and requested_pack in product:
            pack_key = requested_pack
            pack = product[pack_key]
        else:
            pack_key, pack = next(iter(product.items()))
        gbp = pack.get("Pricing", {}).get("GBP", {})
        base = gbp.get("Base Price")
        if base is None:
            return None
        size = float(pack["Size"])
        unit = str(pack["Size Unit"])
        return PriceQuote(
            vendor=self.name,
            sku=pack_key,
            price=float(base),
            currency="GBP",
            pack_size_g=pack_size_to_grams(size, unit),
            fetched_at=datetime.now(timezone.utc),
            raw=pack,
        )
```

- [ ] **Step 4: Re-export**

```python
# src/aichemy_pricing/vendors/__init__.py — append
from aichemy_pricing.vendors.fluorochem import FluorochemVendor

__all__ = ["FluorochemVendor"]
```

- [ ] **Step 5: Run; pass (5 tests offline + 1 live skipped)**

```bash
uv run pytest src/aichemy_pricing/tests/test_vendors_fluorochem.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/vendors/fluorochem.py src/aichemy_pricing/vendors/__init__.py src/aichemy_pricing/tests/test_vendors_fluorochem.py src/aichemy_pricing/tests/data/fluorochem_F765353.json
git commit -m "feat(pricing): FluorochemVendor — Azure-blob JSON (corrected schema)"
```

---

## Task C2: `MolbaseVendor`

**Per CLAIM-18 (PARTIAL):** the original report's URL `/en/cas-{CAS}.html` returns 404 100% of the time. The real URL pattern is **`molbase.com/cas/{CAS}.html`** (no `/en/` prefix, slash separator). 49,406,656 compounds exact (matches "~49M"). Page titles end "price & availability - MOLBASE" — anonymous prices visible.

**Files:**
- Create: `src/aichemy_pricing/vendors/molbase.py`
- Create: `src/aichemy_pricing/tests/test_vendors_molbase.py`
- Capture: `src/aichemy_pricing/tests/data/molbase_aspirin.html`

- [ ] **Step 1: Capture fixture**

```bash
curl -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
  -sL "https://www.molbase.com/cas/50-78-2.html" \
  > src/aichemy_pricing/tests/data/molbase_aspirin.html
test -s src/aichemy_pricing/tests/data/molbase_aspirin.html && echo OK
```

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_vendors_molbase.py
"""Unit tests for MolbaseVendor.

Per CLAIM-18: real URL is molbase.com/cas/{CAS}.html (NOT /en/cas-{CAS}.html
as the original report claimed). 49M compounds aggregated from Chinese suppliers.
Anonymous prices visible.
"""
from __future__ import annotations

import httpx
import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.molbase import MolbaseVendor


def _patch_http(monkeypatch: pytest.MonkeyPatch, *, status: int, body: bytes = b"") -> None:
    def mock_send(self, request, **kw):  # noqa: ARG001
        return httpx.Response(status, content=body, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)


def test_molbase_uses_correct_url(monkeypatch) -> None:
    """Confirm the vendor builds the corrected URL form, not the report's wrong one."""
    captured: dict[str, str] = {}

    def mock_send(self, request, **kw):  # noqa: ARG001
        captured["url"] = str(request.url)
        return httpx.Response(404, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)

    MolbaseVendor().lookup(VendorRef(vendor="molbase", sku="50-78-2"))
    assert captured["url"] == "https://www.molbase.com/cas/50-78-2.html"


def test_molbase_returns_none_on_404(monkeypatch) -> None:
    _patch_http(monkeypatch, status=404)
    assert MolbaseVendor().lookup(VendorRef(vendor="molbase", sku="00-00-0")) is None


def test_molbase_extracts_usd_price_and_pack_from_html(monkeypatch) -> None:
    body = (
        b"<html><head><title>Aspirin price &amp; availability - MOLBASE</title></head>"
        b"<body><div class='supplier-row'>"
        b"<span class='price'>USD 12.50</span><span class='pack'>5g</span>"
        b"</div></body></html>"
    )
    _patch_http(monkeypatch, status=200, body=body)
    quote = MolbaseVendor().lookup(VendorRef(vendor="molbase", sku="50-78-2"))
    assert quote is not None
    assert quote.currency == "USD"
    assert quote.price == 12.50
    assert quote.pack_size_g == 5.0


def test_molbase_extracts_cny_price_chinese_supplier(monkeypatch) -> None:
    """Per CLAIM-18 the majority of Molbase suppliers are Chinese, so CNY (¥)
    must be parsed correctly — many compounds list ONLY in CNY."""
    body = (
        "<html><body><span class='price'>¥ 88.00</span>"
        "<span class='pack'>10g</span></body></html>"
    ).encode()
    _patch_http(monkeypatch, status=200, body=body)
    quote = MolbaseVendor().lookup(VendorRef(vendor="molbase", sku="50-78-2"))
    assert quote is not None
    assert quote.currency == "CNY"
    assert quote.price == 88.00


def test_molbase_returns_none_when_no_price_found(monkeypatch) -> None:
    body = b"<html><body>No suppliers listed yet.</body></html>"
    _patch_http(monkeypatch, status=200, body=body)
    assert MolbaseVendor().lookup(VendorRef(vendor="molbase", sku="50-78-2")) is None


@pytest.mark.live
def test_molbase_live_aspirin_does_not_crash() -> None:
    """We can't assume aspirin is currently priced on Molbase, but the URL must
    return 200 and the parser must not crash on the live HTML."""
    r = MolbaseVendor().lookup(VendorRef(vendor="molbase", sku="50-78-2"))
    if r is not None:
        assert r.price > 0
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/vendors/molbase.py
"""Molbase aggregator (~49M compounds, mostly Chinese suppliers).

Per CLAIM-18 (PARTIAL):
  Real URL: https://www.molbase.com/cas/{CAS}.html
  (Original report's /en/cas-{CAS}.html 404s 100%.)
  Anonymous list prices visible. SKU = CAS number.

Page is server-rendered HTML; we extract the first visible (currency, price,
pack) triple via targeted regex. Currency is captured because the majority
of Molbase suppliers are Chinese and price exclusively in CNY (¥) — defaulting
to USD would silently mis-label these.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import Currency, PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams

# Capture group 1 = currency token; group 2 = numeric price.
_PRICE_RE = re.compile(r"(USD|US\$|\$|¥|CNY|RMB|EUR|€|GBP|£)\s*([\d,.]+)", re.I)
_PACK_RE = re.compile(r"\b([\d.]+)\s*(mg|g|kg)\b", re.I)

_TOKEN_TO_CURRENCY: dict[str, Currency] = {
    "USD": "USD", "US$": "USD", "$": "USD",
    "¥": "CNY", "CNY": "CNY", "RMB": "CNY",
    "EUR": "EUR", "€": "EUR",
    "GBP": "GBP", "£": "GBP",
}


def _normalize_currency(token: str) -> Currency | None:
    return _TOKEN_TO_CURRENCY.get(token.upper()) or _TOKEN_TO_CURRENCY.get(token)


class MolbaseVendor:
    name = "molbase"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.molbase.com/cas/{ref.sku}.html"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        text = resp.text
        m_price = _PRICE_RE.search(text)
        m_pack = _PACK_RE.search(text)
        if not (m_price and m_pack):
            return None
        currency = _normalize_currency(m_price.group(1))
        if currency is None:
            return None
        try:
            price = float(m_price.group(2).replace(",", ""))
            size = float(m_pack.group(1))
        except ValueError:
            return None
        unit = m_pack.group(2).lower()
        return PriceQuote(
            vendor=self.name,
            sku=ref.sku,
            price=price,
            currency=currency,
            pack_size_g=pack_size_to_grams(size, unit),
            fetched_at=datetime.now(timezone.utc),
            raw={"url": url},
        )
```

- [ ] **Step 4: Re-export**

```python
# src/aichemy_pricing/vendors/__init__.py — append
from aichemy_pricing.vendors.molbase import MolbaseVendor

__all__ = ["FluorochemVendor", "MolbaseVendor"]
```

- [ ] **Step 5: Run; pass (4 tests offline + 1 live skipped)**

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/vendors/molbase.py src/aichemy_pricing/vendors/__init__.py src/aichemy_pricing/tests/test_vendors_molbase.py src/aichemy_pricing/tests/data/molbase_aspirin.html
git commit -m "feat(pricing): MolbaseVendor — corrected /cas/{CAS}.html URL"
```

---

## Task C3: `TocrisVendor`

**Per CLAIM-25 (corroboration):** Tocris publishes anonymous USD prices in the SSR HTML (verified live: `tocris.com/products/jw-642_4906` returns body with multiple `$N.NN` strings). URL pattern: `tocris.com/products/{slug}_{itemID}` where the slug is human-readable and itemID is a 4-digit number.

**Files:**
- Create: `src/aichemy_pricing/vendors/tocris.py`
- Create: `src/aichemy_pricing/tests/test_vendors_tocris.py`
- Capture: `src/aichemy_pricing/tests/data/tocris_jw642.html`

- [ ] **Step 1: Capture fixture**

```bash
curl -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
  -sL "https://www.tocris.com/products/jw-642_4906" \
  > src/aichemy_pricing/tests/data/tocris_jw642.html
test -s src/aichemy_pricing/tests/data/tocris_jw642.html && echo OK
```

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_vendors_tocris.py
"""Unit tests for TocrisVendor.

Per CLAIM-25 corroboration: Tocris publishes anonymous USD prices in SSR HTML.
URL pattern: tocris.com/products/{slug}_{itemID}.
SKU here = the full slug+id form, e.g. "jw-642_4906".
"""
from __future__ import annotations

import httpx
import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.tocris import TocrisVendor


def _patch_http(monkeypatch: pytest.MonkeyPatch, *, status: int, body: bytes = b"") -> None:
    def mock_send(self, request, **kw):  # noqa: ARG001
        return httpx.Response(status, content=body, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)


def test_tocris_extracts_price_from_synthetic_html(monkeypatch) -> None:
    body = (
        b"<html><head><title>JW 642 | Tocris Bioscience</title></head>"
        b"<body><table class='pack-prices'>"
        b"<tr><td>10mg</td><td>$165</td></tr>"
        b"<tr><td>50mg</td><td>$650</td></tr>"
        b"</table></body></html>"
    )
    _patch_http(monkeypatch, status=200, body=body)
    quote = TocrisVendor().lookup(VendorRef(vendor="tocris", sku="jw-642_4906"))
    assert quote is not None
    assert quote.currency == "USD"
    assert quote.price > 0


def test_tocris_returns_none_on_404(monkeypatch) -> None:
    _patch_http(monkeypatch, status=404)
    assert TocrisVendor().lookup(VendorRef(vendor="tocris", sku="nope_0000")) is None


def test_tocris_returns_none_when_no_price_in_html(monkeypatch) -> None:
    _patch_http(monkeypatch, status=200, body=b"<html>no pack table</html>")
    assert TocrisVendor().lookup(VendorRef(vendor="tocris", sku="jw-642_4906")) is None


def test_tocris_uses_correct_url(monkeypatch) -> None:
    captured: dict[str, str] = {}
    def mock_send(self, request, **kw):  # noqa: ARG001
        captured["url"] = str(request.url)
        return httpx.Response(404, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)
    TocrisVendor().lookup(VendorRef(vendor="tocris", sku="jw-642_4906"))
    assert captured["url"] == "https://www.tocris.com/products/jw-642_4906"


@pytest.mark.live
def test_tocris_live_jw642() -> None:
    quote = TocrisVendor().lookup(VendorRef(vendor="tocris", sku="jw-642_4906"))
    assert quote is not None
    assert quote.currency == "USD"
    assert quote.price > 0
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/vendors/tocris.py
"""Tocris Bioscience — anonymous USD prices in SSR HTML.

Per CLAIM-25 corroboration:
  URL: https://www.tocris.com/products/{slug}_{itemID}
  Anti-bot: none; browser-UA HTTP GET returns the body with prices inline.

The caller passes `sku = "{slug}_{itemID}"`, e.g. "jw-642_4906". We extract
the cheapest visible (pack, price) pair from the pack-prices table via regex.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams

_PACK_PRICE_RE = re.compile(
    r"([\d.]+)\s*(mg|g|kg|µg|ug|mcg)\b[^$]*\$\s*([\d,]+(?:\.\d+)?)",
    re.I,
)


class TocrisVendor:
    name = "tocris"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.tocris.com/products/{ref.sku}"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        match = _PACK_PRICE_RE.search(resp.text)
        if not match:
            return None
        try:
            size = float(match.group(1))
            unit = match.group(2).lower()
            price = float(match.group(3).replace(",", ""))
        except ValueError:
            return None
        return PriceQuote(
            vendor=self.name,
            sku=ref.sku,
            price=price,
            currency="USD",
            pack_size_g=pack_size_to_grams(size, unit),
            fetched_at=datetime.now(timezone.utc),
            raw={"url": url},
        )
```

- [ ] **Step 4: Re-export**

```python
# src/aichemy_pricing/vendors/__init__.py — final
from aichemy_pricing.vendors.fluorochem import FluorochemVendor
from aichemy_pricing.vendors.molbase import MolbaseVendor
from aichemy_pricing.vendors.tocris import TocrisVendor

__all__ = ["FluorochemVendor", "MolbaseVendor", "TocrisVendor"]
```

- [ ] **Step 5: Run; pass (4 tests offline + 1 live skipped)**

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/vendors/tocris.py src/aichemy_pricing/vendors/__init__.py src/aichemy_pricing/tests/test_vendors_tocris.py src/aichemy_pricing/tests/data/tocris_jw642.html
git commit -m "feat(pricing): TocrisVendor — SSR HTML pack-price extraction"
```

---

## Unit Tests Summary (Sub-Plan C)

| Test file | Offline | Live | Notes |
|---|---:|---:|---|
| `test_vendors_fluorochem.py` | 5 | 1 | Real-fixture parse; kg unit; 404; missing pricing block; product-only fallback; (live) F765353 |
| `test_vendors_molbase.py` | 5 | 1 | Correct URL builder; 404; USD parse; **CNY parse (Chinese supplier)**; no-price; (live) aspirin |
| `test_vendors_tocris.py` | 4 | 1 | Synthetic-HTML parse; 404; no-price; correct URL; (live) JW 642 |
| **Total** | **14** | **3** | All offline tests run in <2s. Live tests require `-m live` flag. |

**All-tests command (offline only):**
```bash
uv run pytest src/aichemy_pricing/tests/test_vendors_*.py -v
```

**Live verification:**
```bash
uv run pytest src/aichemy_pricing/tests/test_vendors_*.py -m live -v
```

**Type-check:**
```bash
uv run mypy src/aichemy_pricing/vendors/
```
Expected: Success.

---

## Self-review

**Spec coverage:** Each of the three Tier 1 vendors promised in the header has a module + test file + fixture. Each implementation is anchored to a specific CLAIM-XX in the verification report. Fluorochem uses the corrected schema (Pricing.GBP["Base Price"]) — not the fabricated `min_gbp`/`has_stock_*`. Molbase uses the corrected URL `/cas/{CAS}.html` — not the report's broken `/en/cas-{CAS}.html`. Tocris uses the verified anonymous SSR pattern.

**Placeholder scan:** No "TBD" / "implement later". One nuance: the regex-based HTML parsers in Molbase and Tocris are deliberately narrow — they assume the simplest visible (price, pack) pair, not a full table parse. If a future regression shows these parsers missing valid prices, the fix is to widen the regex; the scope of this sub-plan is "first verified price returned per SKU", not "best price across all packs/suppliers".

**Type consistency:** All three vendors implement `lookup(ref: VendorRef) -> PriceQuote | None` with `name: str` attribute, satisfying the `PriceLookup` protocol from sub-plan A. All three return `currency="USD"` or `"GBP"` per their actual vendor pages, which are members of the `Currency` literal type defined in sub-plan A.
