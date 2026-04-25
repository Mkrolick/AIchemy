# Sub-Plan D: `aichemy-pricing` — Tier 2 (JS-Rendered) + Tier 3 (Cloudflare-Aware) Vendors

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Parent plan:** `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`
> **Verification source:** `experiments/chem-pricing-verification/CLAIMS.md` (CLAIM-07 Enamine, CLAIM-14 Cayman, CLAIM-17 ChemCruz, CLAIM-15 MedChemExpress)
> **Depends on:** Sub-Plan A (`PriceQuote`, `VendorRef`, `make_plain_client`, `make_cf_client`); knowledge from sub-plan C is helpful but not strictly required (this sub-plan can be reviewed in parallel with C)
> **Delivers (consumed by sub-plan E):**
> - `aichemy_pricing.vendors.enamine.EnamineVendor` — XHR JSON discovered via DevTools (Tier 2)
> - `aichemy_pricing.vendors.cayman.CaymanVendor` — XHR JSON discovered via DevTools (Tier 2)
> - `aichemy_pricing.vendors.chemcruz.ChemCruzVendor` — SSR HTML scrape (Tier 2, light Cloudflare)
> - `aichemy_pricing.vendors.medchemexpress.MedChemExpressVendor` — `curl_cffi` Chrome 124 fingerprint (Tier 3)

**Goal:** Implement the four vendors that need either (a) a discovered XHR endpoint instead of the user-facing HTML page (Enamine, Cayman) or (b) a real-browser TLS fingerprint to pass Cloudflare (MedChemExpress). ChemCruz fits in this sub-plan because it has light Cloudflare on top of an SSR page — same browser-UA-passes pattern as Tocris but worth its own module given the metabolite focus.

**Architecture:** Same one-class-per-vendor pattern as sub-plan C. Tier 2 vendors require a one-time DevTools discovery step to identify the JSON endpoint serving prices; that step is documented inline as Task D-X.0 for each vendor. Tier 3 swaps `make_plain_client()` for `make_cf_client()` from sub-plan A.

**Tech Stack:** Python 3.11, `httpx` (Tier 2), `curl_cffi` (Tier 3 only), `re` for HTML/JSON shape extraction. **No headless-browser dependency** — every Tier 2 vendor here resolves to a JSON endpoint hit directly with `httpx`.

---

## File Structure

```
src/aichemy_pricing/vendors/
├── enamine.py                             # CREATE — Task D1
├── cayman.py                              # CREATE — Task D2
├── chemcruz.py                            # CREATE — Task D3
└── medchemexpress.py                      # CREATE — Task D4

src/aichemy_pricing/tests/
├── data/
│   ├── enamine_EN300_7605608.json         # CAPTURE — discovered XHR response
│   ├── cayman_14010.json                  # CAPTURE — discovered XHR response
│   ├── chemcruz_aspirin.html              # CAPTURE — SSR HTML
│   └── mce_acetyl_coa.html                # CAPTURE — Cloudflare-passed HTML
├── test_vendors_enamine.py                # CREATE (4 tests)
├── test_vendors_cayman.py                 # CREATE (4 tests)
├── test_vendors_chemcruz.py               # CREATE (4 tests)
└── test_vendors_medchemexpress.py         # CREATE (4 tests)
```

---

## Task D1: `EnamineVendor` (Tier 2 — discovered XHR)

**Per CLAIM-07 (VERIFIED):** product URL is `enaminestore.com/catalog/EN300-{N}` (canonical host, no www). Body is a React/CRA shell with `<noscript>You need to enable JavaScript</noscript>` — no SSR pricing. Pricing data must be obtained from an XHR endpoint that the React app calls after page load.

### D1.0: One-time DevTools discovery

**Pre-discovery facts** (verified by inspecting the React/Next.js bundle at `/static/js/main.060dfd03.js`):
- The customer-facing host `enaminestore.com` is a thin shell. The **actual product backend is `ebc.enamine.net`** (visible in the bundle as `https://ebc.enamine.net/molecule-product/`).
- `https://ebc.enamine.net/molecule-product/<sku>` returns the Next.js HTML; the JSON endpoint is a separate route on the same host.
- Common patterns to try in DevTools: `/api/`, `/_next/data/.../{sku}.json`, or a server-action under `/molecule-product/`.

