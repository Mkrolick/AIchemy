import pytest

from aichemy.preprocessing.chem.identifiers import inchi_key


def test_inchi_key_is_deterministic() -> None:
    assert inchi_key("CCO") == inchi_key("CCO")


def test_inchi_key_canonical_equivalents_match() -> None:
    assert inchi_key("OCC") == inchi_key("CCO")


def test_inchi_key_differs_for_different_molecules() -> None:
    assert inchi_key("CCO") != inchi_key("CCN")


def test_inchi_key_invalid_raises() -> None:
    with pytest.raises(ValueError):
        inchi_key("not_a_smiles_string")
