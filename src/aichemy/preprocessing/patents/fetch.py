"""PatentsView REST client.

Fetches patent metadata (filing date, abstract, claims, CPC codes) for the
USPTO patent numbers extracted from reaction `rxn_id`s. Used by the
`fetch_patent_metadata` DVC stage.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import requests

log = logging.getLogger(__name__)


@dataclass
class PatentMetadata:
    patent_number: str
    filing_date: str | None
    grant_date: str | None
    abstract: str | None
    claims_text: str | None
    cpc_codes: list[str]
    assignee: str | None
    fetch_status: str  # "ok" | "not_found" | "error"


PATENT_METADATA_SCHEMA: dict[str, Any] = {
    "patent_number": pl.Utf8,
    "filing_date": pl.Utf8,
    "grant_date": pl.Utf8,
    "abstract": pl.Utf8,
    "claims_text": pl.Utf8,
    "cpc_codes": pl.List(pl.Utf8),
    "assignee": pl.Utf8,
    "fetch_status": pl.Utf8,
}


def fetch_patents(
    patent_numbers: list[str],
    *,
    endpoint: str,
    max_retries: int = 3,
    batch_size: int = 25,
    backoff_seconds: float = 1.0,
) -> list[PatentMetadata]:
    """Fetch metadata for the given patent numbers.

    PatentsView accepts a JSON POST with a query in its query DSL. We batch
    requests to amortize round-trip cost, retry on transient errors, and
    record `fetch_status="error"` on permanent failure (rather than raise,
    so the pipeline doesn't crash).
    """
    out: list[PatentMetadata] = []
    seen: set[str] = set()
    for i in range(0, len(patent_numbers), batch_size):
        batch = patent_numbers[i : i + batch_size]
        results = _fetch_batch(batch, endpoint, max_retries, backoff_seconds)
        for r in results:
            seen.add(r.patent_number)
            out.append(r)
    for pn in patent_numbers:
        if pn not in seen:
            out.append(_error_record(pn))
    return out


def _fetch_batch(
    batch: list[str],
    endpoint: str,
    max_retries: int,
    backoff_seconds: float,
) -> list[PatentMetadata]:
    payload = {
        "q": {"patent_number": batch},
        "f": [
            "patent_number",
            "patent_date",
            "patent_abstract",
            "claims",
            "cpcs",
            "assignees",
            "application",
        ],
        "o": {"per_page": len(batch)},
    }
    for attempt in range(max_retries):
        try:
            r = requests.post(endpoint, json=payload, timeout=30)
            if r.status_code == 200:
                return _parse_response(r.json(), batch)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            log.warning("PatentsView returned %s for batch=%s", r.status_code, batch[:3])
            break
        except requests.RequestException as exc:
            log.warning("PatentsView request failed (attempt %d): %s", attempt + 1, exc)
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
    return [_error_record(pn) for pn in batch]


def _parse_response(body: dict[str, Any], batch: list[str]) -> list[PatentMetadata]:
    by_id: dict[str, PatentMetadata] = {}
    for p in body.get("patents") or []:
        pn = str(p.get("patent_number"))
        claims_text = " ".join(c.get("text", "") for c in (p.get("claims") or []))
        cpc_codes = [c.get("cpc_group_id", "") for c in (p.get("cpcs") or [])]
        cpc_codes = [c for c in cpc_codes if c]
        assignees = p.get("assignees") or []
        assignee = assignees[0].get("assignee_organization") if assignees else None
        application = p.get("application") or {}
        by_id[pn] = PatentMetadata(
            patent_number=pn,
            filing_date=application.get("filing_date"),
            grant_date=p.get("patent_date"),
            abstract=p.get("patent_abstract"),
            claims_text=claims_text or None,
            cpc_codes=cpc_codes,
            assignee=assignee,
            fetch_status="ok",
        )
    out: list[PatentMetadata] = []
    for pn in batch:
        if pn in by_id:
            out.append(by_id[pn])
        else:
            out.append(
                PatentMetadata(
                    patent_number=pn,
                    filing_date=None,
                    grant_date=None,
                    abstract=None,
                    claims_text=None,
                    cpc_codes=[],
                    assignee=None,
                    fetch_status="not_found",
                )
            )
    return out


def _error_record(patent_number: str) -> PatentMetadata:
    return PatentMetadata(
        patent_number=patent_number,
        filing_date=None,
        grant_date=None,
        abstract=None,
        claims_text=None,
        cpc_codes=[],
        assignee=None,
        fetch_status="error",
    )


def write_metadata_parquet(items: list[PatentMetadata], path: Path) -> None:
    rows = [
        {
            "patent_number": p.patent_number,
            "filing_date": p.filing_date,
            "grant_date": p.grant_date,
            "abstract": p.abstract,
            "claims_text": p.claims_text,
            "cpc_codes": p.cpc_codes,
            "assignee": p.assignee,
            "fetch_status": p.fetch_status,
        }
        for p in items
    ]
    df = pl.DataFrame(rows, schema=PATENT_METADATA_SCHEMA)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
