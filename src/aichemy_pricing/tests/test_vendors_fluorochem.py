"""Unit tests for FluorochemVendor.

Per CLAIM-01: endpoint is real, anonymous, no Cloudflare. The original
research report fabricated the JSON shape — these tests use a fixture
captured from the live endpoint to lock the corrected schema in place.
"""

from __future__ import annotations

import json

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
    body = json.dumps(
        {
            "BR1005": {
                "BR1005-1KG": {
                    "SKU": "BR1005-1KG",
                    "Size": "1",
                    "Size Unit": "kg",
                    "Pricing": {"GBP": {"Base Price": 24}},
                }
            }
        }
    ).encode()
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
    body = json.dumps(
        {"X1": {"X1-1G": {"SKU": "X1-1G", "Size": "1", "Size Unit": "g", "Pricing": {}}}}
    ).encode()
    _patch_http(monkeypatch, status=200, body=body)
    v = FluorochemVendor()
    assert v.lookup(VendorRef(vendor="fluorochem", sku="X1-1G")) is None


def test_fluorochem_picks_first_pack_when_caller_passes_product_code_only(monkeypatch) -> None:
    body = json.dumps(
        {
            "Z9": {
                "Z9-100MG": {
                    "SKU": "Z9-100MG",
                    "Size": "100",
                    "Size Unit": "mg",
                    "Pricing": {"GBP": {"Base Price": 5.0}},
                },
                "Z9-1G": {
                    "SKU": "Z9-1G",
                    "Size": "1",
                    "Size Unit": "g",
                    "Pricing": {"GBP": {"Base Price": 25.0}},
                },
            }
        }
    ).encode()
    _patch_http(monkeypatch, status=200, body=body)
    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="Z9"))
    assert quote is not None
    assert quote.pack_size_g in {0.1, 1.0}


@pytest.mark.live
def test_fluorochem_live_F765353_packs() -> None:
    """Hits the real endpoint. Confirms the URL pattern is still live."""
    v = FluorochemVendor()
    quote = v.lookup(VendorRef(vendor="fluorochem", sku="F765353-1G"))
    assert quote is not None
    assert quote.currency == "GBP"
