"""Tests for directionality application (Stage 11)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.augment.directionality import (
    DirectionalityMode,
    apply_directionality,
)


def _sample_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "rxn_id": ["r1", "r2", "r3"],
            "type": ["enzymatic", "enzymatic", "chemical"],
            "direction": ["forward", "reversible", "forward"],
            "reactants": [
                [{"mol_id": "A", "coefficient": 1.0}],
                [{"mol_id": "B", "coefficient": 1.0}],
                [{"mol_id": "C", "coefficient": 1.0}],
            ],
            "products": [
                [{"mol_id": "X", "coefficient": 1.0}],
                [{"mol_id": "Y", "coefficient": 1.0}],
                [{"mol_id": "Z", "coefficient": 1.0}],
            ],
        }
    )


def test_annotate_mode_keeps_row_count_and_direction_intact() -> None:
    out = apply_directionality(_sample_df(), mode=DirectionalityMode.ANNOTATE)
    assert out.height == 3
    assert out["direction"].to_list() == ["forward", "reversible", "forward"]


def test_duplicate_reversible_emits_reverse_rows() -> None:
    out = apply_directionality(_sample_df(), mode=DirectionalityMode.DUPLICATE_REVERSIBLE)
    # 2 forward originals + 1 reversible that gets duplicated (1 forward + 1 reverse)
    # Total = 4 rows
    assert out.height == 4
    rxn_ids = out["rxn_id"].to_list()
    # The reverse row for r2 should be present with a suffix
    assert any(rid.startswith("r2") and rid.endswith("_rev") for rid in rxn_ids)


def test_duplicate_reversible_swaps_reactants_and_products() -> None:
    out = apply_directionality(_sample_df(), mode=DirectionalityMode.DUPLICATE_REVERSIBLE)
    rev = out.filter(pl.col("rxn_id") == "r2_rev").to_dicts()[0]
    # Original r2: B -> Y; reverse should be: Y -> B
    assert rev["reactants"][0]["mol_id"] == "Y"
    assert rev["products"][0]["mol_id"] == "B"


def test_duplicate_leaves_forward_only_rows_unchanged() -> None:
    out = apply_directionality(_sample_df(), mode=DirectionalityMode.DUPLICATE_REVERSIBLE)
    # The two non-reversible rows (r1, r3) should appear exactly once each.
    rxn_ids = out["rxn_id"].to_list()
    assert rxn_ids.count("r1") == 1
    assert rxn_ids.count("r3") == 1
