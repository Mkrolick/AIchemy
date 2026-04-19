from __future__ import annotations

from rdkit import Chem

from aichemy.preprocessing.chem.smiles import parse


def inchi_key(smiles: str) -> str:
    """Compute the standard InChIKey for a SMILES string."""
    mol = parse(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles!r}")
    key = Chem.MolToInchiKey(mol)
    if not key:
        raise ValueError(f"Could not compute InChIKey for SMILES: {smiles!r}")
    return key
