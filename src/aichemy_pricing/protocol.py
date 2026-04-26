"""Structural protocols. Implementations live in `vendors/` and `resolvers/`."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef


@runtime_checkable
class PriceLookup(Protocol):
    """Maps a `VendorRef` to a `PriceQuote`, or None if unknown."""

    name: str

    def lookup(self, ref: VendorRef) -> PriceQuote | None: ...


@runtime_checkable
class VendorResolver(Protocol):
    """Maps an InChIKey to zero-or-more vendor SKUs (offline JOIN, no network)."""

    name: str

    def resolve(self, inchikey: str) -> list[ResolverHit]: ...
