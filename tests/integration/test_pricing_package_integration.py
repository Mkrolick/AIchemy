"""End-to-end: AIchemy pipeline picks up aichemy_pricing as a backend.

Offline only — uses captured Fluorochem fixture bytes via httpx.Client.send
monkeypatching. Skipped at collection time when the pricing extra is absent.
"""
from __future__ import annotations

import typing
from pathlib import Path

import httpx
import pytest

# Skip at collection time if pricing extra isn't installed.
pytest.importorskip("aichemy_pricing")


def test_fx_table_covers_every_currency_literal() -> None:
    """The _InchikeyAdapter returns None when a quote arrives in a currency
    missing from the FX table, with a warning log. That's a silent yield drop
    waiting to happen if anyone adds a new Currency literal without also
    extending the FX table. Lock that invariant in (Revision 10).
    """
    from aichemy.preprocessing.augment.prices import _FX_TO_USD_AS_OF_2026_04_25
    from aichemy_pricing.types import Currency

    declared_currencies = set(typing.get_args(Currency))
    fx_currencies = set(_FX_TO_USD_AS_OF_2026_04_25)
    missing = declared_currencies - fx_currencies
    assert not missing, (
        f"Currency literal members missing from FX table: {missing}. "
        f"Either add an FX rate or shrink the Currency literal."
    )


def test_aichemy_pricing_chain_round_trips_fluorochem_fixture(
    tmp_path, monkeypatch
) -> None:
    """Build the default chain, intercept the fluorochem URL with the
    captured fixture bytes, and confirm a round-trip PriceQuote with the
    expected currency + price."""
    from aichemy_pricing import build_default_chain
    from aichemy_pricing.types import VendorRef

    fixture = Path(
        "src/aichemy_pricing/tests/data/fluorochem_F765353.json"
    ).read_bytes()

    def mock_send(self, request, **kw):  # noqa: ARG001
        if "fluorochem" in str(request.url):
            return httpx.Response(200, content=fixture, request=request)
        return httpx.Response(404, request=request)

    monkeypatch.setattr(httpx.Client, "send", mock_send)

    chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    quote = chain.lookup(VendorRef(vendor="fluorochem", sku="F765353-1G"))
    assert quote is not None
    assert quote.currency == "GBP"
    assert quote.price == 230.0
