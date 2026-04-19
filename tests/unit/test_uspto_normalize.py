"""Tests for USPTO molecule extraction in normalize (bug fix)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing import normalize as nm


def _uspto_fixture() -> pl.DataFrame:
    """Three USPTO-style reactions with bare SMILES as mol_ids."""
    return pl.DataFrame(
        {
            "rxn_id": ["USPTO:1", "USPTO:2", "USPTO:3"],
            "reactants": [
                [{"mol_id": "CCO", "coefficient": 1.0}],
                [{"mol_id": "O", "coefficient": 1.0}],  # water — no carbon
                [{"mol_id": "c1ccccc1", "coefficient": 1.0}],  # benzene
            ],
            "products": [
                [{"mol_id": "CC=O", "coefficient": 1.0}],
                [{"mol_id": "O", "coefficient": 1.0}],  # water → water (0 C)
                [{"mol_id": "CCO", "coefficient": 1.0}],
            ],
            "source": ["uspto", "uspto", "uspto"],
            "type": ["chemical"] * 3,
            "balanced": [False] * 3,
        }
    )


def test_extract_uspto_molecules_produces_molecule_table() -> None:
    uspto = _uspto_fixture()
    mols = nm.extract_uspto_molecules(uspto)
    # Unique SMILES in the fixture: CCO, CC=O, O, c1ccccc1
    assert mols.height == 4
    assert set(mols["mol_id"].to_list()) == {"CCO", "CC=O", "O", "c1ccccc1"}


def test_extract_uspto_molecules_computes_carbon_counts() -> None:
    uspto = _uspto_fixture()
    mols = nm.extract_uspto_molecules(uspto)
    by_id = {row["mol_id"]: row["carbon_count"] for row in mols.iter_rows(named=True)}
    assert by_id["CCO"] == 2
    assert by_id["CC=O"] == 2
    assert by_id["O"] == 0
    assert by_id["c1ccccc1"] == 6


def test_normalize_keeps_uspto_reactions_after_fix() -> None:
    """Regression test: USPTO reactions must survive normalize when their
    extracted molecules have ≥2 carbons on each side."""
    uspto = _uspto_fixture()
    mols = nm.extract_uspto_molecules(uspto)
    filtered = nm.filter_reactions_by_carbon(uspto, mols, min_carbon=2)
    # USPTO:1 (CCO → CC=O) keeps — both sides have 2C
    # USPTO:2 (O → O) drops — neither side has carbon
    # USPTO:3 (benzene → ethanol) keeps
    assert set(filtered["rxn_id"].to_list()) == {"USPTO:1", "USPTO:3"}


def test_extract_handles_empty_input() -> None:
    empty = pl.DataFrame(
        schema={
            "rxn_id": pl.Utf8,
            "reactants": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
            "products": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
        }
    )
    mols = nm.extract_uspto_molecules(empty)
    assert mols.height == 0
