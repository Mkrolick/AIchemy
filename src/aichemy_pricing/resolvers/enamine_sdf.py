"""Parse Enamine BB SDFs into an InChIKey → ResolverHit index.

Per CLAIM-08 (VERIFIED): per-functional-class SDFs at
  enamine.net/building-blocks/functional-classes/{acids,boronics,amines,halides}
are anonymously downloadable. Total BB catalog is 2,292,307 (CLAIM-09 — the
original report's 573K was 4× stale).

SKU field name in the SDF varies across exports; we accept any of:
  "Catalog ID", "idnumber", "ID", "EN_ID"
and prefix with EN300- if not already present.

Per CLAIM-07: canonical product URL is
  https://enaminestore.com/catalog/EN300-{N}     (no www)
SKU width is variable (6 to 8+ digits) — regex is `EN300-\\d+`, not strictly 6.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.resolvers._sdf import iter_sdf_records
from aichemy_pricing.types import ResolverHit

_SKU_TAGS = ("Catalog ID", "idnumber", "ID", "EN_ID")
_INCHIKEY_TAGS = ("InChIKey", "INCHIKEY", "PUBCHEM_IUPAC_INCHIKEY")


def _first(rec: dict[str, list[str]], tags: tuple[str, ...]) -> str | None:
    for t in tags:
        v = rec.get(t)
        if v:
            return v[0]
    return None


@dataclass
class EnamineSdfResolver:
    name: str = "enamine_sdf"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(cls, paths: list[Path]) -> "EnamineSdfResolver":
        self = cls()
        for path in paths:
            for rec in iter_sdf_records(Path(path)):
                ik = _first(rec, _INCHIKEY_TAGS)
                sku = _first(rec, _SKU_TAGS)
                if not (ik and sku):
                    continue
                if not sku.startswith("EN300-"):
                    sku = f"EN300-{sku}"
                self.index[ik].append(
                    ResolverHit(
                        inchikey=ik,
                        vendor="enamine",
                        sku=sku,
                        canonical_url=f"https://enaminestore.com/catalog/{sku}",
                    )
                )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
