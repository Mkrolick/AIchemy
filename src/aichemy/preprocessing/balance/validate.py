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

import polars as pl
from rdkit import Chem

from aichemy.preprocessing.chem.smiles import parse


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


def validate_reactions(
    df: pl.DataFrame,
    molecules: pl.DataFrame | None = None,
    ignore_elements: Sequence[str] = (),
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
    for row in df.iter_rows(named=True):
        reactants = _resolve(row["reactants"])
        products = _resolve(row["products"])
        # If any participant couldn't be resolved to a SMILES, we can't
        # compute balance accurately — mark unbalanced.
        if len(reactants) != len(row["reactants"]) or len(products) != len(row["products"]):
            balanced_vals.append(False)
        else:
            balanced_vals.append(is_balanced(reactants, products, ignore_elements=ignore_elements))

    return df.with_columns(pl.Series("balanced", balanced_vals, dtype=pl.Boolean))
