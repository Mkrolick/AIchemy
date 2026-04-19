from aichemy.preprocessing.augment.prices import PriceLookup, StubPriceLookup


def test_stub_price_lookup_returns_none_by_default() -> None:
    lookup: PriceLookup = StubPriceLookup()
    assert lookup.lookup("CCO") is None


def test_stub_price_lookup_returns_preloaded_value() -> None:
    lookup = StubPriceLookup({"CCO": 1.23})
    assert lookup.lookup("CCO") == 1.23
    assert lookup.lookup("CCN") is None
