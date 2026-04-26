"""Lock the LLM extraction module as a STUB.

This test prevents the LLM stub from accidentally shipping as a
half-working implementation. If you intentionally implement it in a
future revision, update or remove the test (don't keep a fake-passing
stub assertion in place).

(BrowserbaseBrowserLookup was a stub in sub-plan F and is now real —
its tests live in test_browserbase_browser_lookup.py.)
"""

from __future__ import annotations

import pytest

from aichemy_pricing.browserbase.llm_extract import BrowserbaseLLMLookup


def test_llm_extract_constructor_raises_with_helpful_message() -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        BrowserbaseLLMLookup()
    msg = str(exc_info.value)
    assert "deterministic" in msg or "free" in msg
