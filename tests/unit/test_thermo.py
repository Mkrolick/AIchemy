"""Tests for ΔG'° augmentation (Open Item 03).

The thermo module has two tiers:
- Tier 1 (novoStoic ΔGf dict) — always available when the JSON is present.
- Tier 2 (eQuilibrator) — optional fallback for reactions outside novoStoic's
  coverage. Gracefully no-ops when the dep isn't installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from aichemy.preprocessing.augment import thermo


def test_is_available_returns_bool() -> None:
    assert isinstance(thermo.is_available(), bool)


def test_novostoic_raises_when_json_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match="novoStoic"):
        thermo.NovoStoicThermoLookup(missing)


def test_novostoic_computes_reaction_dg(tmp_path: Path) -> None:
    dg_path = tmp_path / "dg.json"
    dg_path.write_text(json.dumps({"MNXM1": 0.0, "MNXM2": -50.0, "MNXM3": -20.0}))
    lookup = thermo.NovoStoicThermoLookup(dg_path)

    # 1 MNXM1 + 1 MNXM2 → 1 MNXM3: ΔG = -20 - (0 + -50) = +30
    dg = lookup.compute(
        [{"mol_id": "MNXM1", "coefficient": 1.0}, {"mol_id": "MNXM2", "coefficient": 1.0}],
        [{"mol_id": "MNXM3", "coefficient": 1.0}],
    )
    assert dg == pytest.approx(30.0)


def test_novostoic_returns_none_when_compound_missing(tmp_path: Path) -> None:
    dg_path = tmp_path / "dg.json"
    dg_path.write_text(json.dumps({"MNXM1": 0.0}))
    lookup = thermo.NovoStoicThermoLookup(dg_path)

    dg = lookup.compute(
        [{"mol_id": "MNXM1", "coefficient": 1.0}],
        [{"mol_id": "MNXM_UNKNOWN", "coefficient": 1.0}],  # missing
    )
    assert dg is None


def test_novostoic_respects_stoichiometric_coefficients(tmp_path: Path) -> None:
    dg_path = tmp_path / "dg.json"
    dg_path.write_text(json.dumps({"A": 10.0, "B": -5.0}))
    lookup = thermo.NovoStoicThermoLookup(dg_path)
    # 2 A → 3 B: ΔG = 3×(-5) − 2×10 = −35
    dg = lookup.compute(
        [{"mol_id": "A", "coefficient": 2.0}],
        [{"mol_id": "B", "coefficient": 3.0}],
    )
    assert dg == pytest.approx(-35.0)


def test_augment_thermo_uses_tier1_when_available(tmp_path: Path) -> None:
    """With novoStoic dict present and eQuilibrator fallback off, should
    populate delta_g from novoStoic only."""
    dg_path = tmp_path / "dg.json"
    dg_path.write_text(json.dumps({"MNXM1": 0.0, "MNXM2": -50.0}))

    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "source": ["metanetx"],
            "reactants": [[{"mol_id": "MNXM1", "coefficient": 1.0}]],
            "products": [[{"mol_id": "MNXM2", "coefficient": 1.0}]],
        }
    )
    out = thermo.augment_thermo(reactions, novostoic_path=dg_path, use_equilibrator_fallback=False)
    assert out["delta_g"].to_list() == [-50.0]


def test_augment_thermo_passes_through_when_neither_tier_resolves(tmp_path: Path) -> None:
    """With novoStoic missing entries and fallback disabled, delta_g stays null."""
    dg_path = tmp_path / "dg.json"
    dg_path.write_text(json.dumps({"MNXM999": 0.0}))

    reactions = pl.DataFrame(
        {
            "rxn_id": ["r1"],
            "source": ["metanetx"],
            "reactants": [[{"mol_id": "MNXM1", "coefficient": 1.0}]],
            "products": [[{"mol_id": "MNXM2", "coefficient": 1.0}]],
        }
    )
    out = thermo.augment_thermo(reactions, novostoic_path=dg_path, use_equilibrator_fallback=False)
    assert out["delta_g"].to_list() == [None]
