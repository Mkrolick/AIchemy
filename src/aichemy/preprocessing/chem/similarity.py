from __future__ import annotations

import numpy as np
from rdkit import DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem.rdchem import Mol
from rdkit.DataStructs.cDataStructs import ExplicitBitVect


def morgan_fingerprint(mol: Mol, radius: int = 2, n_bits: int = 2048) -> ExplicitBitVect:
    """Compute Morgan (ECFP-like) fingerprint as an RDKit bit vector."""
    return AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)


def tanimoto(fp_a: ExplicitBitVect, fp_b: ExplicitBitVect) -> float:
    """Tanimoto similarity between two fingerprint bit vectors."""
    return float(DataStructs.TanimotoSimilarity(fp_a, fp_b))


def bulk_tanimoto(fps: list[ExplicitBitVect]) -> np.ndarray:
    """Pairwise Tanimoto matrix for a list of fingerprints."""
    n = len(fps)
    mat = np.zeros((n, n), dtype=np.float64)
    for i, fp_i in enumerate(fps):
        row = DataStructs.BulkTanimotoSimilarity(fp_i, fps)
        mat[i, :] = row
    return mat
