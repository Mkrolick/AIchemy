"""End-to-end integration test for the licensing stages.

Runs the four new pipeline stages on a tiny synthetic fixture, with USPTO
ODP calls stubbed via ``responses`` and Anthropic calls stubbed via a
``MagicMock`` client. Verifies the data flows through to the
``augment_licenses`` output with correct columns for both USPTO and
MetaNetX rows (the latter exercises the left-join + ``fill_null(False)``
fallback path).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest
import responses

ODP_SEARCH = "https://api.uspto.gov/api/v1/patent/applications/search"
ODP_FILE_URI = (
    "https://api.uspto.gov/api/v1/datasets/products/files/PTGRXML-SPLT/"
    "2015/ipg150915/12345678_07456123.xml"
)
ODP_SIGNED_URL = "https://data.uspto.gov/files/integration-sample.xml"
SAMPLE_GRANT_XML = """<?xml version="1.0"?>
<us-patent-grant>
  <abstract id="abstract"><p>A medicinal preparation.</p></abstract>
  <claims>
    <claim id="CLM-00001"><claim-text>1. A composition comprising the active.</claim-text></claim>
  </claims>
</us-patent-grant>
"""


@pytest.fixture
def fake_reactions_full(tmp_path: Path) -> Path:
    df = pl.DataFrame(
        {
            "rxn_id": ["USPTO:7456123:0", "MNXR1"],
            "reaction_smiles": ["A.B>>C", "X>>Y"],
            "reactants": [
                [{"mol_id": "A", "coefficient": 1.0}, {"mol_id": "B", "coefficient": 1.0}],
                [{"mol_id": "X", "coefficient": 1.0}],
            ],
            "products": [
                [{"mol_id": "C", "coefficient": 1.0}],
                [{"mol_id": "Y", "coefficient": 1.0}],
            ],
            "type": ["chemical", "enzymatic"],
            "yield_rate": [0.85, 0.95],
            "delta_g": [None, None],
            "balanced": [True, True],
            "source": ["uspto", "metanetx"],
        }
    )
    out = tmp_path / "reactions_full.parquet"
    df.write_parquet(out)
    return out


@responses.activate
def test_full_license_flow_with_stubbed_apis(
    tmp_path: Path,
    fake_reactions_full: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses.add(
        responses.GET,
        ODP_SEARCH,
        json={
            "count": 1,
            "patentFileWrapperDataBag": [
                {
                    "applicationNumberText": "12345678",
                    "applicationMetaData": {
                        "patentNumber": "7456123",
                        "grantDate": "2015-09-15",
                        "filingDate": "2015-03-14",
                        "inventionTitle": "MEDICINAL PREPARATION",
                        "cpcClassificationBag": ["A61K 31/505"],
                    },
                    "assignmentBag": [{"assigneeBag": [{"assigneeNameText": "Acme"}]}],
                    "grantDocumentMetaData": {"fileLocationURI": ODP_FILE_URI},
                }
            ],
            "requestIdentifier": "integration-test",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        ODP_FILE_URI,
        body=f'"Use redirect URL to download: {ODP_SIGNED_URL}. IMPORTANT..."',
        status=200,
    )
    responses.add(responses.GET, ODP_SIGNED_URL, body=SAMPLE_GRANT_XML, status=200)
    monkeypatch.setenv("USPTO_ODP_API_KEY", "fake-key-for-test")

    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.name = "report_classification"
    fake_block.input = {
        "process_covered": False,
        "composition_covered": True,
        "confidence": 0.9,
        "rationale": "Independent claim 1 is composition-of-matter.",
    }
    fake_msg = MagicMock()
    fake_msg.stop_reason = "tool_use"
    fake_msg.content = [fake_block]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **kw: fake_client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    from aichemy.preprocessing.augment.licenses import augment_licenses
    from aichemy.preprocessing.patents.cpc import (
        classify_dataframe,
        load_cpc_rules,
    )
    from aichemy.preprocessing.patents.fetch import (
        fetch_patents,
        write_metadata_parquet,
    )
    from aichemy.preprocessing.patents.llm_classify import (
        classify_ambiguous_patents,
    )

    reactions = pl.read_parquet(fake_reactions_full)

    # 1. fetch_patent_metadata
    items = fetch_patents(["7456123"], endpoint=ODP_SEARCH, max_retries=1)
    patents_path = tmp_path / "patent_metadata.parquet"
    write_metadata_parquet(items, patents_path)

    # 2. classify_licenses_cpc
    rules = load_cpc_rules(Path("configs/cpc_rules.yaml"))
    cpc_df = classify_dataframe(
        reactions,
        pl.read_parquet(patents_path),
        rules=rules,
        today=date(2026, 4, 25),
    )
    cpc_path = tmp_path / "cpc.parquet"
    cpc_df.write_parquet(cpc_path)

    # 3. classify_licenses_llm
    llm_df = classify_ambiguous_patents(
        cpc=cpc_df,
        patents=pl.read_parquet(patents_path),
        reactions=reactions,
        cache_path=tmp_path / "cache.jsonl",
        out_path=tmp_path / "llm.parquet",
        client=fake_client,
        model="claude-haiku-4-5",
        max_retries=1,
    )

    # 4. augment_licenses
    out = augment_licenses(reactions, cpc_df, llm_df)

    # Schema: all three license columns present.
    assert {"patent_active", "process_covered", "composition_covered"} <= set(out.columns)

    by_rxn = {r["rxn_id"]: r for r in out.iter_rows(named=True)}

    # USPTO row: A61K is in ambiguous_codes → LLM verdict (False, True) wins.
    # filing_date 2015-03-14 + 20y = 2035-03-14 > today=2026-04-25 → active.
    assert by_rxn["USPTO:7456123:0"]["patent_active"] is True
    assert by_rxn["USPTO:7456123:0"]["process_covered"] is False
    assert by_rxn["USPTO:7456123:0"]["composition_covered"] is True

    # MetaNetX row: source=="metanetx" is excluded from cpc_df by
    # classify_dataframe, then left-joined back as null and fill_null(False).
    assert by_rxn["MNXR1"]["patent_active"] is False
    assert by_rxn["MNXR1"]["process_covered"] is False
    assert by_rxn["MNXR1"]["composition_covered"] is False
