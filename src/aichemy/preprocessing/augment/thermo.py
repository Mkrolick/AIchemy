"""Thermodynamic augmentation (Open Item 03).

Two-tier resolution of ΔG'° (standard transformed Gibbs free energy at
pH 7, 0.25 M ionic strength, 298.15 K):

1. **Tier 1 — novoStoic `MetaNetX_dG_dict.json`** (`NovoStoicThermoLookup`):
   precomputed compound-level ΔGf for ~15k MetaNetX compounds (Maranas
   group, 2025). Reactions composed by
   ``Σ coef·ΔGf(products) − Σ coef·ΔGf(reactants)``.
   Coverage on real MetaNetX: ~22% fully-resolvable reactions. Near-zero
   lookup cost (in-memory dict).

2. **Tier 2 — eQuilibrator component-contribution** (fallback): for
   reactions novoStoic doesn't fully cover. Uses MetaNetX IDs directly
   via ``metanetx.chemical:`` prefix. Confidence-filtered (σ ≤ 50 kJ/mol).

Values agree within ±1 kJ/mol on overlapping reactions (both use
component-contribution under the hood).
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import polars as pl

log = logging.getLogger(__name__)


# ---------- Tier 1: novoStoic precomputed formation energies -----------------


class NovoStoicThermoLookup:
    """Compute ΔG'° by composing pre-fit MetaNetX formation energies.

    Wraps `MetaNetX_dG_dict.json` from the novoStoic 2.0 project. Returns
    None when ANY participant's ΔGf is missing (no extrapolation).
    """

    _DEFAULT_PATH = Path("data/raw/novostoic/MetaNetX_dG_dict.json")

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or self._DEFAULT_PATH
        if not self._path.exists():
            raise FileNotFoundError(
                f"novoStoic ΔGf dict not found at {self._path}. Fetch with:\n"
                "  curl -L -o data/raw/novostoic/MetaNetX_dG_dict.json \\\n"
                "    https://raw.githubusercontent.com/maranasgroup/novoStoic2.0/"
                "dev/data/MetaNetX_dG_dict.json"
            )
        with open(self._path) as f:
            self._dg_f: dict[str, float] = json.load(f)
        log.info(
            "NovoStoicThermoLookup loaded %d compounds from %s",
            len(self._dg_f),
            self._path,
        )

    def __contains__(self, mol_id: str) -> bool:
        return mol_id in self._dg_f

    def compute(self, reactants: list[dict], products: list[dict]) -> float | None:
        """Compose reaction ΔG'° by summing ΔGf on each side."""
        try:
            reactant_sum = sum(float(s["coefficient"]) * self._dg_f[s["mol_id"]] for s in reactants)
            product_sum = sum(float(s["coefficient"]) * self._dg_f[s["mol_id"]] for s in products)
        except KeyError:
            return None  # any missing compound → skip
        result = product_sum - reactant_sum
        if math.isnan(result) or math.isinf(result):
            return None
        return float(result)


# ---------- Tier 2: eQuilibrator (imported lazily) ---------------------------


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


def _build_reaction_formula_mnx(
    reactants: list[dict],
    products: list[dict],
) -> str | None:
    """Build an eQuilibrator-parseable reaction string using MetaNetX IDs directly."""

    def _side(stoich_list: list[dict]) -> str | None:
        if not stoich_list:
            return None
        return " + ".join(
            f"{s['coefficient']:g} metanetx.chemical:{s['mol_id']}" for s in stoich_list
        )

    r = _side(reactants)
    p = _side(products)
    if r is None or p is None:
        return None
    return f"{r} = {p}"


def _build_reaction_formula_smiles(
    reactants: list[dict],
    products: list[dict],
    smiles_by_mol: dict[str, str],
) -> str | None:
    """Fallback: build formula from canonical SMILES lookup (USPTO path)."""

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


def _compute_one(cc: Any, formula: str, max_error_kj: float = 50.0) -> float | None:
    """Safely invoke eQuilibrator; return None on any failure or low confidence."""
    try:
        rxn = cc.parse_reaction_formula(formula)
        result = cc.standard_dg_prime(rxn)
        dg = float(result.value.m)
        err = float(result.error.m)
        if err > max_error_kj:
            return None
        return dg
    except Exception as exc:
        log.debug("eQuilibrator skip: %s (%s)", exc, formula[:80])
        return None


# ---------- Orchestrator -----------------------------------------------------


