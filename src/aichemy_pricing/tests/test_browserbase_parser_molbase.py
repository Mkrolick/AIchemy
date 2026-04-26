"""Unit tests for the L3 Molbase markdown parser.

Molbase aggregates Chinese suppliers, so multi-currency support (CNY, USD,
EUR, GBP) is mandatory. Distinct from `test_vendors_molbase.py` (the L2
httpx-based parser).
"""

from __future__ import annotations

from aichemy_pricing.browserbase.parsers import molbase


def test_molbase_parses_usd_minimal_markdown() -> None:
    md = "100 g  $ 22.00"
    quote = molbase.parse(md, sku="50-78-2")
    assert quote is not None
    assert quote.vendor == "molbase"
    assert quote.sku == "50-78-2"
    assert quote.currency == "USD"
    assert quote.pack_size_g == 100.0
    assert quote.price == 22.00


def test_molbase_parses_cny_chinese_supplier() -> None:
    md = "1 kg  ¥ 88.00"
    quote = molbase.parse(md, sku="50-78-2")
    assert quote is not None
    assert quote.currency == "CNY"
    assert quote.pack_size_g == 1000.0
    assert quote.price == 88.00


def test_molbase_real_fixture(fixture_dir) -> None:
    md = (fixture_dir / "bb_md_molbase_aspirin.md").read_text()
    quote = molbase.parse(md, sku="50-78-2")
    assert quote is not None
    assert quote.price > 0
    assert quote.pack_size_g > 0
    assert quote.currency in ("USD", "CNY", "EUR", "GBP")
