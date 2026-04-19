"""Tests for molecule deduplication (Stage 05)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.dedup.molecules import dedup_molecules


def test_dedup_single_inchi_key_group() -> None:
    # Two rows with the same InChIKey — should collapse to one.
    df = pl.DataFrame(
        {
            "mol_id": ["MNXM4", "USPTO:alt123"],
            "canonical_smiles": ["CCO", "CCO"],
            "inchi_key": [
                "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
            ],
            "carbon_count": [2, 2],
            "price_per_gram": [None, None],
            "source_refs": [["MetaNetX:MNXM4"], ["USPTO:alt123"]],
        },
        schema_overrides={"price_per_gram": pl.Float64, "carbon_count": pl.Int64},
    )
    deduped, dedup_map = dedup_molecules(df)
    assert deduped.height == 1
    # MetaNetX ID wins as canonical
    assert deduped["mol_id"].to_list() == ["MNXM4"]
    # Source refs union
    refs = deduped["source_refs"].to_list()[0]
    assert set(refs) == {"MetaNetX:MNXM4", "USPTO:alt123"}
    # dedup_map maps every pre-dedup ID to the canonical
    assert dedup_map == {"MNXM4": "MNXM4", "USPTO:alt123": "MNXM4"}


def test_dedup_unique_rows_pass_through() -> None:
    df = pl.DataFrame(
        {
            "mol_id": ["A", "B"],
            "canonical_smiles": ["CCO", "CCN"],
            "inchi_key": ["KEY-A", "KEY-B"],
            "carbon_count": [2, 2],
            "price_per_gram": [None, None],
            "source_refs": [["a"], ["b"]],
        },
        schema_overrides={"price_per_gram": pl.Float64, "carbon_count": pl.Int64},
    )
    deduped, dedup_map = dedup_molecules(df)
    assert deduped.height == 2
    assert dedup_map == {"A": "A", "B": "B"}


def test_metanetx_id_preferred_over_inchikey_style_id() -> None:
    df = pl.DataFrame(
        {
            "mol_id": ["SOMEKEY-UHFFFAOYSA-N", "MNXM100"],
            "canonical_smiles": ["X", "X"],
            "inchi_key": ["SAME-KEY", "SAME-KEY"],
            "carbon_count": [0, 0],
            "price_per_gram": [None, None],
            "source_refs": [["uspto"], ["metanetx"]],
        },
        schema_overrides={"price_per_gram": pl.Float64, "carbon_count": pl.Int64},
    )
    deduped, _dedup_map = dedup_molecules(df)
    assert deduped.height == 1
    assert deduped["mol_id"].to_list() == ["MNXM100"]
