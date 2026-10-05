"""CLAIM-01: Fluorochem Azure-blob JSON pricing API.

Claim text: `https://fluorochemcouk.blob.core.windows.net/pricing/{SKU}.json`
returns min/max GBP prices, pack-size variants, and per-warehouse stock booleans
(has_stock_uk, has_stock_germany, has_stock_china) for any Fluorochem SKU.
No WAF, no JS rendering, no login.

This test is a STUB; the ralph loop will fill it in and run it. The intent:
    1. Discover one or more real Fluorochem SKUs (browse the public store).
    2. Hit the claimed blob URL for each.
    3. Assert: 200 OK + JSON body with the claimed fields.
    4. If the URL pattern is wrong, search for the actual pricing endpoint
       (devtools network tab analog: search GitHub/forums for the pattern).
"""

from __future__ import annotations

import pytest
from conftest import save_result

CLAIM_ID = "CLAIM-01"


@pytest.mark.skip(reason="STUB - fill in with real SKUs once a Fluorochem SKU is known")
def test_fluorochem_blob_pricing_api(client) -> None:
    sku = "FILL_ME_IN"  # e.g. "020181" - find a real one first
    url = f"https://fluorochemcouk.blob.core.windows.net/pricing/{sku}.json"
    r = client.get(url)
    payload = {
        "claim": CLAIM_ID,
        "url": url,
        "status_code": r.status_code,
        "headers": dict(r.headers),
        "body_preview": r.text[:2000],
    }
    save_result(CLAIM_ID, payload)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    expected_keys = {"min_gbp", "max_gbp"}  # adjust once we see real shape
    missing = expected_keys - set(body.keys())
    assert not missing, f"Missing fields: {missing}; got keys {list(body.keys())}"
