"""Tests for MetaNetX ingestion (Stage 02)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from aichemy.preprocessing.sources.metanetx import (
    ingest_metanetx,
    parse_chem_prop,
    parse_equation,
    parse_reac_prop,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "metanetx_sample"


def test_parse_chem_prop_reads_fixture() -> None:
    df = parse_chem_prop(FIXTURE_DIR / "chem_prop.tsv")
    assert df.height == 10
    assert set(df.columns) >= {"mnx_id", "name", "formula", "inchi_key", "smiles"}
    # Ethanol
    row = df.filter(pl.col("mnx_id") == "MNXM4").to_dicts()[0]
    assert row["smiles"] == "CCO"
    assert row["inchi_key"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"


def test_parse_chem_prop_handles_hash_comments() -> None:
    """The #ID header line shouldn't be data; mnx_ids should all start with MNXM."""
    df = parse_chem_prop(FIXTURE_DIR / "chem_prop.tsv")
    assert all(mid.startswith("MNXM") for mid in df["mnx_id"].to_list())


def test_parse_equation_simple_forward() -> None:
    # "1 MNXM4 + 1 MNXM6 = 1 MNXM5 + 1 MNXM7 + 1 MNXM1"
    reactants, products = parse_equation("1 MNXM4 + 1 MNXM6 = 1 MNXM5 + 1 MNXM7 + 1 MNXM1")
    assert reactants == [
        {"mol_id": "MNXM4", "coefficient": 1.0},
        {"mol_id": "MNXM6", "coefficient": 1.0},
    ]
    assert products == [
        {"mol_id": "MNXM5", "coefficient": 1.0},
        {"mol_id": "MNXM7", "coefficient": 1.0},
        {"mol_id": "MNXM1", "coefficient": 1.0},
    ]


def test_parse_equation_nonunit_coefficient() -> None:
    _reactants, products = parse_equation(
        "1 MNXM5 + 1 MNXM6 + 1 MNXM2 = 1 MNXM8 + 1 MNXM7 + 2 MNXM1"
    )
    # Verify coefficient on last product is 2
    assert products[-1] == {"mol_id": "MNXM1", "coefficient": 2.0}


def test_parse_reac_prop_reads_fixture() -> None:
    df = parse_reac_prop(FIXTURE_DIR / "reac_prop.tsv")
    assert df.height == 5
    assert set(df.columns) >= {"mnx_rxn_id", "reactants", "products", "ec", "is_balanced"}


def test_ingest_metanetx_integration() -> None:
    molecules, reactions = ingest_metanetx(FIXTURE_DIR)
    assert molecules.height == 10
    assert reactions.height == 5
    # Reactions carry source=metanetx
    assert set(reactions["source"].to_list()) == {"metanetx"}
    # Molecules carry mol_id matching MetaNetX IDs
    assert all(mid.startswith("MNXM") for mid in molecules["mol_id"].to_list())
