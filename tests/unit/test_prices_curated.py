"""Tests for the curated realistic price catalog."""

from __future__ import annotations

from aichemy.preprocessing.augment.prices_curated import (
    CuratedPriceLookup,
    get_catalog,
)


def test_catalog_is_non_empty() -> None:
    catalog = get_catalog()
    assert len(catalog) >= 50


def test_catalog_values_are_positive_finite_floats() -> None:
    for _smiles, price in get_catalog().items():
        assert isinstance(price, float)
        assert price > 0
        assert price < 1e6  # nothing in academia costs more than $1M/g


def test_lookup_ethanol_known_price() -> None:
    lookup = CuratedPriceLookup()
    # CCO canonicalizes to CCO (already canonical)
    price = lookup.lookup("CCO")
    assert price is not None
    assert 0.001 < price < 0.1  # bulk ethanol ≈ $0.003/g


def test_lookup_matches_equivalent_representations() -> None:
    """Two equivalent SMILES for the same molecule should hit the same price."""
    lookup = CuratedPriceLookup()
    # Ethanol written forwards and backwards
    p1 = lookup.lookup("CCO")
    p2 = lookup.lookup("OCC")
    assert p1 == p2
    assert p1 is not None


def test_lookup_returns_none_for_unknown_molecule() -> None:
    lookup = CuratedPriceLookup()
    # A made-up weird fluorinated compound not in the catalog
    assert lookup.lookup("FC(F)(F)C(F)(F)C(F)(F)C(F)(F)F") is None


def test_lookup_returns_none_for_invalid_smiles() -> None:
    lookup = CuratedPriceLookup()
    assert lookup.lookup("not_a_smiles_string") is None
    assert lookup.lookup("") is None


def test_lookup_vanillin_high_value() -> None:
    """Vanillin should be an order of magnitude more expensive than bulk ethanol."""
    lookup = CuratedPriceLookup()
    vanillin = lookup.lookup("COc1cc(C=O)ccc1O")
    ethanol = lookup.lookup("CCO")
    assert vanillin is not None
    assert ethanol is not None
    assert vanillin > ethanol * 10
