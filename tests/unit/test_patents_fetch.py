import json
from pathlib import Path

import polars as pl
import pytest
import responses

from aichemy.preprocessing.patents.fetch import (
    PatentMetadata,
    _normalize_patent_number,
    fetch_patents,
    write_metadata_parquet,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "patents" / "sample_patentsview_response.json"
ENDPOINT = "https://api.uspto.gov/api/v1/patent/applications/search"
GRANT_FILE_URI = (
    "https://api.uspto.gov/api/v1/datasets/products/files/PTGRXML-SPLT/"
    "2008/ipg081125/11106297_07456123.xml"
)
SIGNED_URL = "https://data.uspto.gov/files/sample.xml"
SAMPLE_GRANT_XML = """<?xml version="1.0"?>
<us-patent-grant>
  <abstract id="abstract">
    <p>A method for the synthesis of substituted heterocyclic compounds.</p>
  </abstract>
  <claims>
    <claim id="CLM-00001">
      <claim-text>1. A process for preparing a compound of formula I.</claim-text>
    </claim>
    <claim id="CLM-00002">
      <claim-text>2. The process of claim 1.</claim-text>
    </claim>
  </claims>
</us-patent-grant>
"""


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USPTO_ODP_API_KEY", "fake-key-for-test")


@responses.activate
def test_fetch_patents_returns_metadata_objects():
    responses.add(
        responses.GET,
        ENDPOINT,
        json=json.loads(FIXTURE.read_text()),
        status=200,
    )
    responses.add(
        responses.GET,
        GRANT_FILE_URI,
        body=f'"Use redirect URL to download: {SIGNED_URL}. IMPORTANT..."',
        status=200,
    )
    responses.add(responses.GET, SIGNED_URL, body=SAMPLE_GRANT_XML, status=200)

    out = fetch_patents(["7456123", "9999999"], endpoint=ENDPOINT, max_retries=1)
    assert len(out) == 2
    by_id = {p.patent_number: p for p in out}

    assert by_id["7456123"].fetch_status == "ok"
    assert by_id["7456123"].filing_date == "2005-04-14"
    assert by_id["7456123"].grant_date == "2008-11-25"
    assert by_id["7456123"].assignee == "EXXONMOBIL RESEARCH & ENGINEERING CO."
    assert "B01J 29/084" in by_id["7456123"].cpc_codes
    assert by_id["7456123"].abstract.startswith("A method")
    assert by_id["7456123"].claims_text.startswith("1.")

    assert by_id["9999999"].fetch_status == "not_found"
    assert by_id["9999999"].abstract is None
    assert by_id["9999999"].cpc_codes == []


@responses.activate
def test_fetch_patents_records_error_status_after_retry_exhaustion():
    responses.add(responses.GET, ENDPOINT, status=500)
    out = fetch_patents(["7456123"], endpoint=ENDPOINT, max_retries=2)
    assert len(out) == 1
    assert out[0].fetch_status == "error"


@responses.activate
def test_fetch_grant_xml_auth_error_sets_error_status():
    """401 on the file-location lookup propagates to fetch_status='error'."""
    responses.add(
        responses.GET,
        ENDPOINT,
        json=json.loads(FIXTURE.read_text()),
        status=200,
    )
    responses.add(
        responses.GET,
        GRANT_FILE_URI,
        status=401,
    )

    out = fetch_patents(["7456123"], endpoint=ENDPOINT, max_retries=1)
    assert len(out) >= 1
    by_id = {p.patent_number: p for p in out}
    assert by_id["7456123"].fetch_status == "error"
    assert by_id["7456123"].abstract is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("US08200000B2", "8200000"),
        ("US07767665B2", "7767665"),
        ("US03930836", "3930836"),
        ("US05514680", "5514680"),
        ("USRE041149E1", "RE41149"),
        ("USD0123456S1", "D123456"),
        ("us08200000b2", "8200000"),
        ("  US08200000B2  ", "8200000"),
    ],
)
def test_normalize_patent_number_strips_to_odp_form(raw, expected):
    assert _normalize_patent_number(raw) == expected


@pytest.mark.parametrize("raw", ["", "garbage", "EP08200000", "1234567"])
def test_normalize_patent_number_returns_none_on_unknown_shape(raw):
    assert _normalize_patent_number(raw) is None


@responses.activate
def test_fetch_patents_handles_lowe_document_id_format():
    """Lowe document-id inputs ('US07456123B2') get normalized for the ODP
    query but the result keeps the input form so downstream joins work."""
    responses.add(
        responses.GET,
        ENDPOINT,
        json=json.loads(FIXTURE.read_text()),
        status=200,
    )
    responses.add(
        responses.GET,
        GRANT_FILE_URI,
        body=f'"Use redirect URL to download: {SIGNED_URL}. IMPORTANT..."',
        status=200,
    )
    responses.add(responses.GET, SIGNED_URL, body=SAMPLE_GRANT_XML, status=200)

    out = fetch_patents(["US07456123B2"], endpoint=ENDPOINT, max_retries=1)
    assert len(out) == 1
    assert out[0].patent_number == "US07456123B2"
    assert out[0].fetch_status == "ok"
    sent_q = responses.calls[0].request.url
    assert "7456123" in sent_q
    assert "US07456123B2" not in sent_q


def test_patent_metadata_dataclass_shape():
    p = PatentMetadata(
        patent_number="123",
        filing_date="2010-01-01",
        grant_date=None,
        abstract=None,
        claims_text=None,
        cpc_codes=[],
        assignee=None,
        fetch_status="ok",
    )
    assert p.patent_number == "123"


def test_write_metadata_parquet(tmp_path: Path):
    items = [
        PatentMetadata(
            patent_number="123",
            filing_date="2010-01-01",
            grant_date="2012-06-15",
            abstract="abc",
            claims_text="1. claim",
            cpc_codes=["C07D"],
            assignee="X Inc",
            fetch_status="ok",
        ),
    ]
    out = tmp_path / "patents.parquet"
    write_metadata_parquet(items, out)
    df = pl.read_parquet(out)
    assert df.height == 1
    assert df["patent_number"][0] == "123"
    assert df["cpc_codes"][0].to_list() == ["C07D"]
    assert df["fetch_status"][0] == "ok"