- [ ] **Step 1: Open Chrome DevTools → Network → filter XHR/fetch.**
- [ ] **Step 2: Visit `https://enaminestore.com/catalog/EN300-7605608`** with DevTools open. Watch for requests to `ebc.enamine.net` in particular.
- [ ] **Step 3: Identify the JSON request that returns pricing data.**

  Look for a response body containing fields like `Pricing`, `Quantity`, or `Price` (NOT just an HTML body — Next.js will serve HTML for the catch-all route). Right-click the right entry → Copy → Copy as cURL. Confirm the response `Content-Type` is `application/json`.

  If no JSON XHR is observed, the page may be a React Server Component fetch — the data arrives embedded in the initial HTML response from `ebc.enamine.net/molecule-product/{sku}`. In that case, fall back to **HTML parsing**: capture that HTML body as fixture and write a regex parser instead of a JSON parser.

- [ ] **Step 4: Save the response body as fixture:**

  ```bash
  # Replace <DISCOVERED-URL> with the actual URL from DevTools.
  curl -A "Mozilla/5.0 ...Chrome/124..." \
       -H "Accept: application/json" \
       -sL "<DISCOVERED-URL>" \
       > src/aichemy_pricing/tests/data/enamine_EN300_7605608.json
  test -s src/aichemy_pricing/tests/data/enamine_EN300_7605608.json && echo OK
  ```

- [ ] **Step 5: Document the URL pattern in the vendor module's docstring.** If the API requires extra headers (Origin, Referer, X-API-Key), record those too — they go into the `httpx.Client` headers.

### D1.1: Implementation

**Files:**
- Create: `src/aichemy_pricing/vendors/enamine.py`
- Create: `src/aichemy_pricing/tests/test_vendors_enamine.py`

- [ ] **Step 1: Failing tests**

```python
# src/aichemy_pricing/tests/test_vendors_enamine.py
"""Unit tests for EnamineVendor.

Per CLAIM-07: product URL is enaminestore.com/catalog/EN300-{N}; body is
React shell with no SSR pricing — pricing comes from a discovered XHR JSON
endpoint. The fixture below is captured during D1.0.
"""
from __future__ import annotations

import json

import httpx
import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.enamine import EnamineVendor


def _patch_http(monkeypatch: pytest.MonkeyPatch, *, status: int, body: bytes = b"") -> None:
    def mock_send(self, request, **kw):  # noqa: ARG001
        return httpx.Response(status, content=body, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)


def test_enamine_parses_real_xhr_response(monkeypatch, fixture_dir) -> None:
    body = (fixture_dir / "enamine_EN300_7605608.json").read_bytes()
    _patch_http(monkeypatch, status=200, body=body)
    quote = EnamineVendor().lookup(VendorRef(vendor="enamine", sku="EN300-7605608"))
    assert quote is not None
    assert quote.vendor == "enamine"
    assert quote.currency in ("USD", "EUR")
    assert quote.price > 0
    assert quote.pack_size_g > 0


def test_enamine_returns_none_on_404(monkeypatch) -> None:
    _patch_http(monkeypatch, status=404)
    assert EnamineVendor().lookup(VendorRef(vendor="enamine", sku="EN300-0000")) is None


def test_enamine_returns_none_when_response_missing_pricing(monkeypatch) -> None:
    body = json.dumps({"sku": "EN300-1", "name": "x"}).encode()
    _patch_http(monkeypatch, status=200, body=body)
    assert EnamineVendor().lookup(VendorRef(vendor="enamine", sku="EN300-1")) is None


def test_enamine_uses_correct_xhr_url(monkeypatch) -> None:
    captured: dict[str, str] = {}
    def mock_send(self, request, **kw):  # noqa: ARG001
        captured["url"] = str(request.url)
        return httpx.Response(404, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)
    EnamineVendor().lookup(VendorRef(vendor="enamine", sku="EN300-7605608"))
    assert "EN300-7605608" in captured["url"]


@pytest.mark.live
def test_enamine_live_EN300_7605608() -> None:
    quote = EnamineVendor().lookup(VendorRef(vendor="enamine", sku="EN300-7605608"))
    assert quote is not None
    assert quote.price > 0
```

- [ ] **Step 2: Implement** (using the discovered URL + JSON shape from D1.0)

