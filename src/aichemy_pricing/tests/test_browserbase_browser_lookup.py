"""Unit tests for BrowserbaseBrowserLookup.

Mocks the Playwright/Browserbase session via the ``browser_session`` context
manager so tests are fully offline. Live tests require BROWSERBASE_API_KEY
and are marked ``@pytest.mark.live``.
"""

from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from aichemy_pricing.browserbase import browser_api as browser_api_mod
from aichemy_pricing.browserbase import browser_parsers as browser_parsers_pkg
from aichemy_pricing.browserbase.browser_api import BrowserbaseBrowserLookup
from aichemy_pricing.types import PriceQuote, VendorRef


def _quote(vendor: str = "stub") -> PriceQuote:
    return PriceQuote(
        vendor=vendor,
        sku="x",
        price=1.0,
        currency="USD",
        pack_size_g=1.0,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _stub_parser(
    returns: PriceQuote | None = None,
    raises: Exception | None = None,
    record: list[tuple[str, str]] | None = None,
    wait_ms: int = 0,
) -> SimpleNamespace:
    def parse(markdown: str, sku: str) -> PriceQuote | None:
        if record is not None:
            record.append((markdown, sku))
        if raises is not None:
            raise raises
        return returns

    return SimpleNamespace(
        URL_TEMPLATE="https://example.test/{sku}",
        WAIT_AFTER_LOAD_MS=wait_ms,
        parse=parse,
    )


def _fake_session_factory(page: MagicMock | None):
    """Build a context-manager that yields ``page`` (or None for unconfigured)."""

    @contextlib.contextmanager
    def factory(api_key=None, project_id=None):
        yield page

    return factory


def test_returns_none_when_vendor_not_in_registry() -> None:
    out = BrowserbaseBrowserLookup().lookup(VendorRef(vendor="not-a-real-vendor", sku="x"))
    assert out is None


def test_returns_none_when_session_unconfigured(monkeypatch) -> None:
    monkeypatch.setitem(
        browser_parsers_pkg.REGISTRY, "stub-vendor", _stub_parser(returns=_quote("stub-vendor"))
    )
    monkeypatch.setattr(browser_api_mod, "browser_session", _fake_session_factory(page=None))
    out = BrowserbaseBrowserLookup().lookup(VendorRef(vendor="stub-vendor", sku="abc"))
    assert out is None


def test_navigates_and_dispatches_to_parser(monkeypatch) -> None:
    expected = _quote("stub-vendor")
    record: list[tuple[str, str]] = []
    monkeypatch.setitem(
        browser_parsers_pkg.REGISTRY,
        "stub-vendor",
        _stub_parser(returns=expected, record=record, wait_ms=42),
    )

    page = MagicMock()
    page.content.return_value = "<html><body>10 g $1.00</body></html>"
    monkeypatch.setattr(browser_api_mod, "browser_session", _fake_session_factory(page=page))

    out = BrowserbaseBrowserLookup().lookup(VendorRef(vendor="stub-vendor", sku="abc"))
    assert out is expected
    page.goto.assert_called_once_with("https://example.test/abc", wait_until="load")
    page.wait_for_timeout.assert_called_once_with(42)
    assert len(record) == 1
    assert record[0][1] == "abc"
    # html2text-converted markdown reaches the parser, not raw HTML.
    assert "<html>" not in record[0][0]


def test_returns_none_when_navigation_raises(monkeypatch) -> None:
    monkeypatch.setitem(
        browser_parsers_pkg.REGISTRY, "stub-vendor", _stub_parser(returns=_quote("stub-vendor"))
    )
    page = MagicMock()
    page.goto.side_effect = RuntimeError("net::ERR_TIMED_OUT")
    monkeypatch.setattr(browser_api_mod, "browser_session", _fake_session_factory(page=page))

    out = BrowserbaseBrowserLookup().lookup(VendorRef(vendor="stub-vendor", sku="abc"))
    assert out is None


def test_returns_none_when_parser_raises(monkeypatch) -> None:
    monkeypatch.setitem(
        browser_parsers_pkg.REGISTRY,
        "stub-vendor",
        _stub_parser(raises=RuntimeError("boom")),
    )
    page = MagicMock()
    page.content.return_value = "<html></html>"
    monkeypatch.setattr(browser_api_mod, "browser_session", _fake_session_factory(page=page))

    out = BrowserbaseBrowserLookup().lookup(VendorRef(vendor="stub-vendor", sku="abc"))
    assert out is None


@pytest.mark.live
def test_browser_lookup_live_enamine() -> None:
    """Hits real Browserbase Browser API against Enamine. Requires BROWSERBASE_API_KEY."""
    if not os.environ.get("BROWSERBASE_API_KEY"):
        pytest.skip("BROWSERBASE_API_KEY not set")
    out = BrowserbaseBrowserLookup().lookup(VendorRef(vendor="enamine", sku="EN300-7605608"))
    # Either the SPA hydrated and we got a quote, or the upstream had no
    # price for this SKU and we got None — both are acceptable; the point
    # is no exception escapes and (when present) the quote is well-formed.
    assert out is None or (out.vendor == "enamine" and out.price > 0 and out.pack_size_g > 0)
