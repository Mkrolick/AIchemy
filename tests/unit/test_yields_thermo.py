"""Tests for thermodynamic yield refinement (post-export stage)."""

import math

import polars as pl
import pytest

from aichemy.preprocessing.augment.yields_thermo import (
    _RT_KJ_PER_MOL,
    augment_metanetx_yields_thermo,
    thermodynamic_yield,
)


def test_thermodynamic_yield_zero_dg_is_half():
    """ΔG = 0 → K = 1 → equilibrium fraction = 0.5."""
    assert thermodynamic_yield(0.0) == pytest.approx(0.5)


def test_thermodynamic_yield_negative_dg_favors_products():
    """Strongly negative ΔG → yield approaches 1."""
    # K' = exp(15/RT) ≈ 430, yield ≈ 430/431 ≈ 0.9977
    yld = thermodynamic_yield(-15.0)
    expected_K = math.exp(15.0 / _RT_KJ_PER_MOL)
    assert yld == pytest.approx(expected_K / (1 + expected_K))
    assert 0.99 < yld < 1.0


def test_thermodynamic_yield_positive_dg_favors_reactants():
    """Strongly positive ΔG → yield approaches 0."""
    yld = thermodynamic_yield(15.0)
    assert 0.0 < yld < 0.01


def test_thermodynamic_yield_clips_extreme_values():
    """Pathological ΔG (e.g., +1200 kJ/mol) shouldn't produce 0 exactly
    nor cause math.exp overflow."""
    yld_extreme = thermodynamic_yield(1200.0)
    yld_clipped = thermodynamic_yield(50.0)  # the default cap
    assert yld_extreme == pytest.approx(yld_clipped)
    # And the symmetric end:
    yld_neg_extreme = thermodynamic_yield(-1200.0)
    yld_neg_clipped = thermodynamic_yield(-50.0)
    assert yld_neg_extreme == pytest.approx(yld_neg_clipped)


def test_thermodynamic_yield_respects_min_max_bounds():
    """min_yield / max_yield clip the final value."""
    yld = thermodynamic_yield(-50.0, min_yield=0.05, max_yield=0.95)
    assert yld == pytest.approx(0.95)
    yld2 = thermodynamic_yield(50.0, min_yield=0.05, max_yield=0.95)
    assert yld2 == pytest.approx(0.05)


def test_augment_metanetx_replaces_metanetx_with_dg():
    df = pl.DataFrame(
        {
            "rxn_id": ["MNXR1", "MNXR2", "USPTO:1:0", "MNXR3"],
            "source": ["metanetx", "metanetx", "uspto", "metanetx"],
            "delta_g": [-20.0, 0.0, None, None],
            "yield_rate": [0.658, 0.658, 0.658, 0.658],
        }
    )
    out = augment_metanetx_yields_thermo(df)

    # MetaNetX rows with ΔG: replaced
    assert out["yield_rate"][0] > 0.999  # very favorable
    assert out["yield_rate"][1] == pytest.approx(0.5)  # ΔG=0
    assert out["_yield_source"][0] == "thermodynamic"
    assert out["_yield_source"][1] == "thermodynamic"

    # USPTO row: untouched
    assert out["yield_rate"][2] == pytest.approx(0.658)
    assert out["_yield_source"][2] == "global_mean"

    # MetaNetX without ΔG: untouched
    assert out["yield_rate"][3] == pytest.approx(0.658)
    assert out["_yield_source"][3] == "global_mean"


def test_augment_metanetx_raises_on_missing_columns():
    df = pl.DataFrame({"source": ["metanetx"], "yield_rate": [0.5]})
    with pytest.raises(ValueError, match="missing required columns"):
        augment_metanetx_yields_thermo(df)


def test_augment_metanetx_does_not_change_row_count():
    df = pl.DataFrame(
        {
            "rxn_id": ["A", "B", "C"],
            "source": ["metanetx", "uspto", "metanetx"],
            "delta_g": [-10.0, None, 5.0],
            "yield_rate": [0.5, 0.7, 0.9],
        }
    )
    out = augment_metanetx_yields_thermo(df)
    assert out.height == df.height
