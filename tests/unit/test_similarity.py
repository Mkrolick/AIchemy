from aichemy.preprocessing.chem.similarity import (
    bulk_tanimoto,
    morgan_fingerprint,
    tanimoto,
)
from aichemy.preprocessing.chem.smiles import parse


def test_morgan_fingerprint_is_deterministic() -> None:
    mol = parse("CCO")
    fp1 = morgan_fingerprint(mol, radius=2, n_bits=2048)
    fp2 = morgan_fingerprint(mol, radius=2, n_bits=2048)
    assert tanimoto(fp1, fp2) == 1.0


def test_tanimoto_identical_is_one() -> None:
    fp = morgan_fingerprint(parse("CCO"))
    assert tanimoto(fp, fp) == 1.0


def test_tanimoto_disjoint_is_zero() -> None:
    fp_a = morgan_fingerprint(parse("C"))
    fp_b = morgan_fingerprint(parse("N#N"))
    assert tanimoto(fp_a, fp_b) == 0.0


def test_tanimoto_symmetric() -> None:
    fp_a = morgan_fingerprint(parse("CCO"))
    fp_b = morgan_fingerprint(parse("CCN"))
    assert tanimoto(fp_a, fp_b) == tanimoto(fp_b, fp_a)


def test_bulk_tanimoto_returns_square_matrix() -> None:
    fps = [morgan_fingerprint(parse(s)) for s in ["C", "CC", "CCC"]]
    mat = bulk_tanimoto(fps)
    assert mat.shape == (3, 3)
    assert mat[0, 0] == 1.0
    assert mat[0, 1] == mat[1, 0]
