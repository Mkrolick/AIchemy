"""Unit tests for client factories."""

from __future__ import annotations

from aichemy_pricing.http import CHROME_UA, make_cf_client, make_plain_client


def test_plain_client_uses_browser_ua() -> None:
    c = make_plain_client()
    try:
        assert c.headers["User-Agent"] == CHROME_UA
        assert "Accept" in c.headers
    finally:
        c.close()


def test_plain_client_follows_redirects() -> None:
    c = make_plain_client()
    try:
        assert c.follow_redirects is True
    finally:
        c.close()


def test_cf_client_returns_object_with_get(monkeypatch) -> None:
    """We don't actually make a network call here; just verify the factory hands
    back something with the curl_cffi.requests.Session shape."""
    c = make_cf_client()
    assert hasattr(c, "get") and callable(c.get)
