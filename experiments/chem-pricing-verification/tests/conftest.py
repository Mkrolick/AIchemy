"""Shared fixtures for verification tests.

Each test in this directory probes a live vendor URL claimed by the report.
Tests are slow and network-dependent on purpose - the whole point is to confirm
the URL pattern actually works.

Run as:
    pytest tests/ -v -s --tb=short
or one at a time:
    pytest tests/test_fluorochem.py -v -s
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
}


def save_result(claim_id: str, payload: dict[str, Any]) -> pathlib.Path:
    out = RESULTS / f"{claim_id}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    return out


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
    ) as c:
        yield c
