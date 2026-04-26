"""Unit tests for `aichemy-price` CLI."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from aichemy_pricing import cli as cli_module
from aichemy_pricing.cli import app
from aichemy_pricing.types import PriceQuote, VendorRef


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_version_flag(runner: CliRunner) -> None:
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    from aichemy_pricing import __version__

    assert __version__ in res.stdout


def test_cli_lookup_unknown_vendor_returns_2(runner: CliRunner) -> None:
    res = runner.invoke(app, ["lookup", "no-such-vendor", "X"])
    assert res.exit_code == 2
    assert "Unknown vendor" in (res.stdout + (res.stderr or ""))


def test_cli_lookup_calls_vendor(runner: CliRunner, monkeypatch) -> None:
    captured: dict[str, object] = {}
    quote = PriceQuote(
        vendor="fluorochem",
        sku="F765353-1G",
        price=230.0,
        currency="GBP",
        pack_size_g=1.0,
        fetched_at=datetime(2026, 4, 25, tzinfo=UTC),
    )

    class FakeVendor:
        name = "fluorochem"

        def lookup(self, ref: VendorRef) -> PriceQuote:
            captured["ref"] = ref
            return quote

    monkeypatch.setitem(cli_module._VENDORS, "fluorochem", FakeVendor)
    res = runner.invoke(app, ["lookup", "fluorochem", "F765353-1G"])
    assert res.exit_code == 0
    assert "230" in res.stdout and "GBP" in res.stdout
    assert isinstance(captured["ref"], VendorRef)


def test_cli_lookup_json_flag_dumps_pricequote(
    runner: CliRunner, monkeypatch
) -> None:
    quote = PriceQuote(
        vendor="fluorochem",
        sku="F1-1G",
        price=1.0,
        currency="USD",
        pack_size_g=1.0,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    class FakeVendor:
        name = "fluorochem"

        def lookup(self, ref: VendorRef) -> PriceQuote:
            return quote

    monkeypatch.setitem(cli_module._VENDORS, "fluorochem", FakeVendor)
    res = runner.invoke(app, ["lookup", "fluorochem", "F1-1G", "--json"])
    assert res.exit_code == 0
    parsed = json.loads(res.stdout)
    assert parsed["price"] == 1.0
    assert parsed["currency"] == "USD"


def test_cli_lookup_returns_1_when_no_quote(
    runner: CliRunner, monkeypatch
) -> None:
    class MissVendor:
        name = "fluorochem"

        def lookup(self, ref: VendorRef) -> None:
            return None

    monkeypatch.setitem(cli_module._VENDORS, "fluorochem", MissVendor)
    res = runner.invoke(app, ["lookup", "fluorochem", "x"])
    assert res.exit_code == 1


def test_cli_lookup_placeholder_vendor_returns_2(
    runner: CliRunner, monkeypatch
) -> None:
    """Vendors with unfilled discovery placeholders raise NotImplementedError
    from __init__ (fail-loud guard). The CLI must surface a clean
    typer.Exit(2), not a bare Python traceback."""

    class _Placeholder:
        name = "fluorochem"

        def __init__(self) -> None:
            raise NotImplementedError("_API_URL not yet discovered")

    monkeypatch.setitem(cli_module._VENDORS, "fluorochem", _Placeholder)
    res = runner.invoke(app, ["lookup", "fluorochem", "X"])
    assert res.exit_code == 2
    out = (res.stdout + (res.stderr or "")).lower()
    assert "discovery placeholder" in out
