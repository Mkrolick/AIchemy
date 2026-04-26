"""Unit tests for the L3 Cayman markdown parser."""

from __future__ import annotations

from aichemy_pricing.browserbase.parsers import cayman


def test_cayman_parses_minimal_markdown() -> None:
    md = "1 mg  $50"
    quote = cayman.parse(md, sku="14010")
    assert quote is not None
    assert quote.vendor == "cayman"
    assert quote.sku == "14010"
    assert quote.currency == "USD"
    assert quote.pack_size_g == 0.001
    assert quote.price == 50.0


def test_cayman_real_fixture(fixture_dir) -> None:
    md = (fixture_dir / "bb_md_cayman_14010.md").read_text()
    quote = cayman.parse(md, sku="14010")
    assert quote is not None
    assert quote.price > 0
    assert quote.pack_size_g > 0
    # MW = 352.5 g/mol — parser must not match that as pack size.
    assert quote.pack_size_g != 352.5
