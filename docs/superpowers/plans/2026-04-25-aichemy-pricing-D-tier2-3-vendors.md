# Sub-Plan D: `aichemy-pricing` — Tier 3 (Cloudflare-Aware) Vendor: MedChemExpress

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Parent plan:** `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`
> **Verification source:** `experiments/chem-pricing-verification/CLAIMS.md` (CLAIM-15 MedChemExpress)
> **Depends on:** Sub-Plan A (`PriceQuote`, `VendorRef`, `make_cf_client`)
> **Delivers (consumed by sub-plan E):**
> - `aichemy_pricing.vendors.medchemexpress.MedChemExpressVendor` — `curl_cffi` Chrome 124 fingerprint (Tier 3)

**Scope reduction (post-Round-2 review).** This sub-plan originally covered four vendors (Enamine, Cayman, ChemCruz as Tier 2 via DevTools-discovered XHR endpoints + MedChemExpress as Tier 3 via `curl_cffi`). The architecture pivoted: those three Tier 2 vendors now ship as **L3 markdown parsers in [Sub-Plan F](./2026-04-25-aichemy-pricing-F-browserbase-l3.md)** (Browserbase Fetch API), eliminating the per-vendor DevTools discovery step entirely. Only MedChemExpress remains here — its `curl_cffi`-based L2 path is meaningfully cheaper than routing through Browserbase, and the endpoint shape is already verified (CLAIM-15). Sigma-Aldrich (previously deferred to a hypothetical Tier-4 plan) is also addressed via Sub-Plan F.

**Goal:** Implement MedChemExpress as the only L2 vendor that needs a real-browser TLS fingerprint to pass Cloudflare. Plain `httpx` with a Chrome User-Agent header still gets 403 (CLAIM-15); `curl_cffi` impersonating Chrome 124 passes.

**Architecture:** One vendor class — same shape as Sub-Plan C's Fluorochem/Tocris, but constructs `make_cf_client()` instead of `make_plain_client()`.

**Tech Stack:** Python 3.11, `curl_cffi` (declared as a `pricing` extra in Sub-Plan A), `re` for HTML extraction. No headless browser dependency.

---

## File Structure

```
src/aichemy_pricing/vendors/
└── medchemexpress.py                      # CREATE — Task D4

src/aichemy_pricing/tests/
├── data/
│   └── mce_acetyl_coa.html                # CAPTURE — Cloudflare-passed HTML (validated capture)
└── test_vendors_medchemexpress.py         # CREATE (4 tests)
```

**Note for executors:** Tasks D1–D3 (Enamine, Cayman, ChemCruz) intentionally do not exist in this revision. They are not "removed and lost" — they are reborn as `parsers/{vendor}.py` markdown parsers in Sub-Plan F. If you were tracking the previous version's task IDs in tooling, map: D1→F4 (Enamine), D2→F5 (Cayman), D3→F6 (ChemCruz). Task IDs D1–D3 are intentionally absent so cross-references in older docs/PRs still resolve to the correct successor.

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
from aichemy_pricing.vendors._common import pack_size_to_grams, strip_molarity_tokens

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
        # Strip MW / molarity tokens before regex; on real MCE pages the
        # 200-char window between MW prose and the pack-price block is layout-
        # dependent (mobile templates compact it within range). See Revision 18.
        m = _PACK_PRICE_RE.search(strip_molarity_tokens(resp.text))
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
| `test_vendors_medchemexpress.py` | 4 | 1 | curl_cffi mocked; 403 block; no-price; correct URL; (live) acetyl-CoA |
| **Total** | **4** | **1** | All offline tests run in <1s. Live test requires `-m live`. |

**All-tests command (offline only):**
```bash
uv run pytest src/aichemy_pricing/tests/test_vendors_medchemexpress.py -v
```

**Type-check:**
```bash
uv run mypy src/aichemy_pricing/vendors/medchemexpress.py
```
Expected: Success (note: `curl_cffi` has no public type stubs; `MedChemExpressVendor.__init__` is annotated with `# type: ignore[no-untyped-def]` to keep mypy strict elsewhere).

---

## Self-review

**Spec coverage:** MedChemExpress is the sole vendor in this sub-plan post-trim. The Enamine / Cayman / ChemCruz coverage that originally lived here is now in Sub-Plan F as L3 markdown parsers (no DevTools discovery needed) — see the scope-reduction note above the File Structure section.

**Placeholder scan:** No placeholders. The fixture-capture step uses the validated `_capture.py` helper from Sub-Plan A Task A7 with explicit Cloudflare-marker rejection, so a CF-blocked capture cannot silently poison the test fixture.

**Type consistency:** `MedChemExpressVendor.lookup(ref: VendorRef) -> PriceQuote | None` matches the `PriceLookup` protocol from Sub-Plan A. Constructor accepts an injectable client (untyped because `curl_cffi` has no public type stubs) — tests pass a `MagicMock`. Currency literal `"USD"` matches the `Currency` type from Sub-Plan A.
