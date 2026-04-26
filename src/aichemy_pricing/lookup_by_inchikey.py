"""Adapter that composes a VendorResolver with a PriceLookup chain.

Caller asks: "give me a price for this InChIKey".
Internals:
  1. resolver.resolve(ik) -> list[ResolverHit] (in vendor priority order)
  2. for each hit, build VendorRef(vendor=hit.vendor, sku=hit.sku, ...)
     and call chain.lookup(ref) -> PriceQuote | None
  3. return first non-None quote, or None if every hit misses.
"""

from __future__ import annotations

from dataclasses import dataclass

from aichemy_pricing.protocol import PriceLookup, VendorResolver
from aichemy_pricing.types import PriceQuote, VendorRef


@dataclass
class LookupByInchikey:
    resolver: VendorResolver
    chain: PriceLookup

    def lookup(self, inchikey: str) -> PriceQuote | None:
        for hit in self.resolver.resolve(inchikey):
            ref = VendorRef(vendor=hit.vendor, sku=hit.sku, canonical_url=hit.canonical_url)
            quote = self.chain.lookup(ref)
            if quote is not None:
                return quote
        return None
