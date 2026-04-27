"""Tests for the SID-Map streaming parser."""

from __future__ import annotations

import gzip

from aichemy_pricing.resolvers._sid_map import iter_sid_map


def test_iter_sid_map_parses_two_column_tsv(tmp_path) -> None:
    p = tmp_path / "sid_map.tsv"
    p.write_text("1\t100\n2\t200\n3\t300\n")
    rows = list(iter_sid_map(p))
    assert rows == [(1, 100), (2, 200), (3, 300)]


def test_iter_sid_map_yields_none_for_empty_cid(tmp_path) -> None:
    """Many SIDs (deprecated, non-standardizable) have no CID."""
    p = tmp_path / "sid_map.tsv"
    p.write_text("10\t\n11\t111\n12\t\n")
    rows = list(iter_sid_map(p))
    assert rows == [(10, None), (11, 111), (12, None)]


def test_iter_sid_map_handles_gzipped_input(tmp_path) -> None:
    """Real PubChem SID-Map ships as `.gz`; the parser must open transparently."""
    p = tmp_path / "sid_map.tsv.gz"
    with gzip.open(p, "wt") as fh:
        fh.write("1\t100\n2\t\n3\t300\n")
    rows = list(iter_sid_map(p))
    assert rows == [(1, 100), (2, None), (3, 300)]


def test_iter_sid_map_skips_malformed_rows(tmp_path) -> None:
    """Real-world dumps occasionally have anomalies; one bad row must not
    abort the iteration. We skip non-integer SIDs and non-integer CIDs."""
    p = tmp_path / "sid_map.tsv"
    p.write_text(
        "1\t100\n"
        "garbage_no_tab\n"
        "abc\t200\n"  # bad sid
        "3\tnotanumber\n"  # bad cid
        "4\t400\n"
    )
    rows = list(iter_sid_map(p))
    assert rows == [(1, 100), (4, 400)]


def test_iter_sid_map_skips_blank_lines(tmp_path) -> None:
    p = tmp_path / "sid_map.tsv"
    p.write_text("1\t100\n\n2\t200\n\n")
    rows = list(iter_sid_map(p))
    assert rows == [(1, 100), (2, 200)]
