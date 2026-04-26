"""Unit tests for ZincTrancheResolver."""

from __future__ import annotations

import textwrap

import pytest

from aichemy_pricing.resolvers.zinc_tranches import ZincTrancheResolver


def test_resolver_parses_synthetic_smi(tmp_path) -> None:
    """Use a synthetic SMI to exercise the parser without depending on a real
    ZINC file (which has variable column counts depending on cohort)."""
    smi = textwrap.dedent("""\
        smiles\tzinc_id\tinchikey\tvendor:supplier_code
        CCO\tZINC000000000702\tLFQSCWFLJHTTHZ-UHFFFAOYSA-N\tsigma:E7023;enamine:EN300-12345
        CC\tZINC000000000456\tOTMSDBZUPAUEDD-UHFFFAOYSA-N\tcombiblocksbb:CB-123
        """)
    p = tmp_path / "tiny.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    hits = res.resolve("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
    vendors = {h.vendor for h in hits}
    assert "sigma" in vendors and "enamine" in vendors


def test_resolver_returns_empty_for_unknown_inchikey(tmp_path) -> None:
    p = tmp_path / "empty.smi"
    p.write_text("smiles\tzinc_id\tinchikey\tvendor:supplier_code\n")
    res = ZincTrancheResolver.from_files([p])
    assert res.resolve("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z") == []


def test_resolver_skips_rows_without_inchikey(tmp_path) -> None:
    smi = "smiles\tzinc_id\tinchikey\tvendor:supplier_code\nCCO\tZINC0\t\tsigma:X\n"
    p = tmp_path / "noik.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    assert res.index == {}


def test_resolver_handles_alternate_column_order(tmp_path) -> None:
    """Real ZINC cohorts emit columns in different orders; the parser must
    locate the InChIKey by *shape*, not by fixed position."""
    # InChIKey first, SMILES last (some cohorts/exports do this).
    smi = (
        "inchikey\tzinc_id\tvendor:supplier_code\tsmiles\n"
        "LFQSCWFLJHTTHZ-UHFFFAOYSA-N\tZINC702\tsigma:E7023\tCCO\n"
    )
    p = tmp_path / "alt.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    hits = res.resolve("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
    assert len(hits) == 1 and hits[0].vendor == "sigma"


def test_resolver_rejects_non_inchikey_strings(tmp_path) -> None:
    """A row whose 'inchikey' column is malformed (wrong length / shape) must
    not pollute the index — even if a vendor field is present."""
    smi = "smiles\tzinc_id\tinchikey\tvendor:supplier_code\nCCO\tZINC0\tNOT-A-VALID-IK\tsigma:X\n"
    p = tmp_path / "bad.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    assert res.index == {}


@pytest.mark.live
def test_resolver_parses_real_tranche_fixture(fixture_dir) -> None:
    """If the fixture was captured, the resolver must extract at least one
    indexed InChIKey. A silent empty-index pass would mask the parser being
    out-of-sync with the real ZINC tranche file format."""
    p = fixture_dir / "zinc_tranche_sample.smi"
    if not p.exists() or p.stat().st_size == 0:
        pytest.skip("no zinc tranche fixture captured")
    res = ZincTrancheResolver.from_files([p])
    assert isinstance(res.index, dict)
    # If the fixture has tabs and at least one valid InChIKey-shaped column,
    # we must index at least one entry. If this fails, the parser is wrong
    # for the captured tranche format — fix the resolver, not the test.
    has_tabs = "\t" in p.read_text(errors="replace")
    if has_tabs:
        assert res.index, (
            "tranche fixture is tab-separated but parser indexed zero InChIKeys; "
            "real ZINC column layout likely differs from what the resolver assumes"
        )
