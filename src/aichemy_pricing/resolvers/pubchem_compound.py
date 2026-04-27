"""InChIKey -> vendor SKU resolver via PubChem Substance + SID-Map + Compound JOIN.

Why this exists (the foundational gap that motivates this resolver):
PubChem ships two related dumps. **Substance** records carry the vendor's
`PUBCHEM_EXT_DATASOURCE_NAME` (DSN) + `_REGID` (SKU) + `_URL`, but
vendor-deposited substances do NOT carry `PUBCHEM_IUPAC_INCHIKEY` — the
InChIKey is computed by PubChem's standardization pipeline and only
stored on the linked **Compound** record (CID). The link table is
`SID-Map.gz` (`SID<TAB>CID`).

The original `PubChemSdfResolver` (also in this package) reads only the
Substance dump and requires `PUBCHEM_IUPAC_INCHIKEY` on each record —
which is empty for vendor records, so its index is silently empty. This
resolver does the canonical 3-way JOIN that the original was meant to do.

Three-pass build, single-threaded streaming (memory-bounded):
  1. Stream Substance SDFs; collect `sid -> [(vendor, sku, url), ...]`
     for records whose DSN is in `allowed_sources`.
  2. Stream `SID-Map.gz`; build `cid -> [(vendor, sku, url), ...]` by
     looking up each SID's vendors from pass 1. Drop SIDs whose CID is
     None (deprecated / non-standardized).
  3. Stream Compound SDFs; for each record whose CID is in pass 2,
     read `PUBCHEM_IUPAC_INCHIKEY` and emit one `ResolverHit` per
     vendor entry. Build the final `inchikey -> [ResolverHit, ...]`.

The fully-built index is small enough to persist (parquet, ~50-200 MB
typical for a 6-vendor allowlist). Subsequent runs use `from_cache()`
to skip all three passes (~5 sec deserialize vs ~30-60 min build).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from aichemy_pricing.resolvers._sdf import iter_sdf_records
from aichemy_pricing.resolvers._sid_map import iter_sid_map
from aichemy_pricing.types import ResolverHit

log = logging.getLogger(__name__)


def _first(rec: dict[str, list[str]], tag: str) -> str | None:
    v = rec.get(tag)
    return v[0] if v else None


@dataclass
class PubChemCompoundResolver:
    """InChIKey -> ResolverHit index built via Substance + SID-Map + Compound JOIN.

    Construct via `from_files(...)` (full build) or `from_cache(...)`
    (deserialize a previously-built parquet). Both produce a resolver whose
    `resolve(inchikey)` is an O(1) dict lookup.
    """

    name: str = "pubchem_compound"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    # ---- Construction --------------------------------------------------------

    @classmethod
    def from_files(
        cls,
        compound_sdf_paths: list[Path],
        substance_sdf_paths: list[Path],
        sid_map_path: Path,
        allowed_sources: set[str] | None = None,
        index_cache: Path | None = None,
    ) -> PubChemCompoundResolver:
        """Build the resolver by streaming all three sources and JOINing.

        `allowed_sources` filters Substance records by DSN (the literal
        string stored in `PUBCHEM_EXT_DATASOURCE_NAME` — usually a numeric
        source ID like "959", but a few are display strings like
        "Sigma-Aldrich"). Required for full-corpus builds — without it,
        the in-memory dicts grow to tens of GB.

        If `index_cache` is given, the final index is written to that
        parquet path so subsequent runs can use `from_cache()`.
        """
        log.info(
            "PubChemCompoundResolver.from_files: pass 1/3 — Substance SDFs (%d shards) "
            "filtered by allowed_sources=%s",
            len(substance_sdf_paths),
            allowed_sources,
        )
        sid_to_vendors: dict[int, list[tuple[str, str, str | None]]] = defaultdict(list)
        for path in substance_sdf_paths:
            for rec in iter_sdf_records(Path(path)):
                src = _first(rec, "PUBCHEM_EXT_DATASOURCE_NAME")
                regid = _first(rec, "PUBCHEM_EXT_DATASOURCE_REGID")
                sid_str = _first(rec, "PUBCHEM_SUBSTANCE_ID")
                if not (src and regid and sid_str):
                    continue
                if allowed_sources is not None and src not in allowed_sources:
                    continue
                try:
                    sid = int(sid_str)
                except ValueError:
                    continue
                url = _first(rec, "PUBCHEM_EXT_SUBSTANCE_URL") or _first(
                    rec, "PUBCHEM_EXT_DATASOURCE_URL"
                )
                sid_to_vendors[sid].append((src, regid, url))

        log.info(
            "pass 1 done: %d SIDs collected across %d filtered records",
            len(sid_to_vendors),
            sum(len(v) for v in sid_to_vendors.values()),
        )

        log.info("PubChemCompoundResolver.from_files: pass 2/3 — SID-Map JOIN")
        cid_to_vendors: dict[int, list[tuple[str, str, str | None]]] = defaultdict(list)
        for sid, cid in iter_sid_map(sid_map_path):
            if cid is None:
                continue
            vendors = sid_to_vendors.get(sid)
            if not vendors:
                continue
            cid_to_vendors[cid].extend(vendors)

        log.info(
            "pass 2 done: %d CIDs map to %d vendor entries",
            len(cid_to_vendors),
            sum(len(v) for v in cid_to_vendors.values()),
        )

        log.info(
            "PubChemCompoundResolver.from_files: pass 3/3 — Compound SDFs (%d shards) "
            "for InChIKey lookup",
            len(compound_sdf_paths),
        )
        self = cls()
        for path in compound_sdf_paths:
            for rec in iter_sdf_records(Path(path)):
                cid_str = _first(rec, "PUBCHEM_COMPOUND_CID")
                if not cid_str:
                    continue
                try:
                    cid = int(cid_str)
                except ValueError:
                    continue
                vendors = cid_to_vendors.get(cid)
                if not vendors:
                    continue
                ik = _first(rec, "PUBCHEM_IUPAC_INCHIKEY")
                if not ik or len(ik) != 27:
                    continue
                for vendor, regid, url in vendors:
                    self.index[ik].append(
                        ResolverHit(inchikey=ik, vendor=vendor, sku=regid, canonical_url=url)
                    )

        log.info(
            "build complete: %d unique InChIKeys -> %d total ResolverHits",
            len(self.index),
            sum(len(v) for v in self.index.values()),
        )

        if index_cache is not None:
            self._persist(index_cache)

        return self

    # ---- Persistence ---------------------------------------------------------

    def _persist(self, parquet_path: Path) -> None:
        """Write the index to parquet (one row per ResolverHit)."""
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, str | None]] = []
        for ik, hits in self.index.items():
            for h in hits:
                rows.append(
                    {
                        "inchikey": ik,
                        "vendor": h.vendor,
                        "sku": h.sku,
                        "canonical_url": h.canonical_url,
                    }
                )
        df = pl.DataFrame(
            rows,
            schema={
                "inchikey": pl.Utf8,
                "vendor": pl.Utf8,
                "sku": pl.Utf8,
                "canonical_url": pl.Utf8,
            },
        )
        df.write_parquet(parquet_path)
        log.info(
            "persisted %d hits across %d InChIKeys to %s",
            len(rows),
            df.select("inchikey").n_unique(),
            parquet_path,
        )

    @classmethod
    def from_cache(cls, parquet_path: Path) -> PubChemCompoundResolver:
        """Reload a previously-persisted index from parquet (~5 sec for ~5M rows)."""
        df = pl.read_parquet(parquet_path)
        self = cls()
        for row in df.iter_rows(named=True):
            ik = row["inchikey"]
            self.index[ik].append(
                ResolverHit(
                    inchikey=ik,
                    vendor=row["vendor"],
                    sku=row["sku"],
                    canonical_url=row["canonical_url"],
                )
            )
        log.info(
            "loaded index from %s: %d InChIKeys, %d hits",
            parquet_path,
            len(self.index),
            df.height,
        )
        return self

    # ---- Lookup --------------------------------------------------------------

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
