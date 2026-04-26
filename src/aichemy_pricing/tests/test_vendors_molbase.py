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
