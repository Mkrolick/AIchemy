"""Standalone test suite for aichemy_pricing.

Runs without aichemy.* imports.

Live network tests are marked with @pytest.mark.live and skipped by default.
Run live-only with:  pytest src/aichemy_pricing/tests -m live
"""

from __future__ import annotations

import pathlib
import re

import pytest

DATA = pathlib.Path(__file__).parent / "data"

# `-m live` (or `-m "live or X"`) opts the user IN to live tests.
# `-m "not live"` (or default no `-m`) opts them OUT.
# The negative-lookbehind regex requires the literal 4 chars "not " before "live"
# to recognize the OPT-OUT case — but pytest accepts equivalent forms like
# "not (live)", "not(live)", or "not  live" (double space) that defeat the
# fixed-width lookbehind. We normalize the markexpr first: strip parentheses
# and collapse whitespace, so all of those canonicalize to "not live" before
# the regex runs and route correctly through the lookbehind.
_LIVE_OPT_IN = re.compile(r"(?<!not )\blive\b")


def _normalize_markexpr(raw: str) -> str:
    # Replace parens with spaces; pytest's marker grammar uses parens only for
    # grouping, never as part of a marker name, so this is safe.
    no_parens = raw.replace("(", " ").replace(")", " ")
    # Collapse runs of whitespace to a single space.
    return re.sub(r"\s+", " ", no_parens).strip()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: hits real network; skipped by default")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    markexpr = _normalize_markexpr(config.option.markexpr or "")
    if _LIVE_OPT_IN.search(markexpr):
        return  # caller asked for live; don't filter
    skip_live = pytest.mark.skip(reason="live network test; pass -m live to enable")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def fixture_dir() -> pathlib.Path:
    return DATA
