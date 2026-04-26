"""Tests for UnbalancedPolicy + heuristic repair (Open Item 05)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.balance.validate import (
    UnbalancedPolicy,
    try_heuristic_proton_balance,
    try_heuristic_water_balance,
    validate_reactions,
)


def test_proton_heuristic_fixes_ethanol_to_acetaldehyde() -> None:
    # CCO (C2H6O) → CC=O (C2H4O) differs only in H×2. Adding 2 H+ to products balances.
    reactants = [{"smiles": "CCO", "coefficient": 1.0}]
    products = [{"smiles": "CC=O", "coefficient": 1.0}]
    repaired = try_heuristic_proton_balance(reactants, products)
    assert repaired is not None
    _, new_products = repaired
    # Should have added H+ to products side
    assert any(p.get("smiles") == "[H+]" for p in new_products)


def test_proton_heuristic_fails_on_carbon_imbalance() -> None:
    # Different carbon counts — proton heuristic shouldn't claim it fixed it.
    reactants = [{"smiles": "CCO", "coefficient": 1.0}]  # C2
    products = [{"smiles": "CO", "coefficient": 1.0}]  # C1
    assert try_heuristic_proton_balance(reactants, products) is None


def test_water_heuristic_fixes_ester_hydrolysis() -> None:
    # Correct ester hydrolysis: CC(=O)OCC + H2O -> CC(=O)O + CCO
    # Without water on reactants: C4H8O2 vs C2H4O2 + C2H6O = C4H10O3.
    # Diff: reactants short by H×2 and O×1 -> add 1 H2O to reactants to balance.
    reactants = [{"smiles": "CC(=O)OCC", "coefficient": 1.0}]  # C4H8O2
    products = [
        {"smiles": "CC(=O)O", "coefficient": 1.0},  # C2H4O2
        {"smiles": "CCO", "coefficient": 1.0},  # C2H6O
    ]
    repaired = try_heuristic_water_balance(reactants, products)
    assert repaired is not None
    new_reactants, _ = repaired
    assert any(r.get("smiles") == "O" for r in new_reactants)


def test_validate_policy_flag_keeps_unbalanced_as_false() -> None:
    df = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "reactants": [[{"smiles": "CCO", "coefficient": 1.0}]],
            "products": [[{"smiles": "CC=O", "coefficient": 1.0}]],
        }
    )
    out = validate_reactions(df, unbalanced_policy=UnbalancedPolicy.FLAG)
    assert out.height == 1
    assert out["rdkit_balanced"].to_list() == [False]


def test_validate_policy_drop_removes_unbalanced() -> None:
    df = pl.DataFrame(
        {
            "rxn_id": ["r1", "r2"],
            "reactants": [
                [{"smiles": "O", "coefficient": 1.0}],  # balanced: O = O
                [{"smiles": "CCO", "coefficient": 1.0}],  # unbalanced vs product
            ],
            "products": [
                [{"smiles": "O", "coefficient": 1.0}],
                [{"smiles": "CC=O", "coefficient": 1.0}],
            ],
        }
    )
    out = validate_reactions(df, unbalanced_policy=UnbalancedPolicy.DROP)
    assert out.height == 1
    assert out["rxn_id"].to_list() == ["r1"]


def test_validate_policy_heuristic_h_flips_proton_imbalance_to_true() -> None:
    df = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "reactants": [[{"smiles": "CCO", "coefficient": 1.0}]],
            "products": [[{"smiles": "CC=O", "coefficient": 1.0}]],
        }
    )
    out = validate_reactions(df, unbalanced_policy=UnbalancedPolicy.HEURISTIC_H)
    assert out["rdkit_balanced"].to_list() == [True]
