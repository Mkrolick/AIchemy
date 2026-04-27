"""Tests for `ChainedVendorResolver`."""

from __future__ import annotations

from dataclasses import dataclass

from aichemy_pricing.resolvers.chained import ChainedVendorResolver
from aichemy_pricing.types import ResolverHit


@dataclass
class _StubResolver:
    name: str
    hits: dict[str, list[ResolverHit]]

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.hits.get(inchikey, []))


_IK = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"  # aspirin (real 27-char InChIKey)


def test_chained_returns_union_in_member_order() -> None:
    a = _StubResolver(
        "enamine_sdf",
        {_IK: [ResolverHit(inchikey=_IK, vendor="enamine", sku="EN-1")]},
    )
    b = _StubResolver(
        "pubchem_compound",
        {_IK: [ResolverHit(inchikey=_IK, vendor="sigma", sku="A5376")]},
    )
    c = ChainedVendorResolver(members=[a, b])
    out = c.resolve(_IK)
    assert [(h.vendor, h.sku) for h in out] == [
        ("enamine", "EN-1"),
        ("sigma", "A5376"),
    ]


def test_chained_dedupes_on_vendor_sku_pair() -> None:
    """Two resolvers with the same (vendor, sku) -> first one wins."""
    a = _StubResolver(
        "enamine_sdf",
        {_IK: [ResolverHit(inchikey=_IK, vendor="enamine", sku="EN-1", canonical_url="A")]},
    )
    b = _StubResolver(
        "pubchem_compound",
        {
            _IK: [
                ResolverHit(inchikey=_IK, vendor="enamine", sku="EN-1", canonical_url="B"),
                ResolverHit(inchikey=_IK, vendor="sigma", sku="A5376"),
            ]
        },
    )
    c = ChainedVendorResolver(members=[a, b])
    out = c.resolve(_IK)
    assert [(h.vendor, h.sku, h.canonical_url) for h in out] == [
        ("enamine", "EN-1", "A"),  # first writer wins
        ("sigma", "A5376", None),
    ]


def test_chained_returns_empty_when_no_member_has_hit() -> None:
    a = _StubResolver("enamine_sdf", {})
    b = _StubResolver("pubchem_compound", {})
    c = ChainedVendorResolver(members=[a, b])
    assert c.resolve(_IK) == []


def test_chained_with_no_members_returns_empty() -> None:
    c = ChainedVendorResolver(members=[])
    assert c.resolve(_IK) == []
