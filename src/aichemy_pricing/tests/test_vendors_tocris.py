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
    def mock_send(self, request, **kw):
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


def test_tocris_does_not_match_molecular_weight_as_pack_size(monkeypatch) -> None:
    """Real product pages render molecular weight ('Molecular Weight: 308.4 g/mol')
    BEFORE the pack-prices block. Without the molarity-token stripper in
    `_common.strip_molarity_tokens`, the regex pairs `308.4 g` with the first
    $price and emits a price ~3 orders of magnitude wrong (e.g. $0.535/g
    instead of $16,500/g for a 10mg pack at $165). Lock that bug closed."""
    body = (
        b"<html><head><title>JW 642 | Tocris Bioscience</title></head>"
        b"<body>"
        b"<div class='properties'>Molecular Weight: 308.4 g/mol</div>"
        b"<div class='molarity'>Stock concentration: 5 mg/mL in DMSO</div>"
        b"<table class='pack-prices'>"
        b"<tr><td>10mg</td><td>$165</td></tr>"
        b"<tr><td>50mg</td><td>$650</td></tr>"
        b"</table></body></html>"
    )
    _patch_http(monkeypatch, status=200, body=body)
    quote = TocrisVendor().lookup(VendorRef(vendor="tocris", sku="jw-642_4906"))
    assert quote is not None
    assert quote.pack_size_g == 0.01, (
        f"got pack_size_g={quote.pack_size_g}; molecular-weight token leaked into pack-size match"
    )
    assert quote.price == 165.0


def test_tocris_returns_none_on_404(monkeypatch) -> None:
    _patch_http(monkeypatch, status=404)
    assert TocrisVendor().lookup(VendorRef(vendor="tocris", sku="nope_0000")) is None


def test_tocris_returns_none_when_no_price_in_html(monkeypatch) -> None:
    _patch_http(monkeypatch, status=200, body=b"<html>no pack table</html>")
    assert TocrisVendor().lookup(VendorRef(vendor="tocris", sku="jw-642_4906")) is None


def test_tocris_uses_correct_url(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def mock_send(self, request, **kw):
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
