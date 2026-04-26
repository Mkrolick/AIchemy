"""Unit tests for the L3 ChemCruz markdown parser."""

from __future__ import annotations

from aichemy_pricing.browserbase.parsers import chemcruz


def test_chemcruz_parses_minimal_markdown() -> None:
    md = "25 g  $35.00"
    quote = chemcruz.parse(md, sku="aspirin-50-78-2")
    assert quote is not None
    assert quote.vendor == "chemcruz"
    assert quote.sku == "aspirin-50-78-2"
    assert quote.currency == "USD"
    assert quote.pack_size_g == 25.0
    assert quote.price == 35.0


def test_chemcruz_real_fixture(fixture_dir) -> None:
    md = (fixture_dir / "bb_md_chemcruz_aspirin.md").read_text()
    quote = chemcruz.parse(md, sku="aspirin-50-78-2")
    assert quote is not None
    assert quote.price > 0
    assert quote.pack_size_g > 0
    # MW = 180.16 g/mol — parser must not match that as pack size.
    assert quote.pack_size_g != 180.16
