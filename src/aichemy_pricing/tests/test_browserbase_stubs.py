"""Lock the Browser API + LLM extraction modules as STUBS.

These tests prevent the stubs from accidentally shipping as half-working
implementations. If you intentionally implement either of these in a
future revision, update or remove the test (don't keep a fake-passing
stub assertion in place).
"""

from __future__ import annotations

import pytest

from aichemy_pricing.browserbase.browser_api import BrowserbaseBrowserLookup
from aichemy_pricing.browserbase.llm_extract import BrowserbaseLLMLookup


def test_browser_api_constructor_raises_with_helpful_message() -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        BrowserbaseBrowserLookup()
    msg = str(exc_info.value)
    # Must point the future-implementer at when to swap the stub for a
    # real impl — not just say "TODO".
    assert "Fetch API" in msg or "multi-step" in msg


def test_llm_extract_constructor_raises_with_helpful_message() -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        BrowserbaseLLMLookup()
    msg = str(exc_info.value)
    assert "deterministic" in msg or "free" in msg
