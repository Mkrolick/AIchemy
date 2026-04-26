"""Unit tests for BrowserbaseClient. Mocks the POST so tests are offline."""

from __future__ import annotations

import json
import os

import httpx
import pytest

from aichemy_pricing.browserbase.client import BrowserbaseClient


def test_client_no_api_key_returns_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("BROWSERBASE_API_KEY", raising=False)
    c = BrowserbaseClient()
    assert not c.is_configured()
    assert c.fetch_markdown("https://example.com/x") is None  # silent no-op


def test_client_with_key_posts_to_fetch_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def mock_send(self, request, **kw):
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["api_key"] = request.headers.get("X-BB-API-Key")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "statusCode": 200,
                    "headers": {},
                    "content": "<html><body><h1>Hello</h1><p>$12.50 / 5 g</p></body></html>",
                }
            ).encode(),
            request=request,
        )

    monkeypatch.setattr(httpx.Client, "send", mock_send)

    c = BrowserbaseClient()
    md = c.fetch_markdown("https://www.sigmaaldrich.com/US/en/product/aldrich/202630")
    assert md is not None and "$12.50" in md
    assert captured["method"] == "POST"
    assert captured["api_key"] == "test-key"
    assert isinstance(captured["body"], dict)
    assert captured["body"]["url"].startswith("https://www.sigmaaldrich.com/")
    assert "browserbase.com" in str(captured["url"])


def test_client_returns_none_on_non_200(monkeypatch) -> None:
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")

    def mock_send(self, request, **kw):
        return httpx.Response(503, request=request)

    monkeypatch.setattr(httpx.Client, "send", mock_send)
    c = BrowserbaseClient()
    assert c.fetch_markdown("https://example.com/x") is None


def test_client_returns_none_on_upstream_non_2xx(monkeypatch) -> None:
    """Browserbase returns 200 with statusCode=404 — the upstream page was missing."""
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")

    def mock_send(self, request, **kw):
        return httpx.Response(
            200,
            content=json.dumps(
                {"statusCode": 404, "headers": {}, "content": "<html>Not Found</html>"}
            ).encode(),
            request=request,
        )

    monkeypatch.setattr(httpx.Client, "send", mock_send)
    assert BrowserbaseClient().fetch_markdown("https://example.com/x") is None


def test_client_returns_none_on_empty_content(monkeypatch) -> None:
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")

    def mock_send(self, request, **kw):
        return httpx.Response(
            200,
            content=json.dumps({"statusCode": 200, "headers": {}, "content": ""}).encode(),
            request=request,
        )

    monkeypatch.setattr(httpx.Client, "send", mock_send)
    assert BrowserbaseClient().fetch_markdown("https://example.com/x") is None


@pytest.mark.live
def test_client_live_fetch_smoke() -> None:
    """Hits real Browserbase Fetch API. Requires BROWSERBASE_API_KEY in env."""
    if not os.environ.get("BROWSERBASE_API_KEY"):
        pytest.skip("BROWSERBASE_API_KEY not set")
    c = BrowserbaseClient()
    md = c.fetch_markdown("https://example.com/")
    # Either we got rendered markdown back, or the API briefly errored —
    # both are acceptable outcomes; the point is no exception escapes.
    assert md is None or isinstance(md, str)
