"""Unit tests for the L3 Tocris markdown parser.

Distinct from `test_vendors_tocris.py` (which tests the L2 httpx-based
vendor module). This one parses already-rendered markdown returned by
Browserbase Fetch.
"""

from __future__ import annotations

from aichemy_pricing.browserbase.parsers import tocris


def test_tocris_parses_minimal_markdown() -> None:
    md = "10 mg  $165"
    quote = tocris.parse(md, sku="jw-642_4906")
    assert quote is not None
    assert quote.vendor == "tocris"
    assert quote.sku == "jw-642_4906"
    assert quote.currency == "USD"
    assert quote.pack_size_g == 0.010
    assert quote.price == 165.0


def test_tocris_real_fixture(fixture_dir) -> None:
    md = (fixture_dir / "bb_md_tocris_jw642.md").read_text()
    quote = tocris.parse(md, sku="jw-642_4906")
    assert quote is not None
    assert quote.price > 0
    assert quote.pack_size_g > 0
    # MW = 308.42 g/mol — parser must not match that as pack size (the
    # exact molarity-stripper bug from sub-plan C revision 18).
    assert quote.pack_size_g != 308.42
