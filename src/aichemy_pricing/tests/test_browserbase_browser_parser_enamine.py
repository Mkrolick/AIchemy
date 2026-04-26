"""Unit tests for the L3 Enamine browser-parser."""

from __future__ import annotations

from aichemy_pricing.browserbase.browser_parsers import enamine


def test_enamine_browser_parser_extracts_pack_price() -> None:
    md = "# EN300-7605608\n\n50 mg  $42.00\n100 mg  $78.00\n"
    quote = enamine.parse(md, sku="EN300-7605608")
    assert quote is not None
    assert quote.vendor == "enamine"
    assert quote.sku == "EN300-7605608"
    assert quote.currency == "USD"
    assert quote.price == 42.0
    # 50 mg = 0.05 g
    assert abs(quote.pack_size_g - 0.05) < 1e-9
    assert quote.raw is not None and quote.raw.get("source") == "browserbase_browser"


def test_enamine_browser_parser_returns_none_on_unmatched() -> None:
    quote = enamine.parse("nothing useful here", sku="EN300-NOPE")
    assert quote is None
