"""Parse PubChem Substance SDF (FTP dump) into an InChIKey → ResolverHit index.

Per CLAIM-04 (PARTIAL):
  Source URL: https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/
  Real tag names (from `pubchem_sdtags.txt`):
    PUBCHEM_EXT_DATASOURCE_NAME   ← vendor name
    PUBCHEM_EXT_DATASOURCE_REGID  ← vendor SKU
    PUBCHEM_EXT_DATASOURCE_URL    ← canonical product URL (optional)
  Total source table: 914 sources / 531 vendor-tagged.
  ~491M SIDs across 982 files; production runs MUST set `allowed_sources`
  to keep memory bounded.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.resolvers._sdf import iter_sdf_records
from aichemy_pricing.types import ResolverHit


def _first(rec: dict[str, list[str]], tag: str) -> str | None:
    v = rec.get(tag)
    return v[0] if v else None


@dataclass
class PubChemSdfResolver:
    name: str = "pubchem_sdf"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(
        cls,
        paths: list[Path],
        allowed_sources: set[str] | None = None,
    ) -> PubChemSdfResolver:
        self = cls()
        for path in paths:
            for rec in iter_sdf_records(Path(path)):
                ik = _first(rec, "PUBCHEM_IUPAC_INCHIKEY")
                src = _first(rec, "PUBCHEM_EXT_DATASOURCE_NAME")
                regid = _first(rec, "PUBCHEM_EXT_DATASOURCE_REGID")
                url = _first(rec, "PUBCHEM_EXT_DATASOURCE_URL")
                if not (ik and src and regid):
                    continue
                if allowed_sources is not None and src not in allowed_sources:
                    continue
                self.index[ik].append(
                    ResolverHit(inchikey=ik, vendor=src, sku=regid, canonical_url=url)
                )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
