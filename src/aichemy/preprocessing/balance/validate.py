"""Universal atom-count validation for reactions.

Runs on every row post-balance (MetaNetX and USPTO alike). Computes the
total atom counts on each side of the reaction via RDKit (including
implicit hydrogens) and returns True iff every element matches. Supports
an `ignore_elements` list for cases where a source database uses a
convention that elides protons or waters (MetaNetX being the canonical
example).

This stage is stoichiometry-aware: coefficients scale the per-molecule
atom counts before summing. Non-integer coefficients are handled
correctly (e.g. combustion half-reactions).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from enum import StrEnum

import polars as pl
from rdkit import Chem

from aichemy.preprocessing.chem.smiles import parse


class UnbalancedPolicy(StrEnum):
    """What to do with reactions flagged as unbalanced by atom-count check."""

    FLAG = "flag"  # default: set balanced=False, keep row
    DROP = "drop"  # remove unbalanced rows entirely
    HEURISTIC_H = "heuristic_h"  # attempt to balance by adding/removing H+
    HEURISTIC_H2O = "heuristic_h2o"  # attempt to balance by adding/removing H2O


def atom_counts(smiles: str, coefficient: float) -> Counter[str]:
    """Return element → count for a SMILES molecule, scaled by coefficient.

    Returns an empty Counter if the SMILES cannot be parsed.
    """
    mol = parse(smiles)
    if mol is None:
        return Counter()
    mol_with_h = Chem.AddHs(mol)
    raw: Counter[str] = Counter()
    for atom in mol_with_h.GetAtoms():
        raw[atom.GetSymbol()] += 1
    return Counter({elem: count * coefficient for elem, count in raw.items()})


def _sum_side(side: Iterable[dict]) -> Counter[str]:
    totals: Counter[str] = Counter()
    for item in side:
        totals.update(atom_counts(item["smiles"], item["coefficient"]))
    return totals


def is_balanced(
    reactants: Iterable[dict],
    products: Iterable[dict],
    ignore_elements: Sequence[str] = (),
    tolerance: float = 1e-6,
) -> bool:
    """Check atom balance of a reaction.

    Each reactant/product is a dict with ``smiles`` and ``coefficient``.
    `ignore_elements` skips per-element comparison (e.g. ["H"] for MetaNetX's
    convention of eliding protons). `tolerance` absorbs floating-point noise
    from non-integer coefficients.
    """
    r = _sum_side(reactants)
    p = _sum_side(products)
    all_elements = set(r) | set(p)
    for element in all_elements:
        if element in ignore_elements:
            continue
        if abs(r.get(element, 0) - p.get(element, 0)) > tolerance:
            return False
    return True


def try_heuristic_proton_balance(
    reactants: list[dict],
    products: list[dict],
    tolerance: float = 1e-6,
) -> tuple[list[dict], list[dict]] | None:
    """Attempt to balance H count by adding a H+ (represented as `[H+]`) to one side.

    Returns the adjusted (reactants, products) if balance is restored for H
    alone; None if adding H+ does not produce a balanced reaction.
    """
    r = _sum_side(reactants)
    p = _sum_side(products)
    h_diff = r.get("H", 0) - p.get("H", 0)
    if abs(h_diff) < tolerance:
        return None  # already balanced, no adjustment needed
    # Check every other element balances already.
    for element in set(r) | set(p):
        if element == "H":
            continue
        if abs(r.get(element, 0) - p.get(element, 0)) > tolerance:
            return None
    # Add |h_diff| protons to the side with less H.
    proton = {"smiles": "[H+]", "coefficient": abs(h_diff)}
    if h_diff > 0:
        return reactants, [*products, proton]
    return [*reactants, proton], products


def try_heuristic_water_balance(
    reactants: list[dict],
    products: list[dict],
    tolerance: float = 1e-6,
) -> tuple[list[dict], list[dict]] | None:
    """Attempt to balance reaction by adding H2O if only H (×2) and O (×1) differ.

    Returns adjusted (reactants, products) on success; None otherwise.
    """
    r = _sum_side(reactants)
    p = _sum_side(products)
    o_diff = r.get("O", 0) - p.get("O", 0)
    h_diff = r.get("H", 0) - p.get("H", 0)

    if abs(o_diff) < tolerance and abs(h_diff) < tolerance:
        return None  # already balanced on O + H
    # For water balance: h_diff / o_diff must equal 2 and other elements balance.
    if abs(o_diff) < tolerance:
        return None  # would require H without O
    ratio = h_diff / o_diff if o_diff != 0 else 0
    if abs(ratio - 2) > 0.01:
        return None
    for element in set(r) | set(p):
        if element in ("H", "O"):
            continue
        if abs(r.get(element, 0) - p.get(element, 0)) > tolerance:
            return None
    water = {"smiles": "O", "coefficient": abs(o_diff)}
    if o_diff > 0:
        return reactants, [*products, water]
    return [*reactants, water], products


def validate_reactions(
    df: pl.DataFrame,
    molecules: pl.DataFrame | None = None,
    ignore_elements: Sequence[str] = (),
    unbalanced_policy: UnbalancedPolicy = UnbalancedPolicy.FLAG,
) -> pl.DataFrame:
    """Populate a `balanced: bool` column on a reactions DataFrame.

    Reactions carry ``reactants``/``products`` as lists of structs keyed
    either directly by ``smiles`` (the format used in the standalone
    test suite) or by ``mol_id`` (the format used by the full pipeline).
    When the ``mol_id`` form is used, pass the ``molecules`` DataFrame
    so mol_ids can be resolved to canonical SMILES for atom counting.
    """
    smiles_by_mol: dict[str, str | None] = {}
    if molecules is not None and "mol_id" in molecules.columns:
        smiles_by_mol = dict(
            zip(
                molecules["mol_id"].to_list(),
                molecules["canonical_smiles"].to_list(),
                strict=True,
            )
        )

    def _resolve(side: list[dict]) -> list[dict]:
        resolved: list[dict] = []
        for s in side:
            if "smiles" in s:
                resolved.append({"smiles": s["smiles"], "coefficient": s["coefficient"]})
            else:
                mol_id = s["mol_id"]
                smi = smiles_by_mol.get(mol_id)
                if smi:
                    resolved.append({"smiles": smi, "coefficient": s["coefficient"]})
        return resolved

    balanced_vals: list[bool] = []
    keep_mask: list[bool] = []  # for DROP policy
    for row in df.iter_rows(named=True):
        reactants = _resolve(row["reactants"])
        products = _resolve(row["products"])

        if len(reactants) != len(row["reactants"]) or len(products) != len(row["products"]):
            balanced_vals.append(False)
            keep_mask.append(unbalanced_policy != UnbalancedPolicy.DROP)
            continue

        balanced = is_balanced(reactants, products, ignore_elements=ignore_elements)
        if balanced:
            balanced_vals.append(True)
            keep_mask.append(True)
            continue

        # Attempt heuristic repair if configured
        if unbalanced_policy == UnbalancedPolicy.HEURISTIC_H:
            repaired = try_heuristic_proton_balance(reactants, products)
            if repaired is not None:
                balanced_vals.append(True)
                keep_mask.append(True)
                continue
        elif unbalanced_policy == UnbalancedPolicy.HEURISTIC_H2O:
            repaired = try_heuristic_water_balance(reactants, products)
            if repaired is not None:
                balanced_vals.append(True)
                keep_mask.append(True)
                continue

        # Unbalanced + heuristic didn't apply (or wasn't configured)
        balanced_vals.append(False)
        keep_mask.append(unbalanced_policy != UnbalancedPolicy.DROP)

    # Write the strict atom-count result to `rdkit_balanced`. The upstream
    # `balanced` column is preserved as-is — it carries the per-source
    # claim (SYN-RBL conf>0.8 for USPTO, curator is_balanced=B for MetaNetX).
    # `rdkit_balanced` is the trusted per-element mass-balance check.
    out = df.with_columns(pl.Series("rdkit_balanced", balanced_vals, dtype=pl.Boolean))
    if unbalanced_policy == UnbalancedPolicy.DROP:
        out = out.filter(pl.Series("_keep", keep_mask, dtype=pl.Boolean))
    return out
