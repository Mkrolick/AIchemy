from aichemy.preprocessing.chem.filters import (
    carbon_count,
    has_hydrocarbon_reactant_and_product,
)


def test_carbon_count_methane() -> None:
    assert carbon_count("C") == 1


def test_carbon_count_ethanol() -> None:
    assert carbon_count("CCO") == 2


def test_carbon_count_benzene_aromatic() -> None:
    assert carbon_count("c1ccccc1") == 6


def test_carbon_count_water() -> None:
    assert carbon_count("O") == 0


def test_carbon_count_ammonia() -> None:
    assert carbon_count("N") == 0


def test_hydrocarbon_filter_passes_ethanol_reaction() -> None:
    reactants = ["CCO"]
    products = ["CC=O"]
    assert has_hydrocarbon_reactant_and_product(reactants, products, min_carbons=2) is True


def test_hydrocarbon_filter_rejects_water_coproduct() -> None:
    reactants = ["CCO"]
    products = ["CC=O", "O"]
    assert has_hydrocarbon_reactant_and_product(reactants, products, min_carbons=2) is False


def test_hydrocarbon_filter_rejects_inorganic_reactant() -> None:
    reactants = ["O", "CCO"]
    products = ["CC=O"]
    assert has_hydrocarbon_reactant_and_product(reactants, products, min_carbons=2) is False
