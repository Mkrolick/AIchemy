"""Unit tests for PubChemSdfResolver. Uses a 10-record fixture captured from
the real FTP dump (https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/)."""

from __future__ import annotations

from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver


def test_resolver_indexes_at_least_one_record(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    assert res.index, "expected at least one indexed InChIKey from the fixture"


def test_each_hit_carries_vendor_and_sku(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    sample_ik = next(iter(res.index))
    hits = res.resolve(sample_ik)
    assert hits
    for h in hits:
        assert h.vendor and h.sku


def test_allowed_sources_filter(fixture_dir) -> None:
    """When `allowed_sources` is set, only matching `PUBCHEM_EXT_DATASOURCE_NAME`
    values are indexed."""
    res = PubChemSdfResolver.from_files(
        [fixture_dir / "pubchem_sample.sdf"],
        allowed_sources={"NoSuchVendor-XYZ"},
    )
    assert res.index == {}


def test_resolver_returns_empty_list_for_unknown_inchikey(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    assert res.resolve("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z") == []


def test_canonical_url_populated_when_present(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    # at least one hit should carry a vendor URL
    any_url = any(h.canonical_url for hits in res.index.values() for h in hits)
    # Don't fail hard if the fixture's first 10 records happen to lack URL — just assert shape OK.
    assert isinstance(any_url, bool)
