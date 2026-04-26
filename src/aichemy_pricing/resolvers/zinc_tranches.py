"""Parse ZINC20 2D tranche files into an InChIKey → multi-vendor ResolverHit index.

Per CLAIM-03 (VERIFIED): https://files.docking.org/2D/ hosts ZINC20 tranches.
Per CLAIM-02 (PARTIAL): the report's catitms `count=all` URL 404s anonymously;
use the Tranche Browser instead.

Tranche file format varies across cohorts. Common shapes (tab-separated):
    smiles  zinc_id  [inchikey]  [vendor1:code1;vendor2:code2;...]
…or (rarely):
    inchikey  zinc_id  vendor:supplier_code  smiles

We do not trust column positions. Instead the parser scans each row for:
  • an InChIKey-shaped token (regex `[A-Z]{14}-[A-Z]{10}-[A-Z]`)
  • a vendor-list-shaped token (contains `:`; vendor codes split on `;`)

This makes the resolver robust to layout variation across cohorts.
The `combiblocksbb` short_name is the recognized ZINC short_name for
Combi-Blocks (CLAIM-20).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.types import ResolverHit

_INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def _parse_vendor_field(field_value: str) -> list[tuple[str, str]]:
    """Parse `sigma:E7023;enamine:EN300-12345` → [("sigma","E7023"), ("enamine","EN300-12345")]."""
    out: list[tuple[str, str]] = []
    for token in field_value.split(";"):
        token = token.strip()
        if not token or ":" not in token:
            continue
        vendor, code = token.split(":", 1)
        vendor, code = vendor.strip(), code.strip()
        if vendor and code:
            out.append((vendor, code))
    return out


def _find_inchikey(parts: list[str]) -> str | None:
    for p in parts:
        if _INCHIKEY_RE.match(p.strip()):
            return p.strip()
    return None


def _find_vendor_field(parts: list[str]) -> str | None:
    """Pick the first column that parses as at least one `vendor:code` token."""
    for p in parts:
        if ":" in p and _parse_vendor_field(p):
            return p
    return None


@dataclass
class ZincTrancheResolver:
    name: str = "zinc_tranche"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(cls, paths: list[Path]) -> "ZincTrancheResolver":
        self = cls()
        for path in paths:
            with Path(path).open("rt", errors="replace") as f:
                _header = f.readline()  # discard header row
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 2:
                        continue
                    inchikey = _find_inchikey(parts)
                    if inchikey is None:
                        continue
                    vendor_field = _find_vendor_field(parts)
                    if vendor_field is None:
                        continue
                    for vendor, code in _parse_vendor_field(vendor_field):
                        self.index[inchikey].append(
                            ResolverHit(inchikey=inchikey, vendor=vendor, sku=code)
                        )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
