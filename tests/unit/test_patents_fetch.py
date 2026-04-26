import json
from pathlib import Path

import polars as pl
import responses

from aichemy.preprocessing.patents.fetch import (
    PatentMetadata,
    fetch_patents,
    write_metadata_parquet,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "patents" / "sample_patentsview_response.json"
ENDPOINT = "https://search.patentsview.org/api/v1/patent"


@responses.activate
def test_fetch_patents_returns_metadata_objects():
    responses.add(
        responses.POST,
        ENDPOINT,
        json=json.loads(FIXTURE.read_text()),
        status=200,
    )
    out = fetch_patents(["7456123", "9999999"], endpoint=ENDPOINT, max_retries=1)
    assert len(out) == 2
    by_id = {p.patent_number: p for p in out}
    assert by_id["7456123"].filing_date == "2005-03-14"
    assert by_id["7456123"].abstract.startswith("A method")
    assert "C07D 401/12" in by_id["7456123"].cpc_codes
    assert by_id["7456123"].claims_text.startswith("1. A process")
    assert by_id["7456123"].fetch_status == "ok"
    assert by_id["9999999"].abstract is None
    assert by_id["9999999"].fetch_status == "ok"


@responses.activate
def test_fetch_patents_records_error_status_after_retry_exhaustion():
    responses.add(responses.POST, ENDPOINT, status=500)
    out = fetch_patents(["7456123"], endpoint=ENDPOINT, max_retries=2)
    assert len(out) == 1
    assert out[0].fetch_status == "error"


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
