"""Tests for USPTO ingestion (Stage 03)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aichemy.preprocessing.sources.uspto import (
    _float_or_none,
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
    assert df.height == 6
    assert set(df.columns) >= {
        "reaction_smiles",
        "patent_number",
        "year",
        "text_mined_yield",
        "calculated_yield",
    }


def test_ingest_uspto_matches_reaction_schema() -> None:
    reactions = ingest_uspto(FIXTURE_DIR / "reactions.rsmi")
    assert reactions.height == 6
    # type=chemical, source=uspto
    assert set(reactions["type"].to_list()) == {"chemical"}
    assert set(reactions["source"].to_list()) == {"uspto"}
    # yield_rate carried through when present
    yields = reactions["yield_rate"].to_list()
    # '85%' → 0.85; text-mined preferred over calculated ('90%' → 0.90)
    assert yields[0] == pytest.approx(0.85)
    # '82.0%' → 0.82 (decimal percent, text-mined preferred over '91%')
    assert yields[1] == pytest.approx(0.82)
    # empty text-mined → falls back to calculated '75%' → 0.75
    assert yields[2] == pytest.approx(0.75)
    # '100.5%' → capped at 1.0
    assert yields[3] == pytest.approx(1.0)
    # malformed text-mined ('INVALID') → falls back to calculated '60%' → 0.60
    assert yields[4] == pytest.approx(0.60)
    # both empty → None
    assert yields[5] is None
    # coefficient=1.0 for every participant (SYN-RBL fixes real coefficients later)
    for row in reactions.iter_rows(named=True):
        for side in (row["reactants"], row["products"]):
            for stoich in side:
                assert stoich["coefficient"] == 1.0


def test_ingest_uspto_text_mined_wins_over_calculated() -> None:
    """When both TextMinedYield and CalculatedYield are populated, text-mined wins."""
    reactions = ingest_uspto(FIXTURE_DIR / "reactions.rsmi")
    yields = reactions["yield_rate"].to_list()
    # Row 0: text=85%, calc=90% → 0.85 (not 0.90)
    assert yields[0] == pytest.approx(0.85)
    # Row 1: text=82.0%, calc=91% → 0.82 (not 0.91)
    assert yields[1] == pytest.approx(0.82)


# --- Unit tests for _float_or_none ---


def test_float_or_none_percent_integer() -> None:
    assert _float_or_none("85%") == pytest.approx(0.85)


def test_float_or_none_percent_integer_100() -> None:
    assert _float_or_none("100%") == pytest.approx(1.0)


def test_float_or_none_percent_decimal() -> None:
    assert _float_or_none("82.0%") == pytest.approx(0.82)


def test_float_or_none_over_100_capped() -> None:
    assert _float_or_none("100.5%") == pytest.approx(1.0)


def test_float_or_none_already_normalized() -> None:
    assert _float_or_none("0.85") == pytest.approx(0.85)


def test_float_or_none_zero_percent() -> None:
    assert _float_or_none("0%") == pytest.approx(0.0)


def test_float_or_none_empty_string() -> None:
    assert _float_or_none("") is None


def test_float_or_none_none() -> None:
    assert _float_or_none(None) is None


def test_float_or_none_whitespace_only() -> None:
    assert _float_or_none("   ") is None


def test_float_or_none_whitespace_around_percent() -> None:
    assert _float_or_none("  76%  ") == pytest.approx(0.76)


def test_float_or_none_malformed() -> None:
    assert _float_or_none("INVALID") is None


def test_float_or_none_negative() -> None:
    assert _float_or_none("-5%") is None


def test_float_or_none_result_in_unit_interval() -> None:
    for raw in ("0%", "50%", "100%", "100.5%", "0.5", "1.0"):
        result = _float_or_none(raw)
        assert result is not None
        assert 0.0 <= result <= 1.0, f"{raw!r} → {result} out of [0, 1]"
