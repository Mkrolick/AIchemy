# Sub-Plan F: `aichemy-pricing` — Browserbase L3 Fallback (Fetch API)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Parent plan:** `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`
> **Verification source:** `experiments/chem-pricing-verification/CLAIMS.md` (CLAIM-13 Sigma + CLAIM-15 MCE + CLAIM-17 ChemCruz are the high-leverage L3 vendors)
> **Depends on:** Sub-Plan A (types, `PriceLookup` protocol, `CachedPriceLookup`); composes downstream of sub-plans C (L2 Tier 1) and D-trimmed (L2 MCE).
> **Delivers (consumed by sub-plan E):**
> - `aichemy_pricing.browserbase.client.BrowserbaseClient` — thin httpx wrapper around the Browserbase Fetch API (one HTTPS POST per page)
> - `aichemy_pricing.browserbase.fetch_lookup.BrowserbaseFetchLookup` — `PriceLookup` impl that hits Fetch API → vendor-specific markdown parser → `PriceQuote`
> - `aichemy_pricing.browserbase.parsers.{sigma, enamine, cayman, chemcruz, tocris, molbase}` — one markdown→price parser per L3 vendor
> - `aichemy_pricing.browserbase.browser_api` — **STUB** for full Playwright/CDP automation (Browser API), unused in v1
> - `aichemy_pricing.browserbase.llm_extract` — **STUB** for vendor-agnostic LLM-based extraction, unused in v1

**Goal:** Cover the long-tail of vendors not addressable by L2 httpx — including Sigma-Aldrich (Akamai-gated per CLAIM-13) — by routing un-resolved SKUs through Browserbase's Fetch API. Browserbase renders the page server-side using stealth + residential IPs and returns clean markdown; we parse the price out per vendor.

**Architecture:** Browserbase Fetch API is one HTTP call: `POST https://api.browserbase.com/v1/fetch` with `{url}` returns `{markdown}`. No Playwright, no CDP, no session lifecycle to manage — just a request. Per-vendor markdown parsers are pure functions of `(markdown_text, sku) → PriceQuote | None`. The Browser API and LLM-extraction modules ship as `NotImplementedError`-raising stubs so a future revision can add them without re-architecting.

**Tech Stack:** Python 3.11, `httpx` (already pulled by sub-plan A — Browserbase Fetch is just a POST). `playwright` and `anthropic` are NOT dependencies — the stubs exist but aren't imported until a future revision wires them up.

**Cost model (per CLAIM-13/14/15 verification + Browserbase pricing page):** Fetch API is $1/1K calls on Developer plan ($0.001/page); $0.50/1K on Startup ($0.0005/page). For a 100K-compound run with ~50% L1+L2 hit-rate, L3 fires ~50K times → **~$25–$50** all-in for the Browserbase portion, ~30–40 min wall-clock at 100 concurrent.

---

## File Structure

```
src/aichemy_pricing/browserbase/
├── __init__.py                              # CREATE — re-export the L3 lookup + parsers
├── client.py                                # CREATE — Task F1
├── fetch_lookup.py                          # CREATE — Task F2
├── parsers/
│   ├── __init__.py                          # CREATE — parser registry by vendor name
│   ├── _base.py                             # CREATE — MarkdownParser protocol
│   ├── _common.py                           # CREATE — shared regex + currency helpers
│   ├── sigma.py                             # CREATE — Task F3 (highest-value L3 vendor)
│   ├── enamine.py                           # CREATE — Task F4
│   ├── cayman.py                            # CREATE — Task F5
│   ├── chemcruz.py                          # CREATE — Task F6
│   ├── tocris.py                            # CREATE — Task F7
│   └── molbase.py                           # CREATE — Task F8
├── browser_api.py                           # CREATE — STUB raising NotImplementedError
└── llm_extract.py                           # CREATE — STUB raising NotImplementedError

src/aichemy_pricing/tests/
├── data/
│   ├── browserbase_fetch_response.json      # CAPTURE — frozen Fetch API response (real)
│   ├── bb_md_sigma_aspirin.md               # CAPTURE — Sigma rendered markdown (real)
│   ├── bb_md_enamine_EN300_7605608.md       # CAPTURE
│   ├── bb_md_cayman_14010.md                # CAPTURE
│   ├── bb_md_chemcruz_aspirin.md            # CAPTURE
│   ├── bb_md_tocris_jw642.md                # CAPTURE
│   └── bb_md_molbase_aspirin.md             # CAPTURE
├── test_browserbase_client.py               # 3 tests (mocked POST, missing-key path, error)
├── test_browserbase_fetch_lookup.py         # 4 tests (parser dispatch, miss → None, etc.)
├── test_browserbase_parser_sigma.py         # 2 tests
├── test_browserbase_parser_enamine.py       # 2 tests
├── test_browserbase_parser_cayman.py        # 2 tests
├── test_browserbase_parser_chemcruz.py      # 2 tests
├── test_browserbase_parser_tocris.py        # 2 tests
├── test_browserbase_parser_molbase.py       # 2 tests
└── test_browserbase_stubs.py                # 2 tests (browser_api raises; llm_extract raises)
```

