"""Tests for the SID-Map streaming parser.

Format note: the real PubChem `SID-Map.gz` is a 4-column TSV
(SID<TAB>SourceName<TAB>SourceRegID<TAB>CID), with the CID column entirely
omitted (no trailing tab) for SIDs that have no standardized Compound
association. The FTP README inaccurately documents only 2 columns —
verified empirically against the actual dump.
"""

from __future__ import annotations

import gzip

from aichemy_pricing.resolvers._sid_map import iter_sid_map, iter_sid_map_full


def test_iter_sid_map_parses_real_4col_tsv(tmp_path) -> None:
    p = tmp_path / "sid_map.tsv"
    p.write_text(
        "1\tMolecular Imaging Database (MOLI)\tMOLI000002\t135398523\n"
        "2\tMolecular Imaging Database (MOLI)\tMOLI000003\n"  # CID column omitted
        "3\tMolecular Imaging Database (MOLI)\tMOLI000005\t449639\n"
    )
    rows = list(iter_sid_map(p))
    assert rows == [(1, 135398523), (2, None), (3, 449639)]


def test_iter_sid_map_full_exposes_source_columns(tmp_path) -> None:
    p = tmp_path / "sid_map.tsv"
    p.write_text(
        "1\tMolecular Imaging Database (MOLI)\tMOLI000002\t135398523\n"
        "317226072\tMedChemexpress MCE\tHY-100005A\t121596089\n"
    )
    rows = list(iter_sid_map_full(p))
    assert rows == [
        (1, "Molecular Imaging Database (MOLI)", "MOLI000002", 135398523),
        (317226072, "MedChemexpress MCE", "HY-100005A", 121596089),
    ]


def test_iter_sid_map_yields_none_when_cid_omitted(tmp_path) -> None:
    """SIDs without a standardized Compound have the CID column entirely
    omitted (no trailing tab) — not present as an empty 4th field."""
    p = tmp_path / "sid_map.tsv"
    p.write_text(
        "10\tFoo\tFoo000001\n"  # 3 columns, no CID
        "11\tFoo\tFoo000002\t111\n"  # 4 columns, CID present
        "12\tFoo\tFoo000003\n"  # 3 columns, no CID
    )
    rows = list(iter_sid_map(p))
    assert rows == [(10, None), (11, 111), (12, None)]


def test_iter_sid_map_handles_gzipped_input(tmp_path) -> None:
    """The real PubChem dump ships as `.gz`; the parser must open transparently."""
    p = tmp_path / "sid_map.tsv.gz"
    with gzip.open(p, "wt") as fh:
        fh.write("1\tFoo\tFoo000001\t100\n2\tFoo\tFoo000002\n3\tFoo\tFoo000003\t300\n")
    rows = list(iter_sid_map(p))
    assert rows == [(1, 100), (2, None), (3, 300)]


def test_iter_sid_map_skips_malformed_rows(tmp_path) -> None:
    """Real-world dumps occasionally have anomalies; one bad row must not
    abort the iteration."""
    p = tmp_path / "sid_map.tsv"
    p.write_text(
        "1\tFoo\tFoo000001\t100\n"
        "garbage_no_tab_or_anything\n"  # no tab, can't parse SID -> skip
        "abc\tFoo\tFoo000003\t200\n"  # non-integer SID -> skip
        "3\tFoo\tFoo000004\tnotanumber\n"  # non-integer CID -> CID becomes None
        "4\tFoo\tFoo000005\t400\n"
    )
    rows = list(iter_sid_map(p))
    assert rows == [(1, 100), (3, None), (4, 400)]


def test_iter_sid_map_skips_blank_lines(tmp_path) -> None:
    p = tmp_path / "sid_map.tsv"
    p.write_text("1\tFoo\tFoo000001\t100\n\n2\tFoo\tFoo000002\t200\n\n")
    rows = list(iter_sid_map(p))
    assert rows == [(1, 100), (2, 200)]
