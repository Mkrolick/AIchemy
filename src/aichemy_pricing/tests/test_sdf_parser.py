"""Unit tests for the streaming SDF parser shared by all SDF-based resolvers."""

from __future__ import annotations

import gzip
import textwrap

from aichemy_pricing.resolvers._sdf import iter_sdf_records


def test_parses_two_records_with_multiline_value(tmp_path) -> None:
    sdf = textwrap.dedent("""\
        Aspirin
        ...
        > <PUBCHEM_IUPAC_INCHIKEY>
        BSYNRYMUTXBXSQ-UHFFFAOYSA-N

        > <PUBCHEM_EXT_DATASOURCE_NAME>
        Sigma-Aldrich

        > <PUBCHEM_EXT_DATASOURCE_REGID>
        A2093

        $$$$
        Caffeine
        ...
        > <PUBCHEM_IUPAC_INCHIKEY>
        RYYVLZVUVIJVGH-UHFFFAOYSA-N

        > <PUBCHEM_EXT_DATASOURCE_NAME>
        Cayman Chemical

        > <PUBCHEM_EXT_DATASOURCE_REGID>
        14118

        $$$$
        """)
    p = tmp_path / "tiny.sdf"
    p.write_text(sdf)

    records = list(iter_sdf_records(p))
    assert len(records) == 2
    assert records[0]["PUBCHEM_IUPAC_INCHIKEY"] == ["BSYNRYMUTXBXSQ-UHFFFAOYSA-N"]
    assert records[0]["PUBCHEM_EXT_DATASOURCE_REGID"] == ["A2093"]
    assert records[1]["PUBCHEM_EXT_DATASOURCE_NAME"] == ["Cayman Chemical"]


def test_skips_records_without_terminator(tmp_path) -> None:
    """A truncated SDF (no trailing $$$$) must not yield the partial record."""
    sdf = textwrap.dedent("""\
        Foo
        > <X>
        1

        """)
    p = tmp_path / "trunc.sdf"
    p.write_text(sdf)
    assert list(iter_sdf_records(p)) == []


def test_handles_multiline_tag_values(tmp_path) -> None:
    sdf = textwrap.dedent("""\
        Foo
        > <NOTES>
        line one
        line two
        line three

        > <X>
        1

        $$$$
        """)
    p = tmp_path / "multi.sdf"
    p.write_text(sdf)
    rec = next(iter_sdf_records(p))
    assert rec["NOTES"] == ["line one", "line two", "line three"]
    assert rec["X"] == ["1"]


def test_reads_sdf_gz_transparently(tmp_path) -> None:
    """The PubChem dump ships .sdf.gz; without gzip detection, opening deflate
    bytes as 'rt' with errors='replace' silently yields zero records — every
    downstream lookup returns None for the wrong reason. Lock that closed."""
    sdf_text = textwrap.dedent("""\
        Aspirin
        > <PUBCHEM_IUPAC_INCHIKEY>
        BSYNRYMUTXBXSQ-UHFFFAOYSA-N

        > <PUBCHEM_EXT_DATASOURCE_NAME>
        Sigma-Aldrich

        > <PUBCHEM_EXT_DATASOURCE_REGID>
        A2093

        $$$$
        """)
    p = tmp_path / "tiny.sdf.gz"
    with gzip.open(p, "wt") as f:
        f.write(sdf_text)
    records = list(iter_sdf_records(p))
    assert len(records) == 1
    assert records[0]["PUBCHEM_IUPAC_INCHIKEY"] == ["BSYNRYMUTXBXSQ-UHFFFAOYSA-N"]