def augment_thermo(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame | None = None,
    *,
    novostoic_path: Path | None = None,
    use_equilibrator_fallback: bool = True,
    ph: float = 7.0,
    ionic_strength: str = "0.25 M",
    temperature: str = "298.15 K",
    n_jobs: int = 1,
) -> pl.DataFrame:
    """Populate `delta_g` column. Tier 1: novoStoic. Tier 2: eQuilibrator.

    novoStoic handles ~22% of MetaNetX reactions in ~0 ms per call. For the
    remaining reactions (and USPTO rows), eQuilibrator is called as a
    fallback when ``use_equilibrator_fallback=True`` and the module is
    installed. Set ``use_equilibrator_fallback=False`` for a novoStoic-only
    run (fast; no 1.3 GB cache required).
    """
    # Tier 1 — novoStoic precomputed lookup.
    novostoic: NovoStoicThermoLookup | None
    try:
        novostoic = NovoStoicThermoLookup(novostoic_path)
    except FileNotFoundError:
        log.warning("novoStoic dict not found; running eQuilibrator-only.")
        novostoic = None

    # First pass: try novoStoic on every row.
    delta_g_values: list[float | None] = [None] * reactions.height
    unresolved_indices: list[int] = []
    for i, row in enumerate(reactions.iter_rows(named=True)):
        if "reactants" not in row or "products" not in row or not row["reactants"]:
            continue
        is_mnx = row.get("source") == "metanetx" or all(
            s["mol_id"].startswith("MNXM") for s in row["reactants"] + row["products"]
        )
        if novostoic is not None and is_mnx:
            dg = novostoic.compute(row["reactants"], row["products"])
            if dg is not None:
                delta_g_values[i] = dg
                continue
        unresolved_indices.append(i)

    tier1_hits = sum(1 for v in delta_g_values if v is not None)
    log.info(
        "Tier 1 (novoStoic) resolved %d / %d reactions (%.1f%%).",
        tier1_hits,
        reactions.height,
        100 * tier1_hits / reactions.height if reactions.height else 0,
    )

    # Tier 2 — eQuilibrator for the unresolved.
    if use_equilibrator_fallback and unresolved_indices:
        try:
            ComponentContribution, Q_ = _import_equilibrator()
        except ImportError:
            log.warning("equilibrator-api unavailable; skipping Tier 2.")
            return reactions.with_columns(pl.Series("delta_g", delta_g_values, dtype=pl.Float64))

        cc = ComponentContribution()
        cc.p_h = Q_(str(ph))
        cc.ionic_strength = Q_(ionic_strength)
        cc.temperature = Q_(temperature)

        # Build mol_id → SMILES lookup for USPTO fallback.
        smiles_by_mol: dict[str, str] = {}
        if molecules is not None and "canonical_smiles" in molecules.columns:
            smiles_by_mol = {
                row["mol_id"]: row["canonical_smiles"]
                for row in molecules.iter_rows(named=True)
                if row.get("canonical_smiles")
            }

        formulas: list[str | None] = []
        for i in unresolved_indices:
            row = reactions.row(i, named=True)
            is_mnx = row.get("source") == "metanetx" or all(
                s["mol_id"].startswith("MNXM") for s in row["reactants"] + row["products"]
            )
            if is_mnx:
                formulas.append(_build_reaction_formula_mnx(row["reactants"], row["products"]))
            elif smiles_by_mol:
                formulas.append(
                    _build_reaction_formula_smiles(row["reactants"], row["products"], smiles_by_mol)
                )
            else:
                formulas.append(None)

        if n_jobs == 1:
            tier2_values = [_compute_one(cc, f) if f else None for f in formulas]
        else:
            from joblib import Parallel, delayed

            tier2_values = Parallel(n_jobs=n_jobs, backend="loky", prefer="processes")(
                delayed(_compute_one)(cc, f) if f else delayed(lambda: None)() for f in formulas
            )
        for idx, dg in zip(unresolved_indices, tier2_values, strict=True):
            if dg is not None:
                delta_g_values[idx] = dg

        tier2_hits = sum(1 for v in tier2_values if v is not None)
        log.info("Tier 2 (eQuilibrator) resolved %d additional reactions.", tier2_hits)

    total_hits = sum(1 for v in delta_g_values if v is not None)
    log.info(
        "Total ΔG'° coverage: %d / %d (%.1f%%).",
        total_hits,
        reactions.height,
        100 * total_hits / reactions.height if reactions.height else 0,
    )

    return reactions.with_columns(pl.Series("delta_g", delta_g_values, dtype=pl.Float64))


def is_available() -> bool:
    """Check whether equilibrator-api is importable."""
    try:
        import equilibrator_api  # noqa: F401
    except ImportError:
        return False
    return True