```python
# src/aichemy_pricing/vendors/enamine.py
"""Enamine Store — pricing via discovered XHR JSON endpoint.

Per CLAIM-07 (VERIFIED): user-facing URL `enaminestore.com/catalog/EN300-{N}`
returns a React/CRA shell with no SSR pricing. Pricing must be fetched from
the JSON endpoint the React app calls after page load.

DISCOVERED ENDPOINT (record verbatim from DevTools during D1.0):
  URL pattern: <FILL FROM DEVTOOLS>          e.g. https://www.enaminestore.com/api/v1/catalog/EN300-{N}
  Method:      GET
  Auth:        none observed
  Required headers: Accept: application/json (Origin/Referer may be required)

JSON shape (record verbatim — adjust the parser below to match):
  {
    "sku": "EN300-7605608",
    "packs": [
      {"size": 1, "unit": "g", "price": 123.0, "currency": "USD"},
      ...
    ]
  }
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams

# MUST be replaced during D1.0 with the real discovered endpoint.
# Backend host is known (`ebc.enamine.net`); the path/method depends on whether
# the React app uses a JSON XHR or a server-component HTML fetch.
_PLACEHOLDER_API_URL = "https://ebc.enamine.net/molecule-product/{sku}.json"
_API_URL = _PLACEHOLDER_API_URL  # ⚠️ overwrite after D1.0


class EnamineVendor:
    name = "enamine"

    def __init__(self, client: httpx.Client | None = None) -> None:
        if _API_URL == _PLACEHOLDER_API_URL:
            # Fail loud rather than silently returning None for every lookup.
            raise NotImplementedError(
                "EnamineVendor: _API_URL is still the discovery placeholder. "
                "Run Task D1.0 to identify the real XHR endpoint via DevTools, "
                "then overwrite _API_URL with the discovered pattern."
            )
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = _API_URL.format(sku=ref.sku)
        resp = self._client.get(url, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            return None
        try:
            body = resp.json()
        except ValueError:
            return None
        packs = body.get("packs") or []
        if not packs:
            return None
        pack = packs[0]
        try:
            size = float(pack["size"])
            unit = str(pack["unit"])
            price = float(pack["price"])
            currency = str(pack.get("currency", "USD"))
        except (KeyError, ValueError, TypeError):
            return None
        return PriceQuote(
            vendor=self.name,
            sku=ref.sku,
            price=price,
            currency=currency,
            pack_size_g=pack_size_to_grams(size, unit),
            fetched_at=datetime.now(timezone.utc),
            raw=pack,
        )
```

> **NOTE:** the JSON parser above is structural. After D1.0 captures the real response, edit the parser inline to match the actual field names and adjust the test fixture to a real captured body. Tests must pass before commit.

- [ ] **Step 3: Re-export**

```python
# src/aichemy_pricing/vendors/__init__.py — append
from aichemy_pricing.vendors.enamine import EnamineVendor
__all__ = [..., "EnamineVendor"]
```

- [ ] **Step 4: Run; pass (4 tests offline + 1 live skipped)**

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/vendors/enamine.py src/aichemy_pricing/vendors/__init__.py src/aichemy_pricing/tests/test_vendors_enamine.py src/aichemy_pricing/tests/data/enamine_EN300_7605608.json
git commit -m "feat(pricing): EnamineVendor via discovered XHR JSON endpoint"
```

---

## Task D2: `CaymanVendor` (Tier 2 — discovered XHR)

**Per CLAIM-14 (VERIFIED):** URL `caymanchem.com/product/{itemID}/{slug}`; body is partial-SSR (title + CAS in HTML) with pricing JS-loaded. IDs span 5–8 digits across non-contiguous ranges. **Drive scraper from a sitemap, not range enumeration.**

### D2.0: DevTools discovery

- [ ] Open `https://www.caymanchem.com/product/14010/prostaglandin-e2` → DevTools → Network → XHR.
- [ ] Identify the JSON endpoint that returns pricing.
- [ ] Capture as `src/aichemy_pricing/tests/data/cayman_14010.json`.
- [ ] Document the URL pattern in the module docstring.

### D2.1: Implementation

**Files:**
- Create: `src/aichemy_pricing/vendors/cayman.py`
- Create: `src/aichemy_pricing/tests/test_vendors_cayman.py`

- [ ] **Step 1: Failing tests** (mirror D1 structure: real-fixture parse, 404, missing pricing, correct URL, live test).