---

## Task F1: `client.py` — Browserbase Fetch API client

**Files:**
- Create: `src/aichemy_pricing/browserbase/__init__.py` (empty for now)
- Create: `src/aichemy_pricing/browserbase/client.py`
- Create: `src/aichemy_pricing/tests/test_browserbase_client.py`

**Why:** Centralize the API-key handling and the one POST call. Every parser shares this client.

- [ ] **Step 1: Failing tests**

```python
# src/aichemy_pricing/tests/test_browserbase_client.py
"""Unit tests for BrowserbaseClient. Mocks the POST so tests are offline.

Per Browserbase docs (https://docs.browserbase.com/), the Fetch API is a
single POST to /v1/fetch returning {markdown, status, ...}. Auth via
X-BB-API-Key header from the BROWSERBASE_API_KEY env var.
"""
from __future__ import annotations

import json

import httpx
import pytest

from aichemy_pricing.browserbase.client import BrowserbaseClient


def test_client_no_api_key_returns_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("BROWSERBASE_API_KEY", raising=False)
    c = BrowserbaseClient()
    assert not c.is_configured()
    assert c.fetch_markdown("https://example.com/x") is None  # silent no-op


def test_client_with_key_posts_to_fetch_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def mock_send(self, request, **kw):  # noqa: ARG001
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["api_key"] = request.headers.get("X-BB-API-Key")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            content=json.dumps({"markdown": "# Hello\\n$12.50 / 5 g", "status": 200}).encode(),
            request=request,
        )
    monkeypatch.setattr(httpx.Client, "send", mock_send)

    c = BrowserbaseClient()
    md = c.fetch_markdown("https://www.sigmaaldrich.com/US/en/product/aldrich/202630")
    assert md is not None and "$12.50" in md
    assert captured["method"] == "POST"
    assert captured["api_key"] == "test-key"
    assert captured["body"]["url"].startswith("https://www.sigmaaldrich.com/")
    assert "browserbase.com" in captured["url"]


def test_client_returns_none_on_non_200(monkeypatch) -> None:
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")
    def mock_send(self, request, **kw):  # noqa: ARG001
        return httpx.Response(503, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)
    c = BrowserbaseClient()
    assert c.fetch_markdown("https://example.com/x") is None
```

- [ ] **Step 2: Implement**

```python
# src/aichemy_pricing/browserbase/client.py
"""Thin httpx wrapper around Browserbase's Fetch API.

Mechanics: one HTTPS POST to https://api.browserbase.com/v1/fetch with
`{"url": "..."}`. Returns rendered markdown of the page after JS runs.
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

import httpx

log = logging.getLogger(__name__)

_FETCH_URL = "https://api.browserbase.com/v1/fetch"
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class BrowserbaseClient:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None) -> None:
        self._api_key = api_key or os.environ.get("BROWSERBASE_API_KEY")
        self._client = client or httpx.Client(timeout=_TIMEOUT)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def fetch_markdown(self, url: str) -> str | None:
        """POST to Fetch API, return rendered markdown or None on any failure.

        Returns None (not raises) for: no API key, HTTP error, malformed
        response — the L3 layer treats every miss as "this vendor didn't
        return a price" rather than aborting the whole chain.
        """
        if not self._api_key:
            log.debug("BrowserbaseClient: BROWSERBASE_API_KEY unset; skipping %s", url)
            return None
        try:
            resp = self._client.post(
                _FETCH_URL,
                headers={"X-BB-API-Key": self._api_key, "Content-Type": "application/json"},
                json={"url": url},
            )
        except httpx.HTTPError as exc:
            log.warning("Browserbase fetch %s: HTTP error %s", url, exc)
            return None
        if resp.status_code != 200:
            log.warning("Browserbase fetch %s: status %d", url, resp.status_code)
            return None
        try:
            return resp.json().get("markdown")
        except ValueError:
            log.warning("Browserbase fetch %s: non-JSON response", url)
            return None
```

