"""Thermodynamic augmentation via eQuilibrator (Open Item 03).

Optional stage that enriches each reaction with a `delta_g` (ΔG'°,
standard transformed Gibbs free energy) computed via eQuilibrator's
component-contribution model. Useful for filtering thermodynamically
infeasible pathways before MILP solving.

Activation: install the `thermo` extra (`uv sync --extra thermo`) and
call `augment_thermo(reactions_df, ph=7.0, ionic_strength=0.25)`.

On first use, eQuilibrator downloads ~100 MB of pre-computed tables into
its cache directory. Subsequent calls are fast. If the package isn't
installed or the cache can't be populated, the module gracefully returns
the input DataFrame unchanged.
"""

from __future__ import annotations

import logging

import polars as pl

log = logging.getLogger(__name__)


def _import_equilibrator() -> tuple[type, type]:
    """Deferred import so users without the `thermo` extra can still import aichemy."""
    try:
        from equilibrator_api import Q_, ComponentContribution
    except ImportError as exc:
        raise ImportError(
            "equilibrator-api is required for thermodynamic augmentation. "
            "Install with `uv sync --extra thermo` (or `pip install equilibrator-api`)."
        ) from exc
    return ComponentContribution, Q_


def augment_thermo(
    reactions: pl.DataFrame,
    ph: float = 7.0,
    ionic_strength: str = "0.25 M",
    temperature: str = "298.15 K",
) -> pl.DataFrame:
    """Populate `delta_g` on a reactions DataFrame using eQuilibrator.

    Reactions must carry a `reaction_smiles` column. Rows whose SMILES can't
    be mapped to eQuilibrator identifiers get `delta_g=None` (left for the
    solver to decide what to do with).

    Returns a new DataFrame with `delta_g` added/overwritten. Does NOT
    require the `thermo` extra on import — only on call.
    """
    ComponentContribution, Q_ = _import_equilibrator()

    cc = ComponentContribution()
    cc.p_h = Q_(str(ph))
    cc.ionic_strength = Q_(ionic_strength)
    cc.temperature = Q_(temperature)

    delta_g_values: list[float | None] = []
    for rxn_smiles in reactions["reaction_smiles"].to_list():
        if rxn_smiles is None:
            delta_g_values.append(None)
            continue
        try:
            rxn = cc.parse_reaction_formula(rxn_smiles)
            result = cc.standard_dg_prime(rxn)
            delta_g_values.append(float(result.value.m))
        except Exception as exc:
            log.debug("eQuilibrator skip for %s: %s", rxn_smiles, exc)
            delta_g_values.append(None)

    return reactions.with_columns(pl.Series("delta_g", delta_g_values, dtype=pl.Float64))


def is_available() -> bool:
    """Check whether equilibrator-api is importable."""
    try:
        import equilibrator_api  # noqa: F401
    except ImportError:
        return False
    return True
