"""Browserbase Browser API session lifecycle helper.

Browserbase Fetch (client.py) does not execute JavaScript, so SPA vendors
(Enamine, Cayman, Sigma, Tocris) return their unhydrated shell. Browser
API spins up a real Chrome session that we drive with Playwright over CDP.

Cost: per-minute billing at ~$0.10/hour. A typical lookup is ~10s of
session time. The context manager guarantees `session.close()` runs even
when the page raises — a leaked session keeps billing.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

log = logging.getLogger(__name__)


@contextlib.contextmanager
def browser_session(
    api_key: str | None = None,
    project_id: str | None = None,
    nav_timeout_ms: int = 30_000,
) -> Iterator[Page | None]:
    """Yield a Playwright Page connected to a one-shot Browserbase Chrome session.

    Caller drives the page (navigate, wait, extract). Cleanup — page close,
    context close, browser disconnect, Browserbase session close — runs in
    a finally block whether or not the body raised.

    Yields None when BROWSERBASE_API_KEY is unset; callers must treat that
    as "Browser API unavailable, skip vendor".
    """
    key = api_key or os.environ.get("BROWSERBASE_API_KEY")
    if not key:
        log.debug("browser_session: BROWSERBASE_API_KEY unset; yielding None")
        yield None
        return

    from browserbase import Browserbase
    from playwright.sync_api import sync_playwright

    bb = Browserbase(api_key=key)
    pid = project_id or _default_project_id(bb)
    session = bb.sessions.create(project_id=pid)

    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(session.connect_url)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_navigation_timeout(nav_timeout_ms)
        yield page
    finally:
        with contextlib.suppress(Exception):
            if browser is not None:
                browser.close()
        with contextlib.suppress(Exception):
            if pw is not None:
                pw.stop()
        with contextlib.suppress(Exception):
            bb.sessions.update(
                id=session.id,
                project_id=pid,
                status="REQUEST_RELEASE",
            )


def _default_project_id(bb: object) -> str:
    """Return the first project's id — Browserbase accounts have a default project."""
    projects = bb.projects.list()  # type: ignore[attr-defined]
    if not projects:
        raise RuntimeError("Browserbase account has no projects")
    return str(projects[0].id)
