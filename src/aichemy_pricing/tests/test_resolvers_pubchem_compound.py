"""Tests for `PubChemCompoundResolver` — Substance + SID-Map + Compound JOIN."""

from __future__ import annotations

from pathlib import Path

from aichemy_pricing.resolvers.pubchem_compound import PubChemCompoundResolver

# Two real-shape 27-char InChIKeys (aspirin, caffeine).
_IK_ASPIRIN = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
_IK_CAFFEINE = "RYYVLZVUVIJVGH-UHFFFAOYSA-N"


def _write_substance_sdf(path: Path, records: list[dict[str, str]]) -> None:
    """records: each dict has keys like SUBSTANCE_ID, EXT_DATASOURCE_NAME, etc.
    Tags are emitted in PubChem's `> <TAG>\\n value\\n\\n` format; records
    delimited by `$$$$`."""
    lines: list[str] = []
    for rec in records:
        lines.append("dummy_molfile_header")  # ignored by iter_sdf_records
        for tag, value in rec.items():
            lines.append(f"> <PUBCHEM_{tag}>")
            lines.append(value)
            lines.append("")
        lines.append("$$$$")
    path.write_text("\n".join(lines) + "\n")


def _write_compound_sdf(path: Path, records: list[dict[str, str]]) -> None:
    """Same shape, different tag set. Records are CID-keyed."""
    _write_substance_sdf(path, records)  # same wire format


def _write_sid_map(path: Path, rows: list[tuple[int, int | None]]) -> None:
    """SID-Map's real format is 4 columns
    (SID<TAB>SourceName<TAB>SourceRegID<TAB>CID); CID column is *omitted*
    entirely when there's no Compound association. The test fixtures use
    placeholder source name + reg ID since the resolver only consumes
    columns 0 and 3 (SID and CID)."""
    lines = []
    for sid, cid in rows:
        if cid is None:
            lines.append(f"{sid}\tFakeSource\tFAKE-{sid:06d}")
        else:
            lines.append(f"{sid}\tFakeSource\tFAKE-{sid:06d}\t{cid}")
    path.write_text("\n".join(lines) + "\n")


def test_pubchem_compound_resolver_3way_join_happy_path(tmp_path) -> None:
    """End-to-end: 2 Substance records + 1 SID-Map row each + 2 Compound
    records produce 2 ResolverHits keyed by their respective InChIKeys."""
    sub_sdf = tmp_path / "Substance_001.sdf"
    _write_substance_sdf(
        sub_sdf,
        [
            {
                "SUBSTANCE_ID": "1001",
                "EXT_DATASOURCE_NAME": "959",  # MedChemExpress DSN
                "EXT_DATASOURCE_REGID": "HY-100005A",
                "EXT_DATASOURCE_URL": "https://www.medchemexpress.com/",
                "EXT_SUBSTANCE_URL": "https://www.medchemexpress.com/foo.html",
            },
            {
                "SUBSTANCE_ID": "2002",
                "EXT_DATASOURCE_NAME": "Sigma-Aldrich",
                "EXT_DATASOURCE_REGID": "A5376",
                "EXT_DATASOURCE_URL": "https://www.sigmaaldrich.com/",
            },
        ],
    )

    sid_map = tmp_path / "sid_map.tsv"
    _write_sid_map(sid_map, [(1001, 5001), (2002, 5002)])

    cmp_sdf = tmp_path / "Compound_001.sdf"
    _write_compound_sdf(
        cmp_sdf,
        [
            {"COMPOUND_CID": "5001", "IUPAC_INCHIKEY": _IK_ASPIRIN},
            {"COMPOUND_CID": "5002", "IUPAC_INCHIKEY": _IK_CAFFEINE},
        ],
    )

    resolver = PubChemCompoundResolver.from_files(
        compound_sdf_paths=[cmp_sdf],
        substance_sdf_paths=[sub_sdf],
        sid_map_path=sid_map,
    )

    aspirin_hits = resolver.resolve(_IK_ASPIRIN)
    assert len(aspirin_hits) == 1
    assert aspirin_hits[0].vendor == "959"
    assert aspirin_hits[0].sku == "HY-100005A"
    assert aspirin_hits[0].canonical_url == "https://www.medchemexpress.com/foo.html"

    caffeine_hits = resolver.resolve(_IK_CAFFEINE)
    assert len(caffeine_hits) == 1
    assert caffeine_hits[0].vendor == "Sigma-Aldrich"
    assert caffeine_hits[0].sku == "A5376"


