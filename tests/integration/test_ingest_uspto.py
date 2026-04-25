"""Integration tests for USPTO ingestion (Stage 03).

Exercises ingest_uspto on the regenerated fixture (which uses realistic
'%'-suffixed yield cells) and verifies that yield_rate is populated and
within [0, 1] for all parseable rows.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aichemy.preprocessing.sources.uspto import ingest_uspto

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "uspto_sample"


@pytest.fixture
def rsmi_path(tmp_path: Path) -> Path:
    dest = tmp_path / "reactions.rsmi"
    shutil.copy(FIXTURE_DIR / "reactions.rsmi", dest)
    return dest


def test_ingest_produces_nonzero_yields(rsmi_path: Path) -> None:
    reactions = ingest_uspto(rsmi_path)
    assert reactions["yield_rate"].is_not_null().sum() > 0


def test_ingest_all_nonnull_yields_in_unit_interval(rsmi_path: Path) -> None:
    reactions = ingest_uspto(rsmi_path)
    nonnull = reactions.filter(reactions["yield_rate"].is_not_null())
    assert (nonnull["yield_rate"] >= 0.0).all()
    assert (nonnull["yield_rate"] <= 1.0).all()


def test_ingest_empty_and_malformed_cells_produce_none(rsmi_path: Path) -> None:
    reactions = ingest_uspto(rsmi_path)
    yields = reactions["yield_rate"].to_list()
    # Row 5: both TextMinedYield and CalculatedYield absent → None
    assert yields[5] is None


def test_ingest_does_not_crash_on_fixture(rsmi_path: Path) -> None:
    reactions = ingest_uspto(rsmi_path)
    assert reactions.height == 6
    assert "yield_rate" in reactions.columns
