"""Tests for the normalize stage (Stage 04)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.normalize import (
    canonicalize_molecules,
    filter_reactions_by_carbon,
    merge_sources,
)


def test_merge_sources_unions_molecules() -> None:
    metanetx_mol = pl.DataFrame(
        {
            "mol_id": ["MNXM1", "MNXM4"],
            "canonical_smiles": ["[H+]", "CCO"],
            "inchi_key": ["GPRLSGONYQIRFK-UHFFFAOYSA-N", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"],
            "carbon_count": [None, None],
            "price_per_gram": [None, None],
            "source_refs": [["MetaNetX:MNXM1"], ["MetaNetX:MNXM4"]],
        },
        schema_overrides={"carbon_count": pl.Int64, "price_per_gram": pl.Float64},
    )
    # USPTO ingest initially doesn't produce a molecules table — it feeds
    # its reactant/product SMILES strings. merge_sources for now just takes
    # the MetaNetX molecules table as canonical.
    out = merge_sources(metanetx_mol)
    assert out.height == 2
    assert set(out["mol_id"].to_list()) == {"MNXM1", "MNXM4"}


def test_canonicalize_molecules_adds_carbon_count() -> None:
    df = pl.DataFrame(
        {
            "mol_id": ["m1", "m2", "m3"],
            "canonical_smiles": ["CCO", "O", "c1ccccc1"],
            "inchi_key": ["a", "b", "c"],
            "carbon_count": [None, None, None],
            "price_per_gram": [None, None, None],
            "source_refs": [["a"], ["b"], ["c"]],
        },
        schema_overrides={"carbon_count": pl.Int64, "price_per_gram": pl.Float64},
    )
    out = canonicalize_molecules(df)
    assert out["carbon_count"].to_list() == [2, 0, 6]


def test_filter_reactions_by_carbon_drops_sub_threshold() -> None:
    molecules = pl.DataFrame(
        {
            "mol_id": ["CARBON2", "WATER", "ETHANOL"],
            "carbon_count": [2, 0, 2],
        }
    )
    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1", "r2"],
            "reactants": [
                [{"mol_id": "ETHANOL", "coefficient": 1.0}],
                [{"mol_id": "WATER", "coefficient": 1.0}],
            ],
            "products": [
                [{"mol_id": "CARBON2", "coefficient": 1.0}],
                [{"mol_id": "ETHANOL", "coefficient": 1.0}],
            ],
        }
    )
    filtered = filter_reactions_by_carbon(reactions, molecules, min_carbon=2)
    # r1 passes (all participants have ≥2 carbons); r2 fails (water reactant)
    assert filtered["rxn_id"].to_list() == ["r1"]
