"""Tests for USPTO ingestion (Stage 03)."""

from __future__ import annotations

from pathlib import Path

from aichemy.preprocessing.sources.uspto import (
    ingest_uspto,
    parse_reaction_smiles,
    parse_rsmi_file,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "uspto_sample"


def test_parse_reaction_smiles_reactants_products_only() -> None:
    r, a, p = parse_reaction_smiles("CCO.O>>CC=O.O")
    assert r == ["CCO", "O"]
    assert a == []
    assert p == ["CC=O", "O"]


def test_parse_reaction_smiles_with_agents() -> None:
    r, a, p = parse_reaction_smiles("CCO>[Pt]>CC=O")
    assert r == ["CCO"]
    assert a == ["[Pt]"]
    assert p == ["CC=O"]


def test_parse_rsmi_file_reads_fixture() -> None:
    df = parse_rsmi_file(FIXTURE_DIR / "reactions.rsmi")
    assert df.height == 4
    assert set(df.columns) >= {
        "reaction_smiles",
        "patent_number",
        "year",
        "text_mined_yield",
        "calculated_yield",
    }


def test_ingest_uspto_matches_reaction_schema() -> None:
    reactions = ingest_uspto(FIXTURE_DIR / "reactions.rsmi")
    assert reactions.height == 4
    # type=chemical, source=uspto
    assert set(reactions["type"].to_list()) == {"chemical"}
    assert set(reactions["source"].to_list()) == {"uspto"}
    # yield_rate carried through when present (text_mined preferred)
    yields = reactions["yield_rate"].to_list()
    assert yields[0] == 0.85
    assert yields[1] == 0.92
    # coefficient=1.0 for every participant (SYN-RBL fixes real coefficients later)
    for row in reactions.iter_rows(named=True):
        for side in (row["reactants"], row["products"]):
            for stoich in side:
                assert stoich["coefficient"] == 1.0
