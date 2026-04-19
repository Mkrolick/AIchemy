"""Yield imputation strategies (Stage 09).

Fills missing `yield_rate` values using one of three strategies chosen via
`config.yields.strategy`:

- `global_mean`: mean of all observed yields
- `per_ec_class`: mean per EC class for enzymatic reactions; fallback to
  global mean where a class has no observations
- `fixed`: single user-configured value
"""

from __future__ import annotations

import polars as pl

from aichemy.config import YieldConfig, YieldImputationStrategy


def global_mean_imputer(df: pl.DataFrame) -> pl.DataFrame:
    """Fill missing `yield_rate` with the mean of observed values.

    If all values are null (nothing to average), the column is left unchanged.
    """
    series = df.get_column("yield_rate")
    mean = series.drop_nulls().mean()
    if mean is None:
        return df
    return df.with_columns(pl.col("yield_rate").fill_null(mean))


def fixed_value_imputer(df: pl.DataFrame, value: float) -> pl.DataFrame:
    """Fill missing `yield_rate` with a single configured value."""
    return df.with_columns(pl.col("yield_rate").fill_null(value))


def per_ec_class_imputer(df: pl.DataFrame) -> pl.DataFrame:
    """Fill missing `yield_rate` with per-EC-class mean; fallback to global mean.

    Requires an `ec_class` column (from MetaNetX ingestion). Chemical-source
    rows that lack an `ec_class` fall back to global mean directly.
    """
    global_mean = df.get_column("yield_rate").drop_nulls().mean()

    class_means = df.group_by("ec_class").agg(pl.col("yield_rate").mean().alias("_ec_mean"))
    out = (
        df.join(class_means, on="ec_class", how="left")
        .with_columns(
            pl.coalesce(
                pl.col("yield_rate"),
                pl.col("_ec_mean"),
                pl.lit(global_mean),
            ).alias("yield_rate")
        )
        .drop("_ec_mean")
    )
    return out


def augment_yields(df: pl.DataFrame, config: YieldConfig) -> pl.DataFrame:
    """Dispatch to the configured imputation strategy."""
    if config.strategy == YieldImputationStrategy.GLOBAL_MEAN:
        return global_mean_imputer(df)
    if config.strategy == YieldImputationStrategy.PER_EC_CLASS:
        return per_ec_class_imputer(df)
    if config.strategy == YieldImputationStrategy.FIXED:
        return fixed_value_imputer(df, value=config.fixed_value)
    raise ValueError(f"Unknown yield imputation strategy: {config.strategy!r}")
