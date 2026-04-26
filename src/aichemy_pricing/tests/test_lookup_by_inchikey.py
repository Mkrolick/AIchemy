"""Unit tests for LookupByInchikey adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from aichemy_pricing.lookup_by_inchikey import LookupByInchikey
from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef


class _StaticResolver:
    name = "static"

    def __init__(self, hits: list[ResolverHit]) -> None:
        self.hits = hits

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return [h for h in self.hits if h.inchikey == inchikey]


class _ConditionalChain:
    """Returns a price for any ref whose vendor is in `priced_vendors`."""

    name = "chain"

    def __init__(self, priced_vendors: set[str]) -> None:
        self.priced_vendors = priced_vendors

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        if ref.vendor in self.priced_vendors:
            return PriceQuote(
                vendor=ref.vendor,
                sku=ref.sku,
                price=1.0,
                currency="USD",
                pack_size_g=1.0,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        return None


def test_lookup_returns_first_priced_vendor_per_inchikey() -> None:
    ik = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    resolver = _StaticResolver(
        [
            ResolverHit(inchikey=ik, vendor="apollo", sku="X"),  # not priced
            ResolverHit(inchikey=ik, vendor="enamine", sku="EN300-1"),
            ResolverHit(inchikey=ik, vendor="fluorochem", sku="F1-1G"),
        ]
    )
    chain = _ConditionalChain({"enamine", "fluorochem"})
    out = LookupByInchikey(resolver=resolver, chain=chain).lookup(ik)
    assert out is not None
    assert out.vendor == "enamine"  # first priced hit wins


def test_lookup_returns_none_when_no_resolver_hits() -> None:
    resolver = _StaticResolver([])
    chain = _ConditionalChain({"enamine"})
    assert (
        LookupByInchikey(resolver=resolver, chain=chain).lookup("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        is None
    )


def test_lookup_returns_none_when_no_chain_member_prices_any_resolver_hit() -> None:
    ik = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    resolver = _StaticResolver([ResolverHit(inchikey=ik, vendor="apollo", sku="X")])
    chain = _ConditionalChain({"enamine"})  # apollo not in chain
    assert LookupByInchikey(resolver=resolver, chain=chain).lookup(ik) is None
