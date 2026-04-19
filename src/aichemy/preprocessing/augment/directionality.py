"""Directionality handling for reactions (Stage 11).

MetaNetX reactions carry a `direction` flag ("forward" or "reversible")
that serves as a proxy for thermodynamic favorability. This module
converts that flag into a concrete treatment:

- `ANNOTATE`: preserve the `direction` column as-is; solver decides how
  to handle reversibles.
- `DUPLICATE_REVERSIBLE`: emit two rows for each reversible reaction —
  one forward (kept as-is) and one reverse (reactants and products swapped,
  `rxn_id` suffixed with `_rev`). Forward-only rows pass through untouched.
"""

from __future__ import annotations

from enum import StrEnum

import polars as pl


class DirectionalityMode(StrEnum):
    ANNOTATE = "annotate"
    DUPLICATE_REVERSIBLE = "duplicate_reversible"


def apply_directionality(
    df: pl.DataFrame,
    mode: DirectionalityMode = DirectionalityMode.ANNOTATE,
) -> pl.DataFrame:
    """Apply the given directionality treatment to a reactions DataFrame.

    Expects a `direction` column with values "forward" / "reversible" and a
    `rxn_id` column. In ``DUPLICATE_REVERSIBLE`` mode, each reversible row
    spawns an extra row with swapped reactants/products and a `_rev` suffix
    on `rxn_id`.
    """
    if mode == DirectionalityMode.ANNOTATE:
        return df

    if mode == DirectionalityMode.DUPLICATE_REVERSIBLE:
        reversible = df.filter(pl.col("direction") == "reversible")
        if reversible.height == 0:
            return df
        reversed_rows = reversible.with_columns(
            (pl.col("rxn_id") + "_rev").alias("rxn_id"),
            pl.col("products").alias("reactants"),
            pl.col("reactants").alias("products"),
            pl.lit("reverse").alias("direction"),
        )
        return pl.concat([df, reversed_rows], how="diagonal_relaxed")

    raise ValueError(f"Unknown directionality mode: {mode!r}")