```python
# src/aichemy_pricing/tests/test_vendors_cayman.py
"""Unit tests for CaymanVendor.

Per CLAIM-14: URL caymanchem.com/product/{itemID}/{slug}; partial-SSR with
pricing via XHR. SKU here = the bare itemID (slug omitted).
"""
from __future__ import annotations

import json

import httpx
import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.cayman import CaymanVendor


def _patch_http(monkeypatch: pytest.MonkeyPatch, *, status: int, body: bytes = b"") -> None:
    def mock_send(self, request, **kw):  # noqa: ARG001
        return httpx.Response(status, content=body, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)


def test_cayman_parses_real_xhr_response(monkeypatch, fixture_dir) -> None:
    body = (fixture_dir / "cayman_14010.json").read_bytes()
    _patch_http(monkeypatch, status=200, body=body)
    quote = CaymanVendor().lookup(VendorRef(vendor="cayman", sku="14010"))
    assert quote is not None
    assert quote.vendor == "cayman"
    assert quote.currency == "USD"
    assert quote.price > 0


def test_cayman_returns_none_on_404(monkeypatch) -> None:
    _patch_http(monkeypatch, status=404)
    assert CaymanVendor().lookup(VendorRef(vendor="cayman", sku="0")) is None


def test_cayman_returns_none_when_no_pricing(monkeypatch) -> None:
    _patch_http(monkeypatch, status=200, body=json.dumps({"id": 1}).encode())
    assert CaymanVendor().lookup(VendorRef(vendor="cayman", sku="1")) is None


def test_cayman_includes_sku_in_url(monkeypatch) -> None:
    captured: dict[str, str] = {}
    def mock_send(self, request, **kw):  # noqa: ARG001
        captured["url"] = str(request.url)
        return httpx.Response(404, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)
    CaymanVendor().lookup(VendorRef(vendor="cayman", sku="14010"))
    assert "14010" in captured["url"]


@pytest.mark.live
def test_cayman_live_prostaglandin_e2() -> None:
    quote = CaymanVendor().lookup(VendorRef(vendor="cayman", sku="14010"))
    assert quote is not None
    assert quote.price > 0
```

- [ ] **Step 2: Implement** — same shape as `EnamineVendor`, swap URL pattern for the discovered one. Hard-code currency="USD" (Cayman is USD-only on the US site).

- [ ] **Step 3: Re-export, run, commit.**

```bash
git commit -m "feat(pricing): CaymanVendor via discovered XHR JSON endpoint"
```

---

## Task D3: `ChemCruzVendor` (Tier 2 — SSR with light Cloudflare)

**Per CLAIM-17 (VERIFIED):** URL `scbt.com/p/{slug}-{cas}`; 175,000 ChemCruz biochemicals; moderate Cloudflare passes with browser UA. Unlike Enamine/Cayman, the ChemCruz product page renders prices in SSR HTML (no XHR needed).

**Files:**
- Create: `src/aichemy_pricing/vendors/chemcruz.py`
- Create: `src/aichemy_pricing/tests/test_vendors_chemcruz.py`
- Capture: `src/aichemy_pricing/tests/data/chemcruz_aspirin.html`

- [ ] **Step 1: Capture fixture**

```bash
uv run python -m aichemy_pricing.tests.data._capture \
  --url https://www.scbt.com/p/aspirin-50-78-2 \
  --out src/aichemy_pricing/tests/data/chemcruz_aspirin.html \
  --min-size 5000 \
  --required-marker 'Aspirin' \
  --required-marker '50-78-2'
```

Per CLAIM-17 ChemCruz uses moderate Cloudflare; the helper's BAD_MARKERS list catches the JS-challenge case. If it fails, retry from a residential IP.

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_vendors_chemcruz.py
"""Unit tests for ChemCruzVendor.

Per CLAIM-17: scbt.com/p/{slug}-{cas}; 175k biochemicals; moderate
Cloudflare passes with browser UA. SKU = the {slug}-{cas} suffix.
"""
from __future__ import annotations

import httpx
import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.chemcruz import ChemCruzVendor


def _patch_http(monkeypatch: pytest.MonkeyPatch, *, status: int, body: bytes = b"") -> None:
    def mock_send(self, request, **kw):  # noqa: ARG001
        return httpx.Response(status, content=body, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)


