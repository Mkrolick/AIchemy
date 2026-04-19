"""USPTO PatentsView patent search client.

USPTO's free PatentsView search API (https://search.patentsview.org/)
requires no authentication but has polite rate limits (~45 requests/min).
This client issues a keyword search and returns patent metadata.

Used as scaffolding for downstream reaction-condition extraction; actual
NLP over patent claims is out of scope here.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE = "https://search.patentsview.org/api/v1"


@dataclass
class Patent:
    patent_id: str
    title: str
    date: str | None
    abstract: str | None

    @classmethod
    def from_api(cls, row: dict[str, Any]) -> Patent:
        return cls(
            patent_id=str(row.get("patent_number") or row.get("patent_id") or ""),
            title=row.get("patent_title") or "",
            date=row.get("patent_date"),
            abstract=row.get("patent_abstract"),
        )


class PatentSearcher:
    """Search USPTO PatentsView for patents matching a query.

    ``search_by_keyword(term, max_results=50)`` returns a list of `Patent`
    objects. Rate-limited to ~1 req/sec by default to stay well under
    USPTO's limits.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        rate_limit_seconds: float = 1.0,
        timeout_seconds: float = 15.0,
        client: httpx.Client | None = None,
        user_agent: str = "AIchemy-research/0.1 (https://github.com/mkrolick/AIchemy)",
    ) -> None:
        self._base = base_url
        self._rate_limit = rate_limit_seconds
        self._last_call: float = 0.0
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_call = time.monotonic()

    def search_by_keyword(self, term: str, max_results: int = 50) -> list[Patent]:
        """Keyword search across patent titles + abstracts."""
        self._throttle()
        # PatentsView POST endpoint accepts a JSON body.
        payload = {
            "q": {
                "_or": [
                    {"_text_any": {"patent_title": term}},
                    {"_text_any": {"patent_abstract": term}},
                ]
            },
            "f": ["patent_id", "patent_title", "patent_date", "patent_abstract"],
            "o": {"size": max_results},
        }
        try:
            resp = self._client.post(f"{self._base}/patent/", json=payload)
        except httpx.HTTPError as exc:
            log.warning("PatentsView request error: %s", exc)
            return []
        if resp.status_code != 200:
            log.warning("PatentsView returned %d: %s", resp.status_code, resp.text[:200])
            return []
        data = resp.json() or {}
        rows = data.get("patents") or []
        return [Patent.from_api(row) for row in rows]