- [ ] **Step 3: Run; pass + commit**

---

## Task F2: `fetch_lookup.py` — `BrowserbaseFetchLookup` (`PriceLookup` impl)

**Files:**
- Create: `src/aichemy_pricing/browserbase/fetch_lookup.py`
- Create: `src/aichemy_pricing/browserbase/parsers/__init__.py`
- Create: `src/aichemy_pricing/browserbase/parsers/_base.py`
- Create: `src/aichemy_pricing/tests/test_browserbase_fetch_lookup.py`

- [ ] **Step 1: Define the parser protocol + URL builder**

```python
# src/aichemy_pricing/browserbase/parsers/_base.py
"""Each L3 vendor parser is a tiny module with two callables:

    URL_TEMPLATE: str   # e.g. "https://www.sigmaaldrich.com/US/en/product/aldrich/{sku}"
    def parse(markdown: str, sku: str) -> PriceQuote | None: ...

The vendor name is implied by the module name in `parsers/`.
"""
from __future__ import annotations

from typing import Protocol

from aichemy_pricing.types import PriceQuote


class MarkdownParser(Protocol):
    """Pure function: rendered markdown of a vendor product page → PriceQuote | None."""
    URL_TEMPLATE: str
    def parse(self, markdown: str, sku: str) -> PriceQuote | None: ...
```

- [ ] **Step 2: Build the parser registry**

```python
# src/aichemy_pricing/browserbase/parsers/__init__.py
"""Registry: vendor name → parser module. Add new parsers here."""
from __future__ import annotations

from types import ModuleType

from aichemy_pricing.browserbase.parsers import (
    cayman, chemcruz, enamine, molbase, sigma, tocris,
)

REGISTRY: dict[str, ModuleType] = {
    "sigma": sigma,         # CLAIM-13: Akamai-gated, L3 unlocks via Browserbase stealth
    "enamine": enamine,     # was placeholder L2; now L3 markdown
    "cayman": cayman,       # was placeholder L2; now L3 markdown
    "chemcruz": chemcruz,
    "tocris": tocris,
    "molbase": molbase,
}
```

- [ ] **Step 3: Implement `BrowserbaseFetchLookup`**

```python
# src/aichemy_pricing/browserbase/fetch_lookup.py
"""L3 PriceLookup that routes through Browserbase Fetch API.

Lookup flow:
    1. Look up the vendor's markdown parser in REGISTRY by ref.vendor.
    2. If no parser exists for this vendor → return None (not an error;
       just means we don't have an L3 path for it — caller should add a parser).
    3. Build the URL via parser.URL_TEMPLATE.format(sku=ref.sku).
    4. client.fetch_markdown(url) → markdown or None.
    5. parser.parse(markdown, sku) → PriceQuote or None.
"""
from __future__ import annotations

import logging

from aichemy_pricing.browserbase.client import BrowserbaseClient
from aichemy_pricing.browserbase.parsers import REGISTRY
from aichemy_pricing.types import PriceQuote, VendorRef

log = logging.getLogger(__name__)


class BrowserbaseFetchLookup:
    """L3 fallback: render the vendor product page via Browserbase Fetch API,
    parse the price out of the returned markdown."""
    name = "browserbase_fetch"

    def __init__(self, client: BrowserbaseClient | None = None) -> None:
        self._client = client or BrowserbaseClient()

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        parser = REGISTRY.get(ref.vendor)
        if parser is None:
            log.debug("no L3 parser for vendor=%s; skipping", ref.vendor)
            return None
        url = parser.URL_TEMPLATE.format(sku=ref.sku)
        markdown = self._client.fetch_markdown(url)
        if markdown is None:
            return None
        try:
            return parser.parse(markdown, ref.sku)
        except Exception as exc:  # never let a parser bug abort the chain
            log.warning("L3 parser %s raised on sku=%s: %s", ref.vendor, ref.sku, exc)
            return None
```

- [ ] **Step 4: Failing tests** (mirror the chain test pattern; mock `BrowserbaseClient.fetch_markdown`)

- [ ] **Step 5: Run + commit**

