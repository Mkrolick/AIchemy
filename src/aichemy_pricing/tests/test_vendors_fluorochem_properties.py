"""Tests for the Fluorochem product-page chemical-properties scraper.

Uses a real fixture page captured from Fluorochem 2026-04 (SKU F765353,
1-Cyclopropyl-N-(4-fluorobenzyl)methanamine) so the parser is exercised
against the actual JSON-LD shape Fluorochem publishes — not a hand-crafted
strawman.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aichemy_pricing.vendors.fluorochem_properties import (
    FluorochemProperties,
    _parse_purity_to_fraction,
    parse_fluorochem_product_html,
)

_FIXTURE_DIR = Path(__file__).parent / "data"


@pytest.fixture
def real_fluorochem_html() -> str:
    return (_FIXTURE_DIR / "fluorochem_F765353_product_page.html").read_text()


def test_parses_purity_from_real_fixture(real_fluorochem_html: str) -> None:
    """The captured F765353 page lists Purity: 98%."""
    props = parse_fluorochem_product_html(real_fluorochem_html, sku="F765353")
    assert props.sku == "F765353"
    assert props.purity_text == "98%"
    assert props.purity_fraction == pytest.approx(0.98)


def test_parses_other_chemistry_fields(real_fluorochem_html: str) -> None:
    props = parse_fluorochem_product_html(real_fluorochem_html, sku="F765353")
    assert props.name == "1-Cyclopropyl-N-(4-fluorobenzyl)methanamine"
    assert props.cas_number == "1019538-79-4"
    assert props.iupac_name == "(cyclopropylmethyl)[(4-fluorophenyl)methyl]amine"
    assert props.canonical_smiles == "FC1=CC=C(CNCC2CC2)C=C1"
    assert props.inchi_key == "JMKBYKGNJPSQPJ-UHFFFAOYSA-N"
    assert props.inchi.startswith("InChI=1S/C11H14FN/")
    assert props.mdl_number == "MFCD11140258"


def test_parses_molecular_weight(real_fluorochem_html: str) -> None:
    """C11H14FN nominal MW is 179.24 g/mol — should match the page value."""
    props = parse_fluorochem_product_html(real_fluorochem_html, sku="F765353")
    assert props.molecular_weight == pytest.approx(179.2380066)


def test_parses_physicochemical_descriptors(real_fluorochem_html: str) -> None:
    props = parse_fluorochem_product_html(real_fluorochem_html, sku="F765353")
    assert props.logp == pytest.approx(2.45487385533)
    assert props.hba == 1
    assert props.hbd == 1
    assert props.fsp3 == pytest.approx(0.454545454545)


def test_parses_hazard_fields(real_fluorochem_html: str) -> None:
    props = parse_fluorochem_product_html(real_fluorochem_html, sku="F765353")
    assert props.un_number == "2735"
    assert props.packing_group == "III"
    assert props.hazard_class == "8"
    assert props.shipping_name == "AMINES, LIQUID, CORROSIVE, N.O.S."


def test_raw_property_map_is_populated(real_fluorochem_html: str) -> None:
    """The raw_property_map preserves every additionalProperty entry, even
    fields the dataclass doesn't promote — forward-compatibility for new
    Fluorochem fields."""
    props = parse_fluorochem_product_html(real_fluorochem_html, sku="F765353")
    assert "Purity" in props.raw_property_map
    assert "CAS Number" in props.raw_property_map
    assert props.raw_property_map["Purity"] == "98%"


def test_returns_blank_record_on_unparseable_html() -> None:
    """A page with no JSON-LD still yields a record with the SKU set,
    so the caller can detect "page returned but no chemistry found"."""
    props = parse_fluorochem_product_html("<html><body>nope</body></html>", sku="F999999")
    assert props.sku == "F999999"
    assert props.purity_text is None
    assert props.purity_fraction is None
    assert props.raw_property_map == {}


def test_handles_non_product_jsonld() -> None:
    """If the only JSON-LD block on the page is non-Product (e.g. Organization
    or BreadcrumbList), we still return a clean blank record without crashing."""
    html = """
    <html><head>
    <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Organization","name":"Fluorochem"}
    </script>
    </head></html>
    """
    props = parse_fluorochem_product_html(html, sku="X1")
    assert props.purity_text is None
    assert props.raw_property_map == {}


def test_handles_jsonld_array() -> None:
    """schema.org permits an array of entities at the top level — handle it."""
    html = """
    <html><head>
    <script type="application/ld+json">
    [
      {"@type":"Organization","name":"Fluorochem"},
      {"@type":"Product","name":"X","sku":"F1",
       "additionalProperty":[{"@type":"PropertyValue","name":"Purity","value":"95%"}]}
    ]
    </script>
    </head></html>
    """
    props = parse_fluorochem_product_html(html, sku="F1")
    assert props.purity_text == "95%"
    assert props.purity_fraction == pytest.approx(0.95)


def test_handles_malformed_json() -> None:
    """A broken JSON-LD block shouldn't crash the parser; it should just be
    skipped and a blank record returned."""
    html = """
    <html><head>
    <script type="application/ld+json">{this is not json}</script>
    </head></html>
    """
    props = parse_fluorochem_product_html(html, sku="X")
    assert props.raw_property_map == {}


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("98%", 0.98),
        (">99%", 0.99),
        ("≥97%", 0.97),
        ("98.5%", 0.985),
        ("98% (HPLC)", 0.98),
        ("100%", 1.0),
        ("0%", 0.0),
        ("", None),
        (None, None),
        ("tech grade", None),
        ("HPLC grade", None),
        ("110%", None),  # nonsense — clip via None rather than silently capping
        ("-5%", None),  # ditto
    ],
)
def test_parse_purity_to_fraction(raw: str | None, expected: float | None) -> None:
    got = _parse_purity_to_fraction(raw)
    if expected is None:
        assert got is None
    else:
        assert got == pytest.approx(expected)


def test_dataclass_default_factory_does_not_share_state() -> None:
    """Two records mustn't share the same raw_property_map dict."""
    a = FluorochemProperties(sku="A")
    b = FluorochemProperties(sku="B")
    a.raw_property_map["x"] = "1"
    assert "x" not in b.raw_property_map
