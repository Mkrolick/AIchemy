"""Tests for reaction deduplication (Stage 06)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.dedup.reactions import (
    canonical_reaction_string,
    dedup_reactions,
    rewrite_mol_ids,
)


def test_rewrite_mol_ids_via_map() -> None:
    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "reactants": [[{"mol_id": "A", "coefficient": 1.0}]],
            "products": [[{"mol_id": "B", "coefficient": 1.0}]],
        }
    )
    dedup_map = {"A": "X", "B": "Y"}
    out = rewrite_mol_ids(reactions, dedup_map)
    row = out.to_dicts()[0]
    assert row["reactants"][0]["mol_id"] == "X"
    assert row["products"][0]["mol_id"] == "Y"


def test_rewrite_mol_ids_preserves_unknown_ids() -> None:
    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "reactants": [[{"mol_id": "UNK", "coefficient": 1.0}]],
            "products": [[{"mol_id": "KNOWN", "coefficient": 1.0}]],
        }
    )
    out = rewrite_mol_ids(reactions, {"KNOWN": "CAN"})
    row = out.to_dicts()[0]
    assert row["reactants"][0]["mol_id"] == "UNK"
    assert row["products"][0]["mol_id"] == "CAN"


def test_canonical_reaction_string_is_deterministic() -> None:
    reactants = [
        {"mol_id": "B", "coefficient": 1.0},
        {"mol_id": "A", "coefficient": 2.0},
    ]
    products = [{"mol_id": "C", "coefficient": 1.0}]
    s1 = canonical_reaction_string(reactants, products)
    # Swapping the reactants order should produce the same canonical string
    s2 = canonical_reaction_string(list(reversed(reactants)), products)
    assert s1 == s2


def test_dedup_reactions_hash_collapses_identical() -> None:
    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1", "r2", "r3"],
            "reactants": [
                [{"mol_id": "A", "coefficient": 1.0}],
                [{"mol_id": "A", "coefficient": 1.0}],
                [{"mol_id": "B", "coefficient": 1.0}],
            ],
            "products": [
                [{"mol_id": "X", "coefficient": 1.0}],
                [{"mol_id": "X", "coefficient": 1.0}],
                [{"mol_id": "Y", "coefficient": 1.0}],
            ],
        }
    )
    molecules = pl.DataFrame({"mol_id": ["A", "B", "X", "Y"]})
    out = dedup_reactions(reactions, molecules, dedup_map={})
    # r1 and r2 are duplicates → 1 row for them; r3 unique → 1 row; total 2
    assert out.height == 2


def test_dedup_reactions_referential_integrity() -> None:
    """A reaction referencing a mol_id not in molecules should raise."""
    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "reactants": [[{"mol_id": "DANGLING", "coefficient": 1.0}]],
            "products": [[{"mol_id": "X", "coefficient": 1.0}]],
        }
    )
    molecules = pl.DataFrame({"mol_id": ["X"]})
    try:
        dedup_reactions(reactions, molecules, dedup_map={})
    except ValueError as exc:
        assert "DANGLING" in str(exc)
    else:
        raise AssertionError("Expected referential integrity check to raise")
