"""Tests for the normalize stage (Stage 04)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.normalize import (
    canonicalize_molecules,
    filter_molecules_by_usage,
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
            "mol_id": ["ETHANOL", "WATER", "ETHANAL", "PROTON"],
            "carbon_count": [2, 0, 2, 0],
        }
    )
    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1", "r2", "r3"],
            "reactants": [
                # r1: ethanol + NAD+ → ethanal + NADH (C on both sides) — keep
                [{"mol_id": "ETHANOL", "coefficient": 1.0}],
                # r2: ethanol + water → ethanal (still keep: C on both sides)
                [
                    {"mol_id": "ETHANOL", "coefficient": 1.0},
                    {"mol_id": "WATER", "coefficient": 1.0},
                ],
                # r3: proton + water shuffle → water (no carbons anywhere — drop)
                [
                    {"mol_id": "PROTON", "coefficient": 1.0},
                    {"mol_id": "WATER", "coefficient": 1.0},
                ],
            ],
            "products": [
                [{"mol_id": "ETHANAL", "coefficient": 1.0}],
                [
                    {"mol_id": "ETHANAL", "coefficient": 1.0},
                    {"mol_id": "PROTON", "coefficient": 1.0},
                ],
                [{"mol_id": "WATER", "coefficient": 1.0}],
            ],
        }
    )
    filtered = filter_reactions_by_carbon(reactions, molecules, min_carbon=2)
    # r1 and r2 both have ≥1 high-carbon participant on each side → keep.
    # r3 has no carbon anywhere → drop.
    assert filtered["rxn_id"].to_list() == ["r1", "r2"]


def test_filter_molecules_by_usage_keeps_only_referenced() -> None:
    molecules = pl.DataFrame(
        {
            "mol_id": ["A", "B", "C", "ORPHAN"],
            "canonical_smiles": ["CC", "CCO", "O", "N"],
            "inchi_key": ["a", "b", "c", "d"],
            "carbon_count": [2, 2, 0, 0],
            "price_per_gram": [None, None, None, None],
            "source_refs": [["x"], ["y"], ["z"], ["w"]],
        },
        schema_overrides={"carbon_count": pl.Int64, "price_per_gram": pl.Float64},
    )
    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "reactants": [[{"mol_id": "A", "coefficient": 1.0}]],
            "products": [
                [
                    {"mol_id": "B", "coefficient": 1.0},
                    {"mol_id": "C", "coefficient": 1.0},
                ]
            ],
        }
    )
    out = filter_molecules_by_usage(molecules, reactions)
    assert sorted(out["mol_id"].to_list()) == ["A", "B", "C"]


def test_filter_molecules_by_usage_empty_reactions_drops_all() -> None:
    molecules = pl.DataFrame(
        {
            "mol_id": ["A"],
            "canonical_smiles": ["CC"],
            "inchi_key": ["a"],
            "carbon_count": [2],
            "price_per_gram": [None],
            "source_refs": [["x"]],
        },
        schema_overrides={"carbon_count": pl.Int64, "price_per_gram": pl.Float64},
    )
    empty_rxns = pl.DataFrame(
        schema={
            "rxn_id": pl.Utf8,
            "reactants": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
            "products": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
        }
    )
    out = filter_molecules_by_usage(molecules, empty_rxns)
    assert out.height == 0
    assert out.schema == molecules.schema
