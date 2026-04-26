"""Unit tests for ChainedPriceLookup."""

from __future__ import annotations

from datetime import datetime, timezone

from aichemy_pricing.chain import ChainedPriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef


def _q(vendor: str = "x") -> PriceQuote:
    return PriceQuote(
        vendor=vendor,
        sku="s",
        price=1.0,
        currency="USD",
        pack_size_g=1.0,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class _Stub:
    def __init__(self, name: str, ret: PriceQuote | None) -> None:
        self.name = name
        self.ret = ret
        self.calls = 0

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return self.ret


def test_chain_returns_first_hit_and_short_circuits() -> None:
    a = _Stub("a", None)
    b = _Stub("b", _q("b"))
    c = _Stub("c", _q("c"))
    chain = ChainedPriceLookup([a, b, c])
    res = chain.lookup(VendorRef(vendor="any", sku="any"))
    assert res is not None and res.vendor == "b"
    assert (a.calls, b.calls, c.calls) == (1, 1, 0)


def test_chain_returns_none_when_all_miss() -> None:
    a = _Stub("a", None)
    b = _Stub("b", None)
    chain = ChainedPriceLookup([a, b])
    assert chain.lookup(VendorRef(vendor="x", sku="y")) is None
    assert (a.calls, b.calls) == (1, 1)


def test_chain_with_empty_members_returns_none() -> None:
    chain = ChainedPriceLookup([])
    assert chain.lookup(VendorRef(vendor="x", sku="y")) is None


def test_chain_swallows_per_member_exceptions_and_continues() -> None:
    """Mirrors the existing aichemy.preprocessing.augment.prices.ChainedPriceLookup
    contract: 'one source failing shouldn't kill the chain'. A transient
    httpx.ConnectError or similar from any vendor must not abort the dict-comp
    in `augment_prices` — the chain logs it and falls through to the next
    member."""

    class _Boom:
        name = "boom"
        calls = 0

        def lookup(self, ref):
            self.__class__.calls += 1
            raise RuntimeError("simulated transient failure")

    boom = _Boom()
    survivor = _Stub("survivor", _q("survivor"))
    chain = ChainedPriceLookup([boom, survivor])
    out = chain.lookup(VendorRef(vendor="x", sku="y"))
    assert out is not None and out.vendor == "survivor"
    assert _Boom.calls == 1 and survivor.calls == 1
