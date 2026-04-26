"""Unit tests for the data types. No I/O; pure pydantic."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef


def test_price_quote_normalizes_currency_uppercase() -> None:
    q = PriceQuote(
        vendor="fluorochem",
        sku="F765353-1G",
        price=230.0,
        currency="gbp",  # lowercase input
        pack_size_g=1.0,
        fetched_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )
    assert q.currency == "GBP"
    assert q.price_per_gram_native == 230.0


def test_price_quote_rejects_non_positive_price() -> None:
    base = dict(
        vendor="x",
        sku="y",
        currency="USD",
        pack_size_g=1.0,
        fetched_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError):
        PriceQuote(price=-1.0, **base)
    with pytest.raises(ValidationError):
        PriceQuote(price=0.0, **base)


def test_price_quote_rejects_non_positive_pack_size() -> None:
    with pytest.raises(ValidationError):
        PriceQuote(
            vendor="x",
            sku="y",
            price=1.0,
            currency="USD",
            pack_size_g=0.0,
            fetched_at=datetime.now(timezone.utc),
        )


def test_resolver_hit_carries_inchikey_vendor_sku() -> None:
    h = ResolverHit(
        inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        vendor="enamine",
        sku="EN300-7605608",
    )
    assert h.vendor == "enamine"
    assert h.sku == "EN300-7605608"


def test_resolver_hit_rejects_short_inchikey() -> None:
    with pytest.raises(ValidationError):
        ResolverHit(inchikey="too-short", vendor="x", sku="y")


def test_vendor_ref_does_not_require_url() -> None:
    r = VendorRef(vendor="fluorochem", sku="F765353-1G")
    assert r.canonical_url is None


def test_price_quote_per_gram_with_pack_size() -> None:
    q = PriceQuote(
        vendor="x",
        sku="y",
        price=300.0,
        currency="USD",
        pack_size_g=5.0,
        fetched_at=datetime.now(timezone.utc),
    )
    assert q.price_per_gram_native == 60.0
