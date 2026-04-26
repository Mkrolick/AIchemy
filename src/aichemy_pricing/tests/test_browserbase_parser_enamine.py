"""Unit tests for the L3 Enamine markdown parser."""

from __future__ import annotations

from aichemy_pricing.browserbase.parsers import enamine


def test_enamine_parses_minimal_markdown() -> None:
    md = "1 g  $48.00"
    quote = enamine.parse(md, sku="EN300-7605608")
    assert quote is not None
    assert quote.vendor == "enamine"
    assert quote.sku == "EN300-7605608"
    assert quote.currency == "USD"
    assert quote.pack_size_g == 1.0
    assert quote.price == 48.0


def test_enamine_real_fixture(fixture_dir) -> None:
    md = (fixture_dir / "bb_md_enamine_EN300_7605608.md").read_text()
    quote = enamine.parse(md, sku="EN300-7605608")
    assert quote is not None
    assert quote.price > 0
    assert quote.pack_size_g > 0
    # MW = 160.18 g/mol — parser must not match that as pack size.
    assert quote.pack_size_g != 160.18
