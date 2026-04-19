from __future__ import annotations

from rdkit import Chem
from rdkit.Chem.rdchem import Mol


def parse(smiles: str | None) -> Mol | None:
    """Parse a SMILES string to an RDKit Mol. Returns None if invalid or None."""
    if not smiles:
        return None
    return Chem.MolFromSmiles(smiles)


def is_valid(smiles: str) -> bool:
    """Return True iff the SMILES string parses successfully."""
    return parse(smiles) is not None


def canonicalize(smiles: str) -> str:
    """Return the canonical SMILES representation. Raises ValueError if invalid."""
    mol = parse(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles!r}")
    return Chem.MolToSmiles(mol, canonical=True)
