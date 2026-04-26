"""Unit tests for the L3 Sigma-Aldrich markdown parser."""

from __future__ import annotations

from aichemy_pricing.browserbase.parsers import sigma


def test_sigma_parses_minimal_markdown() -> None:
    md = "Pack: 5 g | Price: $12.50"
    quote = sigma.parse(md, sku="202630")
    assert quote is not None
    assert quote.vendor == "sigma"
    assert quote.sku == "202630"
    assert quote.currency == "USD"
    assert quote.pack_size_g == 5.0
    assert quote.price == 12.5


def test_sigma_real_fixture_does_not_match_molecular_weight(fixture_dir) -> None:
    """Fixture has 'Molecular Weight: 180.16 g/mol' BEFORE the price block —
    parser must not pair 180.16 g with the first $price."""
    md = (fixture_dir / "bb_md_sigma_aspirin.md").read_text()
    quote = sigma.parse(md, sku="A2093")
    assert quote is not None
    assert quote.price > 0
    assert quote.pack_size_g > 0
    # Sanity: the MW (180.16 g/mol) must not have leaked into pack-size.
    assert quote.pack_size_g != 180.16
