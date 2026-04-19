from __future__ import annotations

from collections.abc import Iterable

from aichemy.preprocessing.chem.smiles import parse


def carbon_count(smiles: str) -> int:
    """Return the count of carbon atoms (atomic number 6) in a SMILES molecule."""
    mol = parse(smiles)
    if mol is None:
        return 0
    count = 0
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 6:
            count += 1
    return count


def has_hydrocarbon_reactant_and_product(
    reactants: Iterable[str],
    products: Iterable[str],
    min_carbons: int = 2,
) -> bool:
    """Return True iff every reactant AND every product meets min_carbons.

    Matches the proposal's rule: 'Remove all reactions with less than or equal to
    1 carbon count among reactants or products'.
    """
    if not all(carbon_count(smiles) >= min_carbons for smiles in reactants):
        return False
    return all(carbon_count(smiles) >= min_carbons for smiles in products)