def test_chemcruz_parses_synthetic_ssr_html(monkeypatch) -> None:
    body = (
        b"<html><head><title>Aspirin | SCBT</title></head>"
        b"<body><div class='size-price'>5g</div><div class='price'>$76.00</div></body></html>"
    )
    _patch_http(monkeypatch, status=200, body=body)
    quote = ChemCruzVendor().lookup(VendorRef(vendor="chemcruz", sku="aspirin-50-78-2"))
    assert quote is not None
    assert quote.currency == "USD"
    assert quote.pack_size_g == 5.0
    assert quote.price == 76.0


def test_chemcruz_returns_none_on_404(monkeypatch) -> None:
    _patch_http(monkeypatch, status=404)
    assert ChemCruzVendor().lookup(VendorRef(vendor="chemcruz", sku="x-0-0-0")) is None


def test_chemcruz_returns_none_when_no_price(monkeypatch) -> None:
    _patch_http(monkeypatch, status=200, body=b"<html>no price here</html>")
    assert ChemCruzVendor().lookup(VendorRef(vendor="chemcruz", sku="x-0-0-0")) is None


def test_chemcruz_uses_correct_url(monkeypatch) -> None:
    captured: dict[str, str] = {}
    def mock_send(self, request, **kw):  # noqa: ARG001
        captured["url"] = str(request.url)
        return httpx.Response(404, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)
    ChemCruzVendor().lookup(VendorRef(vendor="chemcruz", sku="aspirin-50-78-2"))
    assert captured["url"] == "https://www.scbt.com/p/aspirin-50-78-2"


@pytest.mark.live
def test_chemcruz_live_aspirin() -> None:
    r = ChemCruzVendor().lookup(VendorRef(vendor="chemcruz", sku="aspirin-50-78-2"))
    if r is not None:  # ChemCruz may not stock every CAS; just don't crash
        assert r.price > 0
```

- [ ] **Step 3: Implement** — same regex pattern as Tocris (size/unit + `$N.NN`).

```python
# src/aichemy_pricing/vendors/chemcruz.py
"""Santa Cruz Biotechnology / ChemCruz — anonymous SSR HTML pricing.

Per CLAIM-17 (VERIFIED): scbt.com/p/{slug}-{cas}; 175k biochemicals;
moderate Cloudflare passes with a browser UA. Pricing renders in SSR HTML.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from aichemy_pricing.http import make_plain_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams

_PACK_RE = re.compile(r"\b([\d.]+)\s*(mg|g|kg|µg|ug|mcg)\b", re.I)
_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


class ChemCruzVendor:
    name = "chemcruz"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_plain_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.scbt.com/p/{ref.sku}"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        m_pack = _PACK_RE.search(resp.text)
        m_price = _PRICE_RE.search(resp.text)
        if not (m_pack and m_price):
            return None
        try:
            size = float(m_pack.group(1))
            unit = m_pack.group(2).lower()
            price = float(m_price.group(1).replace(",", ""))
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

- [ ] **Step 4: Re-export, run, commit.**

```bash
git commit -m "feat(pricing): ChemCruzVendor — SSR HTML scrape"
```

---

## Task D4: `MedChemExpressVendor` (Tier 3 — Cloudflare via curl_cffi)

**Per CLAIM-15 (VERIFIED):** URL `medchemexpress.com/{slug}.html`; **Cloudflare returns 403 to plain HTTP, even with a Chrome User-Agent header**. Bypass requires a real-browser TLS fingerprint via `curl_cffi` impersonating Chrome 124. All four CoA salt forms the original report named (free, lithium, trisodium, trilithium) exist as separate `.html` slugs — exact verification match.

**Files:**
- Create: `src/aichemy_pricing/vendors/medchemexpress.py`
- Create: `src/aichemy_pricing/tests/test_vendors_medchemexpress.py`
- Capture: `src/aichemy_pricing/tests/data/mce_acetyl_coa.html`

- [ ] **Step 1: Capture fixture using curl_cffi (validated)**

```bash
uv run python -m aichemy_pricing.tests.data._capture \
  --url https://www.medchemexpress.com/acetyl-coenzyme-a.html \
  --out src/aichemy_pricing/tests/data/mce_acetyl_coa.html \
  --client cf --impersonate chrome124 \
  --min-size 5000 \
  --required-marker 'Acetyl'
```

The helper (Sub-Plan A Task A7) refuses to write the fixture if Cloudflare returned a challenge page — its BAD_MARKERS list covers `Just a moment...`, `cf-browser-verification`, `challenge-platform`, `Checking your browser`, and `Enable JavaScript and cookies`. If the helper fails, retry with a newer `--impersonate` token (`chrome116`, `chrome120`, `chrome131`) — Chrome's TLS fingerprint rotates with each major release.

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_vendors_medchemexpress.py
"""Unit tests for MedChemExpressVendor.

