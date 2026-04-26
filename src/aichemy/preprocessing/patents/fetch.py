"""USPTO Open Data Portal (ODP) REST client.

Fetches patent metadata (filing date, abstract, claims, CPC codes) for the
USPTO patent numbers extracted from reaction `rxn_id`s. Used by the
`fetch_patent_metadata` DVC stage.

PatentsView (search.patentsview.org and api.patentsview.org) was retired in
April 2026 — every path now 301-redirects to the USPTO ODP transition guide.
This module targets the ODP at api.uspto.gov, which requires a free API key
(signup at developer.uspto.gov, supply via the ``USPTO_ODP_API_KEY`` env
var). ODP splits metadata and full text across two endpoints — search returns
metadata + a per-record ``fileLocationURI``, which is downloaded separately
(two-step: auth'd indirection + signed URL) and parsed for abstract/claims.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import requests

log = logging.getLogger(__name__)

API_KEY_ENV = "USPTO_ODP_API_KEY"

_GRANT_AUTH_ERROR_STATUSES = frozenset({401, 403, 429})


class GrantFetchError(Exception):
    """Raised by _fetch_grant_xml when the server returns an auth/rate-limit error.

    HTTP 401, 403, or 429 from either the file-location lookup or the
    signed-URL download are unrecoverable without operator action (bad key,
    insufficient permissions, or quota exhausted), so they propagate up to
    _fetch_batch which sets fetch_status="error" on the parent record.
    """


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
    api_key: str | None = None,
    max_retries: int = 3,
    batch_size: int = 25,
    backoff_seconds: float = 1.0,
) -> list[PatentMetadata]:
    """Fetch metadata for the given patent numbers from the USPTO ODP.

    Each batch is one Lucene OR-query against the ODP search endpoint; each
    hit triggers a follow-up two-step grant-XML download for abstract/claims.
    Returns one ``PatentMetadata`` per input number, with status:
      - ``"ok"``        — search hit + (optional) XML parsed
      - ``"not_found"`` — search returned no record for that number
      - ``"error"``     — search retries exhausted on a permanent failure
    """
    if api_key is None:
        api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"{API_KEY_ENV} is not set; obtain a free key at "
            "https://developer.uspto.gov and export it before running"
        )

    out: list[PatentMetadata] = []
    seen: set[str] = set()
    for i in range(0, len(patent_numbers), batch_size):
        batch = patent_numbers[i : i + batch_size]
        results = _fetch_batch(batch, endpoint, api_key, max_retries, backoff_seconds)
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
    api_key: str,
    max_retries: int,
    backoff_seconds: float,
) -> list[PatentMetadata]:
    q = "applicationMetaData.patentNumber:(" + " OR ".join(batch) + ")"
    headers = {"X-API-Key": api_key, "Accept": "application/json"}
    params = {"q": q, "limit": str(len(batch))}
    for attempt in range(max_retries):
        try:
            r = requests.get(endpoint, params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                pairs = _parse_response(r.json(), batch)
                for rec, raw in pairs:
                    if rec.fetch_status != "ok":
                        continue
                    file_uri = (raw.get("grantDocumentMetaData") or {}).get("fileLocationURI")
                    if not file_uri:
                        continue
                    try:
                        xml = _fetch_grant_xml(file_uri, api_key)
                    except GrantFetchError as exc:
                        log.warning(
                            "Grant XML auth/rate-limit error for %s: %s",
                            rec.patent_number,
                            exc,
                        )
                        rec.fetch_status = "error"
                        continue
                    if xml is None:
                        continue
                    abstract, claims_text = _parse_grant_xml(xml)
                    rec.abstract = abstract
                    rec.claims_text = claims_text
                return [rec for rec, _ in pairs]
            if r.status_code == 404:
                # ODP returns 404 with "No matching records found" — treat the
                # whole batch as not_found rather than retry.
                return [_not_found_record(pn) for pn in batch]
            if r.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            log.warning("ODP search returned %s for batch=%s", r.status_code, batch[:3])
            break
        except requests.RequestException as exc:
            log.warning("ODP search request failed (attempt %d): %s", attempt + 1, exc)
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
    return [_error_record(pn) for pn in batch]


def _parse_response(
    body: dict[str, Any], batch: list[str]
) -> list[tuple[PatentMetadata, dict[str, Any]]]:
    """Map a USPTO ODP search response to (PatentMetadata, raw_record) pairs.

    Captured contract (curl, 2026-04-26, against api.uspto.gov):
      body = {
        "count": int,
        "patentFileWrapperDataBag": [{
          "applicationNumberText": str,
          "applicationMetaData": {
            "patentNumber": str | null,
            "grantDate": str | null,         # YYYY-MM-DD
            "filingDate": str | null,        # YYYY-MM-DD
            "inventionTitle": str | null,
            "cpcClassificationBag": list[str],   # e.g. "B01J  29/084"
                                                 # (extra whitespace; collapsed)
            "firstApplicantName": str | null,
            ...
          },
          "assignmentBag": [
            {"assigneeBag": [{"assigneeNameText": str}, ...]},
            ...
          ],
          "grantDocumentMetaData": {"fileLocationURI": str},
          ...
        }, ...],
        "requestIdentifier": str,
      }

    Patent numbers absent from the result set become fetch_status="not_found".
    abstract + claims_text are NOT in this response — they come from the
    grant XML fetched via grantDocumentMetaData.fileLocationURI by
    _fetch_grant_xml / _parse_grant_xml. PatentsView v1 returned them inline;
    ODP does not.
    """
    by_id: dict[str, tuple[PatentMetadata, dict[str, Any]]] = {}
    for record in body.get("patentFileWrapperDataBag") or []:
        meta = record.get("applicationMetaData") or {}
        pn = meta.get("patentNumber")
        if not pn:
            continue
        pn = str(pn)

        cpc_raw = meta.get("cpcClassificationBag") or []
        cpc_codes = [re.sub(r"\s+", " ", c).strip() for c in cpc_raw if c]

        assignee = None
        for ab in record.get("assignmentBag") or []:
            for entry in ab.get("assigneeBag") or []:
                name = entry.get("assigneeNameText")
                if name:
                    assignee = name
                    break
            if assignee:
                break
        if assignee is None:
            assignee = meta.get("firstApplicantName")

        by_id[pn] = (
            PatentMetadata(
                patent_number=pn,
                filing_date=meta.get("filingDate"),
                grant_date=meta.get("grantDate"),
                abstract=None,
                claims_text=None,
                cpc_codes=cpc_codes,
                assignee=assignee,
                fetch_status="ok",
            ),
            record,
        )

    out: list[tuple[PatentMetadata, dict[str, Any]]] = []
    for pn in batch:
        if pn in by_id:
            out.append(by_id[pn])
        else:
            out.append((_not_found_record(pn), {}))
    return out


def _fetch_grant_xml(file_uri: str, api_key: str) -> str | None:
    """Resolve and download the grant XML pointed to by an ODP fileLocationURI.

    Two-step protocol:
      1. GET <file_uri>  with X-API-Key, ``allow_redirects=False``
         -> 302 with ``Location: <signed-url>`` (also echoed in body as
            ``"Use redirect URL to download: <signed-url>. IMPORTANT..."``).
            Older / mocked variants may return 200 with the same body and
            no ``Location`` header — both shapes are handled.
      2. GET <signed-url>  (no auth header)
         -> 200, full grant XML

    Returns the XML body on success, or None when the grant XML is genuinely
    absent (no signed URL in response, non-auth non-200 on signed download).
    Callers should keep fetch_status="ok" in that case — it is data absence,
    not an API error.

    Raises GrantFetchError for HTTP 401/403/429 from either step — these
    indicate a bad/expired key, insufficient permissions, or exhausted quota
    and require operator action; the caller should set fetch_status="error".
    """
    try:
        r = requests.get(
            file_uri,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=30,
            allow_redirects=False,
        )
        if r.status_code in _GRANT_AUTH_ERROR_STATUSES:
            raise GrantFetchError(f"file-location lookup returned HTTP {r.status_code}")
        signed_url = r.headers.get("Location")
        if not signed_url:
            m = re.search(r"https://data\.uspto\.gov/[^\s\"]+", r.text)
            if not m:
                log.warning(
                    "ODP file-location lookup returned %s with no signed URL",
                    r.status_code,
                )
                return None
            signed_url = m.group(0).rstrip(".")
        rr = requests.get(signed_url, timeout=60)
        if rr.status_code in _GRANT_AUTH_ERROR_STATUSES:
            raise GrantFetchError(f"signed-URL download returned HTTP {rr.status_code}")
        if rr.status_code != 200:
            log.warning("Grant XML download returned %s", rr.status_code)
            return None
        return rr.text
    except GrantFetchError:
        raise
    except requests.RequestException as exc:
        log.warning("Grant XML fetch failed: %s", exc)
        return None


def _parse_grant_xml(xml: str) -> tuple[str | None, str | None]:
    """Extract abstract + concatenated claims text from a USPTO grant XML.

    Regex-based (USPTO grant XML has variable namespace/DTD shape; full XML
    parsing trips on the entity declarations on older patents). Multiple
    <claim ...>...</claim> blocks are concatenated newline-separated.
    Inner tags are stripped; whitespace collapsed. Returns (None, None) if
    the corresponding tag isn't present.
    """
    abstract: str | None = None
    m = re.search(r"<abstract\b[^>]*>(.*?)</abstract>", xml, re.DOTALL)
    if m:
        abstract = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() or None

    claim_blocks = re.findall(r"<claim(?:\s[^>]*)?>(.*?)</claim>", xml, re.DOTALL)
    claims_text: str | None = None
    if claim_blocks:
        cleaned = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", b)).strip() for b in claim_blocks]
        cleaned = [c for c in cleaned if c]
        if cleaned:
            claims_text = "\n".join(cleaned)

    return abstract, claims_text


def _not_found_record(patent_number: str) -> PatentMetadata:
    return PatentMetadata(
        patent_number=patent_number,
        filing_date=None,
        grant_date=None,
        abstract=None,
        claims_text=None,
        cpc_codes=[],
        assignee=None,
        fetch_status="not_found",
    )


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
