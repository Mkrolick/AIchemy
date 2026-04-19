"""Tests for yield imputation strategies (Stage 09)."""

from __future__ import annotations

import math

import polars as pl

from aichemy.config import YieldConfig, YieldImputationStrategy
from aichemy.preprocessing.augment.yields import (
    augment_yields,
    fixed_value_imputer,
    global_mean_imputer,
    per_ec_class_imputer,
)


def test_global_mean_imputer_fills_missing_with_mean() -> None:
    df = pl.DataFrame(
        {
            "rxn_id": ["a", "b", "c", "d"],
            "yield_rate": [0.8, 0.9, None, None],
        }
    )
    out = global_mean_imputer(df)
    filled = out["yield_rate"].to_list()
    assert filled[0] == 0.8
    assert filled[1] == 0.9
    assert math.isclose(filled[2], 0.85, abs_tol=1e-9)
    assert math.isclose(filled[3], 0.85, abs_tol=1e-9)


def test_global_mean_imputer_handles_all_missing() -> None:
    df = pl.DataFrame({"yield_rate": [None, None]}, schema={"yield_rate": pl.Float64})
    out = global_mean_imputer(df)
    # All-null → nothing to impute from; filled values stay null
    assert all(v is None for v in out["yield_rate"].to_list())


def test_fixed_value_imputer() -> None:
    df = pl.DataFrame({"yield_rate": [0.5, None]}, schema={"yield_rate": pl.Float64})
    out = fixed_value_imputer(df, value=0.85)
    assert out["yield_rate"].to_list() == [0.5, 0.85]


def test_per_ec_class_imputer_fills_with_class_mean_then_global() -> None:
    df = pl.DataFrame(
        {
            "rxn_id": ["a", "b", "c", "d", "e"],
            "ec_class": ["1.1.1.1", "1.1.1.1", "1.1.1.1", "2.7.1.1", "2.7.1.1"],
            "yield_rate": [0.9, 0.8, None, 0.5, None],
            "type": ["enzymatic"] * 5,
        }
    )
    out = per_ec_class_imputer(df)
    # Class 1.1.1.1 mean is (0.9 + 0.8) / 2 = 0.85; class 2.7.1.1 mean is 0.5
    filled = out["yield_rate"].to_list()
    assert filled[0] == 0.9
    assert filled[1] == 0.8
    assert math.isclose(filled[2], 0.85, abs_tol=1e-9)
    assert filled[3] == 0.5
    assert math.isclose(filled[4], 0.5, abs_tol=1e-9)


def test_per_ec_class_falls_back_to_global_mean_for_unknown_class() -> None:
    df = pl.DataFrame(
        {
            "ec_class": ["1.1.1.1", "9.9.9.9"],  # no observed yield in 9.9.9.9
            "yield_rate": [0.9, None],
            "type": ["enzymatic", "enzymatic"],
        }
    )
    out = per_ec_class_imputer(df)
    filled = out["yield_rate"].to_list()
    assert filled[1] == 0.9  # falls back to global mean


def test_augment_yields_dispatches_per_config_strategy() -> None:
    df = pl.DataFrame({"yield_rate": [0.5, None]}, schema={"yield_rate": pl.Float64})
    cfg = YieldConfig(strategy=YieldImputationStrategy.FIXED, fixed_value=0.77)
    out = augment_yields(df, cfg)
    assert out["yield_rate"].to_list() == [0.5, 0.77]
