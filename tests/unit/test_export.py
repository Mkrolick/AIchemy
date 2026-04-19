"""Tests for the export stage (Stage 12)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from aichemy.preprocessing.export import (
    assert_referential_integrity,
    write_manifest,
)


def _sample_reactions() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "rxn_id": ["r1", "r2"],
            "reactants": [
                [{"mol_id": "A", "coefficient": 1.0}],
                [{"mol_id": "B", "coefficient": 1.0}],
            ],
            "products": [
                [{"mol_id": "B", "coefficient": 1.0}],
                [{"mol_id": "C", "coefficient": 1.0}],
            ],
            "balanced": [True, False],
        }
    )


def _sample_molecules(mol_ids: list[str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "mol_id": mol_ids,
            "canonical_smiles": ["X"] * len(mol_ids),
        }
    )


def test_referential_integrity_passes_for_valid_data() -> None:
    reactions = _sample_reactions()
    molecules = _sample_molecules(["A", "B", "C"])
    assert_referential_integrity(reactions, molecules)  # no raise


def test_referential_integrity_raises_on_dangling_mol_id() -> None:
    reactions = _sample_reactions()
    molecules = _sample_molecules(["A", "B"])  # C is missing
    with pytest.raises(ValueError, match="dangling"):
        assert_referential_integrity(reactions, molecules)


def test_manifest_contains_expected_fields(tmp_path: Path) -> None:
    reactions = _sample_reactions()
    molecules = _sample_molecules(["A", "B", "C"])
    manifest = write_manifest(
        reactions,
        molecules,
        metanetx_version="4.4",
        uspto_slice="grants_1976_2016",
        output_path=tmp_path / "manifest.json",
    )
    assert manifest["counts"]["reactions"] == 2
    assert manifest["counts"]["molecules"] == 3
    assert manifest["counts"]["balanced_reactions"] == 1
    assert manifest["sources"]["metanetx_version"] == "4.4"
    assert manifest["sources"]["uspto_slice"] == "grants_1976_2016"
    assert "generated_at" in manifest
    assert "spec_version" in manifest

    # The manifest was written to disk and is readable.
    on_disk = json.loads((tmp_path / "manifest.json").read_text())
    assert on_disk == manifest