def test_pubchem_compound_resolver_allowed_sources_filters_substance(tmp_path) -> None:
    """allowed_sources={'959'} drops the Sigma-Aldrich record before the JOIN."""
    sub_sdf = tmp_path / "Substance_001.sdf"
    _write_substance_sdf(
        sub_sdf,
        [
            {
                "SUBSTANCE_ID": "1001",
                "EXT_DATASOURCE_NAME": "959",
                "EXT_DATASOURCE_REGID": "HY-100005A",
            },
            {
                "SUBSTANCE_ID": "2002",
                "EXT_DATASOURCE_NAME": "Sigma-Aldrich",
                "EXT_DATASOURCE_REGID": "A5376",
            },
        ],
    )
    sid_map = tmp_path / "sid_map.tsv"
    _write_sid_map(sid_map, [(1001, 5001), (2002, 5002)])
    cmp_sdf = tmp_path / "Compound_001.sdf"
    _write_compound_sdf(
        cmp_sdf,
        [
            {"COMPOUND_CID": "5001", "IUPAC_INCHIKEY": _IK_ASPIRIN},
            {"COMPOUND_CID": "5002", "IUPAC_INCHIKEY": _IK_CAFFEINE},
        ],
    )

    resolver = PubChemCompoundResolver.from_files(
        compound_sdf_paths=[cmp_sdf],
        substance_sdf_paths=[sub_sdf],
        sid_map_path=sid_map,
        allowed_sources={"959"},
    )

    assert len(resolver.resolve(_IK_ASPIRIN)) == 1
    assert resolver.resolve(_IK_CAFFEINE) == []  # filtered out


def test_pubchem_compound_resolver_drops_sids_with_no_cid(tmp_path) -> None:
    """SIDs with no CID in SID-Map are silently dropped (deprecated /
    non-standardizable substances)."""
    sub_sdf = tmp_path / "Substance_001.sdf"
    _write_substance_sdf(
        sub_sdf,
        [
            {
                "SUBSTANCE_ID": "1001",
                "EXT_DATASOURCE_NAME": "959",
                "EXT_DATASOURCE_REGID": "HY-001",
            },
        ],
    )
    sid_map = tmp_path / "sid_map.tsv"
    _write_sid_map(sid_map, [(1001, None)])  # no CID
    cmp_sdf = tmp_path / "Compound_001.sdf"
    _write_compound_sdf(cmp_sdf, [])

    resolver = PubChemCompoundResolver.from_files(
        compound_sdf_paths=[cmp_sdf],
        substance_sdf_paths=[sub_sdf],
        sid_map_path=sid_map,
    )

    assert resolver.resolve(_IK_ASPIRIN) == []
    assert sum(len(v) for v in resolver.index.values()) == 0


