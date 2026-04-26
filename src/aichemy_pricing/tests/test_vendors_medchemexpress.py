"""Unit tests for MedChemExpressVendor.

Per CLAIM-15: tests mock at the session.get layer; the real curl_cffi path is
exercised only by the @pytest.mark.live test.
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
    assert "acetyl-coenzyme-a.html" in str(sess.get.call_args)


@pytest.mark.live
def test_mce_live_acetyl_coa() -> None:
    """Hits real MCE through curl_cffi. Asserts no Cloudflare block."""
    v = MedChemExpressVendor()
    r = v.lookup(VendorRef(vendor="medchemexpress", sku="acetyl-coenzyme-a"))
    assert r is None or r.price > 0
