"""Compose multiple `VendorResolver`s and dedup their hits.

Lets a narrow-but-exact resolver (e.g., `EnamineSdfResolver`, which only
yields Enamine SKUs but with high confidence) try ahead of a broad-but-
indirect one (`PubChemCompoundResolver`, which covers many vendors via
PubChem's Substance->CID->Compound JOIN). Order matters for confidence,
not correctness — dedup is keyed on `(vendor, sku)` so a later resolver
returning the same hit is dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

from aichemy_pricing.protocol import VendorResolver
from aichemy_pricing.types import ResolverHit


@dataclass
class ChainedVendorResolver:
    members: list[VendorResolver]
    name: str = "chained"

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        seen: set[tuple[str, str]] = set()
        out: list[ResolverHit] = []
        for member in self.members:
            for hit in member.resolve(inchikey):
                key = (hit.vendor, hit.sku)
                if key in seen:
                    continue
                seen.add(key)
                out.append(hit)
        return out
