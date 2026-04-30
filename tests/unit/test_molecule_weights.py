"""Per-molecule MW augmentation."""

from __future__ import annotations

import math

import polars as pl
import pytest

from aichemy.preprocessing.augment.molecule_weights import augment_with_mw


def test_water_mw_correct():
    df = pl.DataFrame({"mol_id": ["WATER"], "canonical_smiles": ["O"]})
    out = augment_with_mw(df)
    assert "mol_weight" in out.columns
    assert out["mol_weight"][0] == pytest.approx(18.015, abs=0.05)


def test_glucose_mw_correct():
    df = pl.DataFrame(
        {
            "mol_id": ["GLUCOSE"],
            # α-D-glucose
            "canonical_smiles": ["OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O"],
        }
    )
    out = augment_with_mw(df)
    # Molecular formula C6H12O6 → 180.156 g/mol
    assert out["mol_weight"][0] == pytest.approx(180.16, abs=0.05)


def test_unparseable_smiles_returns_null():
    df = pl.DataFrame(
        {
            "mol_id": ["BAD", "ALSO_BAD", "OK"],
            "canonical_smiles": ["NOT_A_SMILES_AT_ALL", "[Q]", "O"],
        }
    )
    out = augment_with_mw(df)
    weights = out["mol_weight"].to_list()
    # First two should be null, third (water) should be ~18
    assert weights[0] is None
    assert weights[1] is None
    assert weights[2] is not None and weights[2] == pytest.approx(18.015, abs=0.05)


def test_dataframe_roundtrip_preserves_order_and_columns():
    df = pl.DataFrame(
        {
            "mol_id": ["A", "B", "C"],
            "canonical_smiles": ["O", "CCO", "C"],
            "extra_col": ["foo", "bar", "baz"],
        }
    )
    out = augment_with_mw(df)
    assert out.height == df.height
    assert out["mol_id"].to_list() == ["A", "B", "C"]
    assert out["extra_col"].to_list() == ["foo", "bar", "baz"]
    assert out["mol_weight"].dtype == pl.Float64
    # Sanity: ethanol (CCO) ≈ 46.07, methane (C) ≈ 16.04
    weights = out["mol_weight"].to_list()
    assert weights[0] == pytest.approx(18.015, abs=0.05)
    assert weights[1] == pytest.approx(46.07, abs=0.05)
    assert weights[2] == pytest.approx(16.04, abs=0.05)


def test_missing_canonical_smiles_column_raises():
    df = pl.DataFrame({"mol_id": ["A"], "smi_misnamed": ["O"]})
    with pytest.raises(ValueError, match="canonical_smiles"):
        augment_with_mw(df)


def test_empty_dataframe_returns_empty_with_mw_column():
    df = pl.DataFrame(
        schema={"mol_id": pl.Utf8, "canonical_smiles": pl.Utf8},
    )
    out = augment_with_mw(df)
    assert out.height == 0
    assert "mol_weight" in out.columns
    assert out["mol_weight"].dtype == pl.Float64


def test_nan_or_none_smiles_returns_null():
    """None entries (vs malformed strings) should also gracefully yield null."""
    df = pl.DataFrame({"mol_id": ["X", "Y"], "canonical_smiles": [None, "O"]})
    out = augment_with_mw(df)
    weights = out["mol_weight"].to_list()
    assert weights[0] is None
    assert weights[1] == pytest.approx(18.015, abs=0.05)


def test_mw_values_are_finite_floats():
    """Sanity check: no NaN/inf should leak through for valid SMILES."""
    df = pl.DataFrame(
        {
            "mol_id": ["A", "B", "C", "D"],
            "canonical_smiles": ["O", "[H][H]", "O=O", "N#N"],
        }
    )
    out = augment_with_mw(df)
    for w in out["mol_weight"].to_list():
        assert w is not None and not math.isnan(w) and math.isfinite(w)