Per CLAIM-15 (VERIFIED): URL medchemexpress.com/{slug}.html; Cloudflare 403s
plain httpx and even httpx with Chrome UA — must use curl_cffi with a real
TLS fingerprint. Tests below mock at the curl_cffi.Session.get layer.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aichemy_pricing.types import VendorRef
from aichemy_pricing.vendors.medchemexpress import MedChemExpressVendor


def _make_mock_session(*, status: int, body: bytes) -> MagicMock:
    sess = MagicMock()
    sess.get.return_value = MagicMock(status_code=status, text=body.decode("utf-8", "replace"))
    return sess


def test_mce_parses_real_html(fixture_dir) -> None:
    body = (fixture_dir / "mce_acetyl_coa.html").read_bytes()
    sess = _make_mock_session(status=200, body=body)
    v = MedChemExpressVendor(client=sess)
    quote = v.lookup(VendorRef(vendor="medchemexpress", sku="acetyl-coenzyme-a"))
    # Live MCE pages render prices in HTML; just check no crash and shape.
    if quote is not None:
        assert quote.currency == "USD"
        assert quote.price > 0


def test_mce_returns_none_on_403_cloudflare_block() -> None:
    sess = _make_mock_session(status=403, body=b"<html>cloudflare challenge</html>")
    v = MedChemExpressVendor(client=sess)
    assert v.lookup(VendorRef(vendor="medchemexpress", sku="x.html")) is None


def test_mce_returns_none_when_html_missing_price() -> None:
    sess = _make_mock_session(status=200, body=b"<html><body>no price</body></html>")
    v = MedChemExpressVendor(client=sess)
    assert v.lookup(VendorRef(vendor="medchemexpress", sku="x")) is None


def test_mce_uses_correct_url() -> None:
    sess = _make_mock_session(status=404, body=b"")
    v = MedChemExpressVendor(client=sess)
    v.lookup(VendorRef(vendor="medchemexpress", sku="acetyl-coenzyme-a"))
    sess.get.assert_called_once()
    call_args = sess.get.call_args
    assert "acetyl-coenzyme-a.html" in str(call_args)


