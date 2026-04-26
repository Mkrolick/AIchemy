import polars as pl

from aichemy.preprocessing.augment.licenses import augment_licenses


def _reactions(rxns):
    return pl.DataFrame(
        {
            "rxn_id": [r[0] for r in rxns],
            "source": [r[1] for r in rxns],
            "balanced": [True] * len(rxns),
        }
    )


def test_metanetx_rows_get_all_false():
    reactions = _reactions([("MNXR1", "metanetx")])
    cpc = pl.DataFrame(
        schema={
            "rxn_id": pl.Utf8,
            "patent_number": pl.Utf8,
            "patent_active": pl.Boolean,
            "cpc_ambiguous": pl.Boolean,
            "process_covered_cpc": pl.Boolean,
            "composition_covered_cpc": pl.Boolean,
        }
    )
    llm = pl.DataFrame(
        schema={
            "patent_number": pl.Utf8,
            "process_covered": pl.Boolean,
            "composition_covered": pl.Boolean,
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["patent_active"] is False
    assert row["process_covered"] is False
    assert row["composition_covered"] is False


def test_uspto_unambiguous_uses_cpc():
    reactions = _reactions([("USPTO:A:0", "uspto")])
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:A:0"],
            "patent_number": ["A"],
            "patent_active": [True],
            "cpc_ambiguous": [False],
            "process_covered_cpc": [True],
            "composition_covered_cpc": [False],
        }
    )
    llm = pl.DataFrame(
        schema={
            "patent_number": pl.Utf8,
            "process_covered": pl.Boolean,
            "composition_covered": pl.Boolean,
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["patent_active"] is True
    assert row["process_covered"] is True
    assert row["composition_covered"] is False


def test_uspto_ambiguous_uses_llm_when_present():
    reactions = _reactions([("USPTO:B:0", "uspto")])
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:B:0"],
            "patent_number": ["B"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
            "process_covered_cpc": [False],
            "composition_covered_cpc": [False],
        }
    )
    llm = pl.DataFrame(
        {
            "patent_number": ["B"],
            "process_covered": [False],
            "composition_covered": [True],
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["process_covered"] is False
    assert row["composition_covered"] is True


def test_uspto_ambiguous_falls_back_to_false_when_llm_missing():
    reactions = _reactions([("USPTO:C:0", "uspto")])
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:C:0"],
            "patent_number": ["C"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
            "process_covered_cpc": [False],
            "composition_covered_cpc": [False],
        }
    )
    llm = pl.DataFrame(
        schema={
            "patent_number": pl.Utf8,
            "process_covered": pl.Boolean,
            "composition_covered": pl.Boolean,
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["patent_active"] is True
    assert row["process_covered"] is False
    assert row["composition_covered"] is False