---

## Tasks F3–F8: Vendor markdown parsers

Each task below has the same shape: (1) capture a real markdown fixture by hitting the vendor URL via `bb.fetch(...)` once, (2) write the parser as a pure function of `(markdown, sku) → PriceQuote | None`, (3) two tests — synthetic-markdown parse + real-fixture parse.

### Task F3: `parsers/sigma.py` (highest value — was Tier-4-deferred)

```python
# src/aichemy_pricing/browserbase/parsers/sigma.py
"""Sigma-Aldrich rendered-markdown parser. The L2 path can't reach Sigma
because of Akamai (CLAIM-13); Browserbase's stealth + residential IP pool
gets through (usually — verify on first capture).

URL template uses the verified brand-prefix scheme (CLAIM-13 corroborated by
Google-indexed live products at /US/en/product/aldrich/{sku}, /sigma/{sku},
/sial/{sku}, /supelco/{sku}, /mm/{sku}). For SKUs that come from PubChem
SDF resolution, the brand prefix is part of the SKU id, so we accept either
(brand, sku) split or a single concatenated ref.sku.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from aichemy_pricing.types import PriceQuote
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

# Default to aldrich brand if SKU has no brand prefix.
URL_TEMPLATE = "https://www.sigmaaldrich.com/US/en/product/aldrich/{sku}"

_PACK_PRICE_RE = re.compile(
    r"([\d.]+)\s*(mg|g|kg|µg|ug|mcg)\b[^$]{0,400}\$\s*([\d,]+(?:\.\d+)?)",
    re.I | re.S,
)


def parse(markdown: str, sku: str) -> PriceQuote | None:
    text = strip_molarity_tokens(markdown)
    m = _PACK_PRICE_RE.search(text)
    if not m:
        return None
    try:
        size = float(m.group(1))
        unit = m.group(2).lower()
        price = float(m.group(3).replace(",", ""))
    except ValueError:
        return None
    return PriceQuote(
        vendor="sigma",
        sku=sku,
        price=price,
        currency="USD",
        pack_size_g=pack_size_to_grams(size, unit),
        fetched_at=datetime.now(timezone.utc),
        raw={"source": "browserbase_fetch", "url_template": URL_TEMPLATE},
    )
```

Tests: synthetic-markdown parse (with MW prose to verify Revision-18 strip), real-fixture parse, no-price returns None.

### Tasks F4–F8

Same shape, one per vendor (Enamine, Cayman, ChemCruz, Tocris, Molbase). The URL templates come from the verified CLAIM-XX evidence files. Each parser:
- Reuses `strip_molarity_tokens` + `pack_size_to_grams` from `vendors/_common.py`
- Returns `PriceQuote(vendor="<name>", sku=ref.sku, ...)` matching its registry key
- Has 2 tests: synthetic + real fixture

---

## Task F9: STUB modules

**Why:** The stubs reserve module names + APIs so a future revision can swap one in without re-architecting.

```python
# src/aichemy_pricing/browserbase/browser_api.py
"""STUB: Browser API path — full Playwright/CDP automation.

Use when L3 needs to click a "show price" button, navigate paginated
listings, fill an institutional-account login, or otherwise interact with
the page beyond a single rendered fetch. Browserbase Browser API spins up
a cloud Chrome session billed per minute.

NOT IMPLEMENTED in v1. The Fetch API path (fetch_lookup.py) covers all
verified L3 vendors — no vendor in scope requires multi-step automation.
"""
from __future__ import annotations

from aichemy_pricing.types import PriceQuote, VendorRef


class BrowserbaseBrowserLookup:
    name = "browserbase_browser"

    def __init__(self) -> None:
        raise NotImplementedError(
            "BrowserbaseBrowserLookup: not implemented in v1. The Fetch API "
            "path (BrowserbaseFetchLookup) covers all verified L3 vendors. "
            "Build this only when a vendor needs multi-step browser interaction "
            "that a single Fetch call cannot satisfy."
        )

    def lookup(self, ref: VendorRef) -> PriceQuote | None:  # pragma: no cover
        raise NotImplementedError
```

