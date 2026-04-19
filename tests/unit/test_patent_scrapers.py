"""Tests for USPTO PatentsView scraper (Open Item 08)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from aichemy.scrapers.patents import Patent, PatentSearcher


def test_patent_from_api_row() -> None:
    p = Patent.from_api(
        {
            "patent_id": "10123456",
            "patent_title": "Synthesis of something",
            "patent_date": "2020-01-15",
            "patent_abstract": "A method for...",
        }
    )
    assert p.patent_id == "10123456"
    assert p.title == "Synthesis of something"
    assert p.date == "2020-01-15"


def test_search_by_keyword_parses_response(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://search.patentsview.org/api/v1/patent/",
        json={
            "patents": [
                {
                    "patent_id": "10000001",
                    "patent_title": "Vanillin synthesis via lignin",
                    "patent_date": "2019-06-30",
                    "patent_abstract": "A process for producing vanillin...",
                },
                {
                    "patent_id": "10000002",
                    "patent_title": "Biocatalytic vanillin",
                    "patent_date": "2020-08-15",
                    "patent_abstract": None,
                },
            ]
        },
    )
    searcher = PatentSearcher(rate_limit_seconds=0.0)
    results = searcher.search_by_keyword("vanillin", max_results=2)
    assert len(results) == 2
    assert results[0].title.startswith("Vanillin")


def test_search_handles_http_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://search.patentsview.org/api/v1/patent/",
        status_code=503,
    )
    searcher = PatentSearcher(rate_limit_seconds=0.0)
    assert searcher.search_by_keyword("anything") == []