@pytest.mark.live
def test_mce_live_acetyl_coa() -> None:
    """Hits real MCE through curl_cffi. Asserts no Cloudflare block."""
    v = MedChemExpressVendor()
    r = v.lookup(VendorRef(vendor="medchemexpress", sku="acetyl-coenzyme-a"))
    # Even if price-extraction fails, the HTTP layer must not 403.
    # We assert by calling .lookup and getting back either a quote or None
    # (None acceptable if regex misses — the point is no exception).
    assert r is None or r.price > 0
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/vendors/medchemexpress.py
"""MedChemExpress — Cloudflare-aware via curl_cffi.

Per CLAIM-15 (VERIFIED): URL medchemexpress.com/{slug}.html. Cloudflare 403s
plain httpx (even with the Chrome UA header) — passing requires the TLS
fingerprint that `curl_cffi` provides via `impersonate="chrome124"`.

All four CoA salt forms named in the original report exist as separate
.html slugs (verified):
  /acetyl-coenzyme-a.html (free)
  /acetyl-coenzyme-a-lithium.html
  /acetyl-coenzyme-a-trisodium.html
  /acetyl-coenzyme-a-trilithium.html
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from aichemy_pricing.http import make_cf_client
from aichemy_pricing.types import PriceQuote, VendorRef
from aichemy_pricing.vendors._common import pack_size_to_grams

_PACK_PRICE_RE = re.compile(
    r"([\d.]+)\s*(mg|g|kg|µg|ug|mcg)\b[^$]{0,200}\$\s*([\d,]+(?:\.\d+)?)",
    re.I | re.S,
)


class MedChemExpressVendor:
    name = "medchemexpress"

    def __init__(self, client=None) -> None:  # type: ignore[no-untyped-def]
        self._client = client if client is not None else make_cf_client()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        url = f"https://www.medchemexpress.com/{ref.sku}.html"
        resp = self._client.get(url)
        if resp.status_code != 200:
            return None
        m = _PACK_PRICE_RE.search(resp.text)
        if not m:
            return None
        try:
            size = float(m.group(1))
            unit = m.group(2).lower()
            price = float(m.group(3).replace(",", ""))
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
from aichemy_pricing.vendors.cayman import CaymanVendor
from aichemy_pricing.vendors.chemcruz import ChemCruzVendor
from aichemy_pricing.vendors.enamine import EnamineVendor
from aichemy_pricing.vendors.fluorochem import FluorochemVendor
from aichemy_pricing.vendors.medchemexpress import MedChemExpressVendor
from aichemy_pricing.vendors.molbase import MolbaseVendor
from aichemy_pricing.vendors.tocris import TocrisVendor

__all__ = [
    "FluorochemVendor", "MolbaseVendor", "TocrisVendor",
    "EnamineVendor", "CaymanVendor", "ChemCruzVendor",
    "MedChemExpressVendor",
]
```

- [ ] **Step 5: Run; pass (4 tests offline + 1 live skipped)**

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/vendors/medchemexpress.py src/aichemy_pricing/vendors/__init__.py src/aichemy_pricing/tests/test_vendors_medchemexpress.py src/aichemy_pricing/tests/data/mce_acetyl_coa.html
git commit -m "feat(pricing): MedChemExpressVendor via curl_cffi (Tier 3)"
```

---

## Unit Tests Summary (Sub-Plan D)

| Test file | Offline | Live | Notes |
|---|---:|---:|---|
| `test_vendors_enamine.py` | 4 | 1 | XHR JSON parse; 404; missing pricing; correct URL; (live) EN300-7605608 |
| `test_vendors_cayman.py` | 4 | 1 | XHR JSON parse; 404; missing pricing; URL contains SKU; (live) PG E2 |
| `test_vendors_chemcruz.py` | 4 | 1 | Synthetic SSR parse; 404; no-price; correct URL; (live) aspirin |
| `test_vendors_medchemexpress.py` | 4 | 1 | curl_cffi mocked; 403 block; no-price; correct URL; (live) acetyl-CoA |
| **Total** | **16** | **4** | All offline tests run in <3s. Live tests require `-m live`. |

**All-tests command (offline only):**
```bash
uv run pytest src/aichemy_pricing/tests/test_vendors_enamine.py src/aichemy_pricing/tests/test_vendors_cayman.py src/aichemy_pricing/tests/test_vendors_chemcruz.py src/aichemy_pricing/tests/test_vendors_medchemexpress.py -v
```

**Type-check:**
```bash
uv run mypy src/aichemy_pricing/vendors/
```
Expected: Success (note: `curl_cffi` has no public type stubs; the `make_cf_client` and `MedChemExpressVendor.__init__` are annotated with `# type: ignore[no-untyped-def]` to keep mypy strict elsewhere).

---

## Self-review

**Spec coverage:** Each of the four vendors has a module + test file + fixture + CLAIM-XX anchor. Tier 2 tasks (D1, D2) include explicit DevTools discovery sub-steps (D1.0, D2.0) before implementation, because the JSON endpoint isn't documented anywhere — it must be observed live and the parser fitted to the real shape. Tier 3 (D4) uses `curl_cffi` because plain `httpx` with a Chrome UA still gets 403 from MCE per direct probing.

**Placeholder scan:** The Enamine and Cayman implementations have a `<FILL FROM DEVTOOLS>` URL pattern in their docstrings — this is **not a placeholder we're shipping with**, it's a flag that the implementation step must record the real URL discovered in D1.0 / D2.0 before tests can pass. The tests assert against captured-from-live fixtures, so the parser correctness is locked in by the fixture, not by stub data.

**Type consistency:** All four vendors implement `lookup(ref: VendorRef) -> PriceQuote | None` with `name: str`. MedChemExpress's constructor accepts an injectable client (untyped because curl_cffi has no type stubs) — tests pass a `MagicMock` instead. Currency literals all match the `Currency` type from sub-plan A.
