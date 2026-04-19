"""Base class for chemical-price web scrapers.

Enforces the discipline that every vendor integration must honor:
- robots.txt respect (per-domain cached)
- configurable User-Agent with contact email
- per-domain rate limiting (not just per-scraper, so multiple scrapers
  hitting the same domain still cooperate)
- exponential backoff on 429/503/transient errors
- source-URL provenance on every returned price
- graceful None return on any failure (never crash the pipeline)
"""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

# Global per-domain last-call registry so multiple scrapers targeting the
# same host cooperate on rate limiting.
_LAST_CALL_PER_DOMAIN: dict[str, float] = {}
_LAST_CALL_LOCK = Lock()


@dataclass
class PriceQuote:
    """A single scraped price with full provenance.

    Every field must be populated so downstream consumers can audit where
    the number came from and how old it is.
    """

    smiles: str
    price_per_gram_usd: float
    vendor: str
    source_url: str
    fetched_at: datetime
    # Optional metadata the vendor page provided (catalog number, size, etc.)
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "smiles": self.smiles,
            "price_per_gram_usd": self.price_per_gram_usd,
            "vendor": self.vendor,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at.isoformat(),
            "extra": dict(self.extra),
        }


class PriceScraperBase(ABC):
    """Abstract base for all price scrapers.

    Subclasses must implement:
        - ``vendor_name`` (class attr)
        - ``_fetch_quote(smiles)`` — perform the vendor-specific lookup
          and return a ``PriceQuote`` or ``None``.

    The base class handles robots.txt, rate limiting, backoff, and converts
    all exceptions into ``None`` so a single flaky vendor can't crash a
    batch job.
    """

    vendor_name: str = "base"

    def __init__(
        self,
        user_agent: str,
        rate_limit_seconds: float = 3.0,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
        respect_robots_txt: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        if not user_agent:
            raise ValueError("user_agent is required (include a contact email)")
        self._user_agent = user_agent
        self._rate_limit = rate_limit_seconds
        self._max_retries = max_retries
        self._backoff = backoff_base_seconds
        self._respect_robots_txt = respect_robots_txt
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Rate limit (per-domain, globally)
    # ------------------------------------------------------------------
    def _throttle(self, url: str) -> None:
        domain = urlparse(url).netloc
        with _LAST_CALL_LOCK:
            last = _LAST_CALL_PER_DOMAIN.get(domain, 0.0)
            now = time.monotonic()
            elapsed = now - last
            wait = self._rate_limit - elapsed if elapsed < self._rate_limit else 0.0
            _LAST_CALL_PER_DOMAIN[domain] = now + wait
        if wait > 0:
            time.sleep(wait)

    # ------------------------------------------------------------------
    # robots.txt
    # ------------------------------------------------------------------
    def _robots_allows(self, url: str) -> bool:
        if not self._respect_robots_txt:
            return True
        parsed = urlparse(url)
        netloc = parsed.netloc
        robots_url = f"{parsed.scheme}://{netloc}/robots.txt"
        rp = self._robots_cache.get(netloc)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                resp = self._client.get(robots_url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp.parse([])  # empty robots = allow-all per RFC 9309
            except httpx.HTTPError:
                log.warning(
                    "%s: could not fetch robots.txt at %s; assuming disallow.",
                    self.vendor_name,
                    robots_url,
                )
                return False
            self._robots_cache[netloc] = rp
        return rp.can_fetch(self._user_agent, url)

    # ------------------------------------------------------------------
    # HTTP with retries + backoff
    # ------------------------------------------------------------------
    def _get(self, url: str, **kwargs: Any) -> httpx.Response | None:
        if not self._robots_allows(url):
            log.warning(
                "%s: robots.txt forbids %s for UA %r.",
                self.vendor_name,
                url,
                self._user_agent,
            )
            return None
        for attempt in range(self._max_retries):
            self._throttle(url)
            try:
                resp = self._client.get(url, **kwargs)
            except httpx.HTTPError as exc:
                log.warning(
                    "%s: request error on attempt %d for %s: %s",
                    self.vendor_name,
                    attempt + 1,
                    url,
                    exc,
                )
                time.sleep(self._backoff * (2**attempt))
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = self._backoff * (2**attempt)
                log.info(
                    "%s: got %d from %s; backing off %.1fs (attempt %d/%d).",
                    self.vendor_name,
                    resp.status_code,
                    url,
                    wait,
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(wait)
                continue
            return resp
        log.warning(
            "%s: exhausted %d retries for %s.",
            self.vendor_name,
            self._max_retries,
            url,
        )
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, smiles: str) -> PriceQuote | None:
        """Fetch a price quote for a SMILES; return None on any failure."""
        if not smiles:
            return None
        try:
            quote = self._fetch_quote(smiles)
        except Exception as exc:
            log.warning(
                "%s: unexpected failure on %s: %s",
                self.vendor_name,
                smiles,
                exc,
            )
            return None
        if quote is None:
            return None
        # Stamp the fetched_at if the subclass didn't set one.
        if not quote.fetched_at:
            quote.fetched_at = datetime.now(UTC)
        return quote

    @abstractmethod
    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        """Vendor-specific lookup. Must not raise — return None on failure."""
