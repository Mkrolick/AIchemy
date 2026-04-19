import pytest
from aichemy.preprocessing.chem.smiles import canonicalize, is_valid, parse


def test_canonicalize_equivalent_smiles_produce_same_result() -> None:
    assert canonicalize("CCO") == canonicalize("OCC")


def test_canonicalize_returns_string() -> None:
    result = canonicalize("c1ccccc1")
    assert isinstance(result, str)
    assert result


def test_canonicalize_invalid_raises() -> None:
    with pytest.raises(ValueError):
        canonicalize("not_a_smiles_string")


def test_is_valid_true_for_ethanol() -> None:
    assert is_valid("CCO") is True


def test_is_valid_false_for_garbage() -> None:
    assert is_valid("not_a_smiles_string") is False


def test_parse_returns_mol_for_valid() -> None:
    assert parse("CCO") is not None


def test_parse_returns_none_for_invalid() -> None:
    assert parse("not_a_smiles_string") is None
