"""Unit tests for BrowserbaseFetchLookup."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from aichemy_pricing.browserbase import parsers as parsers_pkg
from aichemy_pricing.browserbase.fetch_lookup import BrowserbaseFetchLookup
from aichemy_pricing.types import PriceQuote, VendorRef


def _stub_parser(
    returns: PriceQuote | None = None,
    raises: Exception | None = None,
    record: list[tuple[str, str]] | None = None,
) -> SimpleNamespace:
    """Return a module-shaped stub usable as a parser registry value."""

    def parse(markdown: str, sku: str) -> PriceQuote | None:
        if record is not None:
            record.append((markdown, sku))
        if raises is not None:
            raise raises
        return returns

    return SimpleNamespace(URL_TEMPLATE="https://example.test/{sku}", parse=parse)


def _quote(vendor: str = "stub") -> PriceQuote:
    return PriceQuote(
        vendor=vendor,
        sku="x",
        price=1.0,
        currency="USD",
        pack_size_g=1.0,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_dispatches_to_parser_when_vendor_in_registry(monkeypatch) -> None:
    expected = _quote("stub-vendor")
    parser = _stub_parser(returns=expected)
    monkeypatch.setitem(parsers_pkg.REGISTRY, "stub-vendor", parser)

    client = MagicMock()
    client.fetch_markdown.return_value = "# Some markdown\n$1.00 / 1g"

    out = BrowserbaseFetchLookup(client=client).lookup(VendorRef(vendor="stub-vendor", sku="abc"))
    assert out is expected
    client.fetch_markdown.assert_called_once_with("https://example.test/abc")


def test_returns_none_when_vendor_not_in_registry() -> None:
    client = MagicMock()
    out = BrowserbaseFetchLookup(client=client).lookup(
        VendorRef(vendor="not-a-real-vendor", sku="x")
    )
    assert out is None
    client.fetch_markdown.assert_not_called()


def test_returns_none_when_client_returns_none(monkeypatch) -> None:
    parse_calls: list[tuple[str, str]] = []
    parser = _stub_parser(returns=_quote("stub2"), record=parse_calls)
    monkeypatch.setitem(parsers_pkg.REGISTRY, "stub2", parser)

    client = MagicMock()
    client.fetch_markdown.return_value = None

    out = BrowserbaseFetchLookup(client=client).lookup(VendorRef(vendor="stub2", sku="abc"))
    assert out is None
    assert parse_calls == []  # parser must not have been called


def test_parser_exception_caught_returns_none(monkeypatch) -> None:
    parser = _stub_parser(raises=RuntimeError("boom"))
    monkeypatch.setitem(parsers_pkg.REGISTRY, "stub3", parser)

    client = MagicMock()
    client.fetch_markdown.return_value = "anything"

    out = BrowserbaseFetchLookup(client=client).lookup(VendorRef(vendor="stub3", sku="abc"))
    assert out is None  # exception swallowed