def test_pubchem_compound_resolver_skips_records_missing_required_fields(tmp_path) -> None:
    """Substance records without DSN+REGID+SID are skipped at pass 1."""
    sub_sdf = tmp_path / "Substance_001.sdf"
    _write_substance_sdf(
        sub_sdf,
        [
            # Missing SUBSTANCE_ID
            {"EXT_DATASOURCE_NAME": "959", "EXT_DATASOURCE_REGID": "HY-001"},
            # Missing REGID
            {"SUBSTANCE_ID": "2002", "EXT_DATASOURCE_NAME": "959"},
            # OK
            {
                "SUBSTANCE_ID": "3003",
                "EXT_DATASOURCE_NAME": "959",
                "EXT_DATASOURCE_REGID": "HY-003",
            },
        ],
    )
    sid_map = tmp_path / "sid_map.tsv"
    _write_sid_map(sid_map, [(3003, 5003)])
    cmp_sdf = tmp_path / "Compound_001.sdf"
    _write_compound_sdf(cmp_sdf, [{"COMPOUND_CID": "5003", "IUPAC_INCHIKEY": _IK_ASPIRIN}])

    resolver = PubChemCompoundResolver.from_files(
        compound_sdf_paths=[cmp_sdf],
        substance_sdf_paths=[sub_sdf],
        sid_map_path=sid_map,
    )

    hits = resolver.resolve(_IK_ASPIRIN)
    assert len(hits) == 1
    assert hits[0].sku == "HY-003"


def test_pubchem_compound_resolver_multiple_vendors_per_compound(tmp_path) -> None:
    """Same CID listed by two different vendors -> two ResolverHits, same IK."""
    sub_sdf = tmp_path / "Substance_001.sdf"
    _write_substance_sdf(
        sub_sdf,
        [
            {
                "SUBSTANCE_ID": "1001",
                "EXT_DATASOURCE_NAME": "959",
                "EXT_DATASOURCE_REGID": "HY-1",
            },
            {
                "SUBSTANCE_ID": "2002",
                "EXT_DATASOURCE_NAME": "Sigma-Aldrich",
                "EXT_DATASOURCE_REGID": "A1",
            },
        ],
    )
    sid_map = tmp_path / "sid_map.tsv"
    # Both SIDs map to the same CID
    _write_sid_map(sid_map, [(1001, 5001), (2002, 5001)])
    cmp_sdf = tmp_path / "Compound_001.sdf"
    _write_compound_sdf(cmp_sdf, [{"COMPOUND_CID": "5001", "IUPAC_INCHIKEY": _IK_ASPIRIN}])

    resolver = PubChemCompoundResolver.from_files(
        compound_sdf_paths=[cmp_sdf],
        substance_sdf_paths=[sub_sdf],
        sid_map_path=sid_map,
    )

    hits = resolver.resolve(_IK_ASPIRIN)
    assert len(hits) == 2
    assert {h.vendor for h in hits} == {"959", "Sigma-Aldrich"}


def test_pubchem_compound_resolver_round_trips_via_parquet_cache(tmp_path) -> None:
    """build -> _persist -> from_cache -> resolve gives the same hits."""
    sub_sdf = tmp_path / "Substance_001.sdf"
    _write_substance_sdf(
        sub_sdf,
        [
            {
                "SUBSTANCE_ID": "1001",
                "EXT_DATASOURCE_NAME": "959",
                "EXT_DATASOURCE_REGID": "HY-100005A",
                "EXT_SUBSTANCE_URL": "https://www.medchemexpress.com/foo.html",
            }
        ],
    )
    sid_map = tmp_path / "sid_map.tsv"
    _write_sid_map(sid_map, [(1001, 5001)])
    cmp_sdf = tmp_path / "Compound_001.sdf"
    _write_compound_sdf(cmp_sdf, [{"COMPOUND_CID": "5001", "IUPAC_INCHIKEY": _IK_ASPIRIN}])
    cache_path = tmp_path / "index.parquet"

    PubChemCompoundResolver.from_files(
        compound_sdf_paths=[cmp_sdf],
        substance_sdf_paths=[sub_sdf],
        sid_map_path=sid_map,
        index_cache=cache_path,
    )
    assert cache_path.exists()

    reloaded = PubChemCompoundResolver.from_cache(cache_path)
    hits = reloaded.resolve(_IK_ASPIRIN)
    assert len(hits) == 1
    assert hits[0].vendor == "959"
    assert hits[0].sku == "HY-100005A"
    assert hits[0].canonical_url == "https://www.medchemexpress.com/foo.html"
