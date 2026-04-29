"""Post-export thermodynamic yield refinement for MetaNetX reactions.

Pipeline-position-wise this stage runs AFTER `export`. It reads
`data/processed/reactions.parquet` and for MetaNetX rows where `delta_g`
is non-null, replaces the imputed `yield_rate` (a USPTO-derived global
mean from the upstream `augment_yields` stage) with a thermodynamic
estimate derived from the reaction's standard transformed Gibbs free
energy.

Why this is honest only for MetaNetX:
  - eQuilibrator / novoStoic ΔG'° are biochemistry-grade (cellular pH/T).
    They are physically meaningful for metabolic reactions.
  - USPTO patent reactions are organic chemistry under highly variable
    conditions (solvent, T, concentrations). A standard biochem ΔG'°
    has no defensible bearing on those, and `delta_g` is null for USPTO
    rows by design (the upstream `augment_thermo` stage skips them).

Formula:
  K' = exp(-ΔG'° / RT)
  fraction_at_eq = K' / (1 + K')

Clipping:
  ΔG'° is clipped to ±`max_abs_dg_kj_mol` (default 50) before the
  exponential. Without clipping, eQuilibrator's pathological
  extrapolations (we observed values out to ±1200 kJ/mol on rare
  / charged species) push K' to 10^200-ish and drag the resulting
  yield to either 0.0 or 1.0 exactly. A 0/1 yield then propagates as
  a degenerate constraint into the MILP.

  After clipping, yields are bounded roughly in [4e-9, 1−4e-9]; we
  also expose `min_yield`/`max_yield` knobs to tighten further if the
  solver dislikes extreme bounds.
"""

from __future__ import annotations

import math

import polars as pl

# Standard biochemistry reference state: pH 7.0, 0.25 M ionic strength,
# T = 298.15 K. RT in kJ/mol.
_RT_KJ_PER_MOL = 8.314_462_618e-3 * 298.15  # ≈ 2.4789 kJ/mol


def thermodynamic_yield(
    delta_g_kj_per_mol: float,
    *,
    max_abs_dg_kj_per_mol: float = 50.0,
    min_yield: float = 0.0,
    max_yield: float = 1.0,
) -> float:
    """Convert ΔG'° (kJ/mol) to an equilibrium-fraction yield in [0, 1].

    Uses K' = exp(-ΔG'°/RT), yield = K'/(1+K'). ΔG'° is clipped to
    ±``max_abs_dg_kj_per_mol`` to bound numerical excursions, then the
    final yield is clipped to ``[min_yield, max_yield]``.
    """
    dg = max(-max_abs_dg_kj_per_mol, min(max_abs_dg_kj_per_mol, delta_g_kj_per_mol))
    # exp(-dg/RT) is large when dg<<0 (favorable). Compute via 1/(1+exp(dg/RT))
    # to avoid overflow at the favorable end.
    yld = 1.0 / (1.0 + math.exp(dg / _RT_KJ_PER_MOL))
    return max(min_yield, min(max_yield, yld))


def augment_metanetx_yields_thermo(
    df: pl.DataFrame,
    *,
    max_abs_dg_kj_per_mol: float = 50.0,
    min_yield: float = 0.0,
    max_yield: float = 1.0,
) -> pl.DataFrame:
    """Replace `yield_rate` with thermo-derived value for MetaNetX rows
    that have a non-null `delta_g`. Other rows pass through unchanged.

    Adds an `_yield_source` audit column with values:
      "thermodynamic" — replaced via ΔG
      "global_mean"   — left as-is (USPTO row, or MetaNetX row missing ΔG)
    """
    required = {"source", "delta_g", "yield_rate"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    # Vectorize by computing the thermo yield in pure expressions.
    rt = _RT_KJ_PER_MOL
    cap = max_abs_dg_kj_per_mol

    dg_clipped = pl.col("delta_g").clip(-cap, cap)
    thermo_yield_expr = (1.0 / (1.0 + (dg_clipped / rt).exp())).clip(min_yield, max_yield)

    is_metanetx = pl.col("source") == "metanetx"
    has_dg = pl.col("delta_g").is_not_null()
    use_thermo = is_metanetx & has_dg

    out = df.with_columns(
        [
            pl.when(use_thermo)
            .then(thermo_yield_expr)
            .otherwise(pl.col("yield_rate"))
            .alias("yield_rate"),
            pl.when(use_thermo)
            .then(pl.lit("thermodynamic"))
            .otherwise(pl.lit("global_mean"))
            .alias("_yield_source"),
        ]
    )
    return out
