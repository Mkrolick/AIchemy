"""Tests for the raw-data downloader (Stage 01)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from aichemy.preprocessing.sources.fetch import download


def test_download_streams_content_to_disk(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        url="https://example.com/data.tsv",
        content=b"col1\tcol2\nfoo\tbar\n",
    )
    dest = tmp_path / "data.tsv"
    out = download("https://example.com/data.tsv", dest)
    assert out == dest
    assert dest.read_text() == "col1\tcol2\nfoo\tbar\n"


def test_download_skips_existing_file(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    dest = tmp_path / "data.tsv"
    dest.write_text("already-here")
    # No HTTP mock registered — if we do hit the network the test would fail.
    out = download("https://example.com/data.tsv", dest)
    assert out == dest
    assert dest.read_text() == "already-here"


def test_download_removes_partial_on_error(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    import httpx

    httpx_mock.add_response(
        url="https://example.com/data.tsv",
        status_code=404,
    )
    dest = tmp_path / "data.tsv"
    with pytest.raises(httpx.HTTPStatusError):
        download("https://example.com/data.tsv", dest)
    assert not dest.exists()
    assert not dest.with_suffix(dest.suffix + ".partial").exists()
