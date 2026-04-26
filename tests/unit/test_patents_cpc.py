from datetime import date
from pathlib import Path

import polars as pl

from aichemy.preprocessing.patents.cpc import (
    CPC_CLASSIFICATION_SCHEMA,
    CPCRules,
    classify_dataframe,
    classify_patent,
    load_cpc_rules,
)

RULES_PATH = Path(__file__).parent.parent / "fixtures" / "cpc_rules_test.yaml"


def _rules() -> CPCRules:
    return load_cpc_rules(RULES_PATH)


def test_inactive_patent_short_circuits():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07D 401/12"],
        filing_date_str="1985-01-01",
        today=today,
        rules=_rules(),
    )
    assert out.patent_active is False
    assert out.process_covered_cpc is False
    assert out.composition_covered_cpc is False
    assert out.cpc_ambiguous is False


def test_active_process_only():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07C 1/00"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.patent_active is True
    assert out.cpc_process_hit is True
    assert out.cpc_composition_hit is False
    assert out.cpc_ambiguous is False
    assert out.process_covered_cpc is True
    assert out.composition_covered_cpc is False


def test_active_composition_only():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07D 401/12"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_process_hit is False
    assert out.cpc_composition_hit is True
    assert out.cpc_ambiguous is False
    assert out.process_covered_cpc is False
    assert out.composition_covered_cpc is True


def test_active_both_hit_is_ambiguous():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07C 1/00", "C07D 401/12"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_ambiguous is True
    assert out.process_covered_cpc is False
    assert out.composition_covered_cpc is False


def test_active_a61k_is_ambiguous():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["A61K 31/505"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_ambiguous is True


def test_active_no_chemistry_codes_is_ambiguous():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["G06F 17/00"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_ambiguous is True


def test_missing_filing_date_treated_inactive():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07D"],
        filing_date_str=None,
        today=today,
        rules=_rules(),
    )
    assert out.patent_active is False


def test_classify_dataframe_joins_reactions_and_patents():
    today = date(2026, 4, 25)
    rules = _rules()
    reactions = pl.DataFrame(
        {
            "rxn_id": ["USPTO:7456123:0", "USPTO:1985111:0", "MNXR1"],
            "source": ["uspto", "uspto", "metanetx"],
        }
    )
    patents = pl.DataFrame(
        {
            "patent_number": ["7456123", "1985111"],
            "filing_date": ["2015-06-01", "1985-01-01"],
            "cpc_codes": [["C07D 401/12"], ["C07D 401/12"]],
        }
    )
    out = classify_dataframe(reactions, patents, rules=rules, today=today)
    assert out.height == 2
    by_rxn = {r["rxn_id"]: r for r in out.iter_rows(named=True)}
    assert by_rxn["USPTO:7456123:0"]["patent_active"] is True
    assert by_rxn["USPTO:7456123:0"]["composition_covered_cpc"] is True
    assert by_rxn["USPTO:1985111:0"]["patent_active"] is False
    for col, dtype in CPC_CLASSIFICATION_SCHEMA.items():
        assert col in out.columns
        assert out.schema[col] == dtype
