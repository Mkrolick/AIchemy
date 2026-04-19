"""Tests for the universal atom-balance validator (Stage 08)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.balance.validate import (
    atom_counts,
    is_balanced,
    validate_reactions,
)


def test_atom_counts_ethanol() -> None:
    counts = atom_counts("CCO", 1.0)
    assert counts["C"] == 2
    assert counts["O"] == 1
    assert counts["H"] == 6  # includes implicit hydrogens


def test_atom_counts_scales_with_coefficient() -> None:
    doubled = atom_counts("CCO", 2.0)
    assert doubled["C"] == 4
    assert doubled["O"] == 2
    assert doubled["H"] == 12


def test_atom_counts_invalid_smiles_is_empty() -> None:
    assert atom_counts("not_a_smiles", 1.0) == {}


def test_is_balanced_trivial_identity() -> None:
    # O >> O
    reactants = [{"smiles": "O", "coefficient": 1.0}]
    products = [{"smiles": "O", "coefficient": 1.0}]
    assert is_balanced(reactants, products) is True


def test_is_balanced_detects_missing_water() -> None:
    # ester hydrolysis minus the water: CC(=O)OC + H2O -> CC(=O)O + CO
    # omit the water reactant → unbalanced
    reactants = [{"smiles": "CC(=O)OC", "coefficient": 1.0}]
    products = [
        {"smiles": "CC(=O)O", "coefficient": 1.0},
        {"smiles": "CO", "coefficient": 1.0},
    ]
    # Without ignore_elements, this is off by H2O
    assert is_balanced(reactants, products) is False


def test_is_balanced_ignores_hydrogens_when_configured() -> None:
    # Ethanol → acetaldehyde: differs only in H count (6 vs 4). MetaNetX
    # elides the released 2H equivalents in its directional convention.
    reactants = [{"smiles": "CCO", "coefficient": 1.0}]  # C2 H6 O
    products = [{"smiles": "CC=O", "coefficient": 1.0}]  # C2 H4 O
    assert is_balanced(reactants, products) is False
    assert is_balanced(reactants, products, ignore_elements=["H"]) is True


def test_validate_reactions_adds_balanced_column() -> None:
    df = pl.DataFrame(
        {
            "rxn_id": ["r1", "r2"],
            "reactants": [
                [{"smiles": "O", "coefficient": 1.0}],
                [{"smiles": "CC(=O)OC", "coefficient": 1.0}],
            ],
            "products": [
                [{"smiles": "O", "coefficient": 1.0}],
                [
                    {"smiles": "CC(=O)O", "coefficient": 1.0},
                    {"smiles": "CO", "coefficient": 1.0},
                ],
            ],
        }
    )
    out = validate_reactions(df)
    assert out["balanced"].to_list() == [True, False]