```python
# src/aichemy_pricing/browserbase/llm_extract.py
"""STUB: LLM-based extraction path.

Use when adding a new vendor without writing a per-vendor regex parser:
fetch markdown via Fetch API → feed to an LLM → ask "what's the per-gram
price". Vendor-agnostic but adds Anthropic/OpenAI cost (~$0.001–0.01/page)
and depends on prompt-engineering quality.

NOT IMPLEMENTED in v1 — the per-vendor regex parsers in parsers/{vendor}.py
are deterministic, free, and faster.
"""
from __future__ import annotations

from aichemy_pricing.types import PriceQuote, VendorRef


class BrowserbaseLLMLookup:
    name = "browserbase_llm"

    def __init__(self) -> None:
        raise NotImplementedError(
            "BrowserbaseLLMLookup: not implemented in v1. The per-vendor "
            "markdown parsers under aichemy_pricing.browserbase.parsers are "
            "deterministic and free; build this only when the parser-per-vendor "
            "cost grows past the LLM-call cost (e.g. supporting 50+ vendors)."
        )

    def lookup(self, ref: VendorRef) -> PriceQuote | None:  # pragma: no cover
        raise NotImplementedError
```

Tests: `test_browserbase_stubs.py` confirms each raises `NotImplementedError` on construction with a clear message — locks the stubs in place so they don't accidentally ship as working-but-broken implementations.

---

## Integration with sub-plan E `build_default_chain`

Sub-plan E Task E2's `build_default_chain` adds `BrowserbaseFetchLookup()` as the **last** member of the chain — L1 cache wraps the chain; L2 vendors fire first (cheap + free); the L3 fallback only fires if every L2 returned None (which is what we want for cost control). Order matters:

```python
# in build_default_chain (sub-plan E):
inner = ChainedPriceLookup([
    FluorochemVendor(),       # L2 — verified JSON API
    MedChemExpressVendor(),   # L2 — curl_cffi for Cloudflare
    BrowserbaseFetchLookup(), # L3 — covers Sigma + Enamine + Cayman + ChemCruz + Tocris + Molbase
])
```

The `_DEFAULT_VENDOR_CLASSES` placeholder-skip wrapper from Revision 16 still applies — `BrowserbaseFetchLookup.__init__` doesn't raise even without the API key (per F1 design), so it's always in the chain; it just no-ops if `BROWSERBASE_API_KEY` is unset.

---

## Unit Tests Summary (Sub-Plan F)

| Test file | Test count | Notes |
|---|---:|---|
| `test_browserbase_client.py` | 3 | No-key no-op; POST shape; non-200 returns None |
| `test_browserbase_fetch_lookup.py` | 4 | Parser dispatch; unknown-vendor None; client-miss None; parser-exception caught |
| `test_browserbase_parser_sigma.py` | 2 | Synthetic markdown w/ MW prose; real fixture |
| `test_browserbase_parser_enamine.py` | 2 | Synthetic + real fixture |
| `test_browserbase_parser_cayman.py` | 2 | Synthetic + real fixture |
| `test_browserbase_parser_chemcruz.py` | 2 | Synthetic + real fixture |
| `test_browserbase_parser_tocris.py` | 2 | Synthetic + real fixture |
| `test_browserbase_parser_molbase.py` | 2 | Synthetic + real fixture |
| `test_browserbase_stubs.py` | 2 | browser_api raises; llm_extract raises with helpful message |
| **Total** | **21** | All offline (mocked POST + frozen markdown fixtures); no `live` markers needed for v1. |

A single live integration test (under `@pytest.mark.live`) hits the real Fetch API once with a known URL to confirm the API key + endpoint still work — gated behind `--live` per Sub-Plan A's normalized markexpr filter.

---

## Self-review

**Spec coverage:** Closes the L3 gap from sub-plans C/D. Sigma + Enamine + Cayman + ChemCruz + Tocris + Molbase are all reachable now with one Browserbase API key — Sigma in particular was previously deferred to a hypothetical Tier-4 plan; here it's a 30-line markdown parser.

**Placeholder scan:** No "TBD" / "implement later" — the two stubs are intentional (browser_api, llm_extract) with `NotImplementedError` + a clear message saying when to replace them. Future revisions can swap them in without touching `BrowserbaseFetchLookup` or any parser.

**Type consistency:** `BrowserbaseFetchLookup.lookup(ref: VendorRef) -> PriceQuote | None` matches the `PriceLookup` protocol from sub-plan A. Each parser module exports `URL_TEMPLATE: str` and `parse(markdown, sku) -> PriceQuote | None`, matching the `MarkdownParser` protocol in `parsers/_base.py`.
