"""Thermodynamic augmentation via eQuilibrator (Open Item 03).

Populates the `delta_g` column (ΔG'°, standard transformed Gibbs free
energy at pH 7, 0.25 M ionic strength, 298.15 K) for every reaction
whose participants can be resolved to eQuilibrator-known compounds.

eQuilibrator's compound database is keyed on KEGG IDs, ChEBI IDs, InChI
strings, and canonical SMILES (fallback). For each reaction we build a
formula of the form:

    "coef1 SMILES1 + coef2 SMILES2 = coef3 SMILES3 + ..."

and hand it to `cc.parse_reaction_formula()`. Reactions whose participants
aren't in eQuilibrator's catalog (most custom metabolites) return None.

First use downloads ~100 MB of pre-computed tables to eQuilibrator's
cache directory. Subsequent calls are fast. Per-reaction call is still
~10-500 ms (component-contribution lookups), so we parallelize via joblib.
"""

from __future__ import annotations

import logging
from typing import Any

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


def _build_reaction_formula(
    reactants: list[dict],
    products: list[dict],
    smiles_by_mol: dict[str, str],
) -> str | None:
    """Build an eQuilibrator-parseable reaction string from stoichiometry + SMILES lookup.

    Returns None if any participant's mol_id has no SMILES in the lookup.
    """

    def _side(stoich_list: list[dict]) -> str | None:
        parts: list[str] = []
        for s in stoich_list:
            smi = smiles_by_mol.get(s["mol_id"])
            if not smi:
                return None
            parts.append(f"{s['coefficient']:g} {smi}")
        return " + ".join(parts)

    r = _side(reactants)
    p = _side(products)
    if r is None or p is None:
        return None
    return f"{r} = {p}"


def _compute_one(cc: Any, formula: str) -> float | None:
    """Safely invoke eQuilibrator; return None on any failure."""
    try:
        rxn = cc.parse_reaction_formula(formula)
        result = cc.standard_dg_prime(rxn)
        return float(result.value.m)
    except Exception as exc:
        log.debug("eQuilibrator skip: %s (%s)", exc, formula[:80])
        return None


def augment_thermo(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame | None = None,
    ph: float = 7.0,
    ionic_strength: str = "0.25 M",
    temperature: str = "298.15 K",
    n_jobs: int = 1,
) -> pl.DataFrame:
    """Populate `delta_g` on a reactions DataFrame using eQuilibrator.

    If `molecules` is passed, builds a mol_id → canonical_smiles lookup
    for resolving reaction formulas. When a molecule isn't in the lookup
    (or isn't in eQuilibrator's compound catalog), the reaction gets
    `delta_g=None`.

    When ``n_jobs > 1``, parallelizes the per-reaction eQuilibrator calls
    via joblib. Note: eQuilibrator itself isn't fully thread-safe for
    concurrent compound lookups; process-based parallelism (``n_jobs > 1``)
    is safe, threads are not.
    """
    ComponentContribution, Q_ = _import_equilibrator()

    cc = ComponentContribution()
    cc.p_h = Q_(str(ph))
    cc.ionic_strength = Q_(ionic_strength)
    cc.temperature = Q_(temperature)

    # Build mol_id → SMILES lookup if we have a molecules table.
    smiles_by_mol: dict[str, str] = {}
    if molecules is not None and "canonical_smiles" in molecules.columns:
        smiles_by_mol = {
            row["mol_id"]: row["canonical_smiles"]
            for row in molecules.iter_rows(named=True)
            if row.get("canonical_smiles")
        }

    # Build per-row formulas first; skip rows we can't resolve.
    formulas: list[str | None] = []
    for row in reactions.iter_rows(named=True):
        if smiles_by_mol and "reactants" in row and "products" in row:
            formula = _build_reaction_formula(row["reactants"], row["products"], smiles_by_mol)
        else:
            # No molecules table — fall back to reaction_smiles column as-is.
            formula = row.get("reaction_smiles") if row.get("reaction_smiles") else None
        formulas.append(formula)

    # Compute sequentially (safer) or in parallel.
    if n_jobs == 1:
        delta_g_values = [_compute_one(cc, f) if f else None for f in formulas]
    else:
        from joblib import Parallel, delayed

        delta_g_values = Parallel(n_jobs=n_jobs, backend="loky", prefer="processes")(
            delayed(_compute_one)(cc, f) if f else delayed(lambda: None)() for f in formulas
        )

    return reactions.with_columns(pl.Series("delta_g", delta_g_values, dtype=pl.Float64))


def is_available() -> bool:
    """Check whether equilibrator-api is importable."""
    try:
        import equilibrator_api  # noqa: F401
    except ImportError:
        return False
    return True
