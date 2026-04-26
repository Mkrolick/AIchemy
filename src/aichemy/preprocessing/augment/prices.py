"""Federated price lookup for chemical molecules.

This module exposes a pluggable `PriceLookup` protocol and several
implementations: a stub (for tests and default), a SQLite-backed cache
decorator, a chain that falls back across sources, a PubChem client
(free public API), and a configurable web-scraper base class.

Scraping is OFF by default. The default `backend="stub"` never touches
the network; the default `chain=["pubchem"]` only enables PubChem when
`backend="chained"` is explicitly selected, and even then PubChem does
not produce prices (it populates `vendor_urls` for downstream use).
Real price scraping requires both `backend="chained"` AND
`prices.scraper.enabled=True` AND a vendor listed in
`prices.scraper.vendors[*].enabled=True`.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx
import polars as pl

from aichemy.config import PreprocessingConfig, ScraperVendorConfig

log = logging.getLogger(__name__)


# ---------- Protocols -------------------------------------------------------


class PriceLookup(Protocol):
    """A source that maps a canonical SMILES string to a per-gram USD price."""

    def lookup(self, smiles: str) -> float | None: ...


@dataclass
class VendorLink:
    """A discovered vendor URL for a given molecule (no price attached)."""

    vendor: str
    url: str


class VendorDiscovery(Protocol):
    """A source that maps a canonical SMILES string to a list of vendor URLs."""

    def find_vendors(self, smiles: str) -> list[VendorLink]: ...


# ---------- Stub (default, for tests and offline use) -----------------------


class StubPriceLookup:
    """In-memory PriceLookup for tests and early-dev workflows."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices = prices or {}

    def lookup(self, smiles: str) -> float | None:
        return self._prices.get(smiles)


# ---------- Chain (fallback across sources) ---------------------------------


class ChainedPriceLookup:
    """Try each inner lookup in order; return first non-None result."""

    def __init__(self, lookups: Iterable[PriceLookup]) -> None:
        self._lookups = list(lookups)

    def lookup(self, smiles: str) -> float | None:
        for inner in self._lookups:
            try:
                result = inner.lookup(smiles)
            except Exception as exc:  # one source failing shouldn't kill the chain
                log.warning("Price lookup backend %r raised: %s", type(inner).__name__, exc)
                continue
            if result is not None:
                return result
        return None


# ---------- Persistent cache ------------------------------------------------


class CachedPriceLookup:
    """Persistent SQLite cache wrapping an inner PriceLookup.

    Caches both hits and misses (None) so we don't re-query for known-unknown
    SMILES. Respects a TTL in days; past the TTL a fresh lookup is forced.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS prices (
            smiles TEXT PRIMARY KEY,
            price REAL,
            fetched_at TEXT NOT NULL
        )
    """

    def __init__(
        self,
        inner: PriceLookup,
        cache_path: Path,
        ttl_days: int = 30,
    ) -> None:
        self._inner = inner
        self._cache_path = cache_path
        self._ttl = timedelta(days=ttl_days)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(cache_path))
        self._conn.execute(self._SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def lookup(self, smiles: str) -> float | None:
        now = datetime.now(UTC)
        cur = self._conn.execute("SELECT price, fetched_at FROM prices WHERE smiles = ?", (smiles,))
        row = cur.fetchone()
        if row is not None:
            price, fetched_at_iso = row
            fetched_at = datetime.fromisoformat(fetched_at_iso)
            if now - fetched_at < self._ttl:
                # May be None (cached miss); price column is REAL NULL.
                return float(price) if price is not None else None

        result = self._inner.lookup(smiles)
        self._conn.execute(
            "INSERT OR REPLACE INTO prices (smiles, price, fetched_at) VALUES (?, ?, ?)",
            (smiles, result, now.isoformat()),
        )
        self._conn.commit()
        return result


# ---------- PubChem client (free public API; vendor discovery) --------------


class PubChemClient:
    """Discovery client against NCBI PubChem's free REST API.

    PubChem does not expose per-gram prices directly, but maps SMILES → CID
    and surfaces vendor cross-references. This client is a `VendorDiscovery`,
    not a `PriceLookup`. It is also exposed as a `PriceLookup` that always
    returns None so it can participate in a `ChainedPriceLookup` without
    skewing prices; the benefit is population of the `vendor_urls` column.
    """

    _BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def __init__(
        self,
        client: httpx.Client | None = None,
        rate_limit_seconds: float = 0.25,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._rate_limit = rate_limit_seconds
        self._last_call: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_call = time.monotonic()

    def _cid_for_smiles(self, smiles: str) -> int | None:
        self._throttle()
        url = f"{self._BASE}/compound/smiles/{smiles}/cids/JSON"
        try:
            resp = self._client.get(url)
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        try:
            payload = resp.json()
            cids = payload["IdentifierList"]["CID"]
        except (KeyError, json.JSONDecodeError):
            return None
        return int(cids[0]) if cids else None

    def find_vendors(self, smiles: str) -> list[VendorLink]:
        cid = self._cid_for_smiles(smiles)
        if cid is None:
            return []
        self._throttle()
        url = f"{self._BASE}/compound/cid/{cid}/xrefs/SourceName/JSON"
        try:
            resp = self._client.get(url)
        except httpx.HTTPError:
            return []
        if resp.status_code != 200:
            return []
        try:
            payload = resp.json()
            sources = payload["InformationList"]["Information"][0].get("SourceName", [])
        except (KeyError, IndexError, json.JSONDecodeError):
            return []
        return [
            VendorLink(vendor=str(src), url=f"{self._BASE}/compound/cid/{cid}/xrefs/JSON")
            for src in sources
        ]

    def lookup(self, smiles: str) -> float | None:
        """PubChem does not return prices; participating in the chain is a no-op here."""
        return None


# ---------- Scraper base (opt-in; honors robots.txt) ------------------------


class ScraperBase(ABC):
    """Base class for vendor scrapers.

    Enforces robots.txt compliance, rate limiting, and exponential backoff
    on 429/503. Subclasses implement `_fetch_price(smiles)` which issues
    one HTTP request and returns a price or None.

    Scraping is OFF by default. Instantiate this class only when
    config.prices.scraper.enabled is True AND the vendor is in the
    enabled allowlist.
    """

    vendor_name: str = "base"  # override in subclass

    def __init__(
        self,
        vendor_config: ScraperVendorConfig,
        user_agent: str,
        respect_robots_txt: bool = True,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
    ) -> None:
        if not vendor_config.enabled:
            raise RuntimeError(
                f"Refusing to construct {type(self).__name__}: vendor_config.enabled is False."
            )
        self._vendor_config = vendor_config
        self._user_agent = user_agent
        self._respect_robots_txt = respect_robots_txt
        self._max_retries = max_retries
        self._backoff = backoff_base_seconds
        self._last_call: float = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=15.0,
            follow_redirects=True,
        )
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        log.warning(
            "Scraper %s is ENABLED for vendor %r. Rate limit: %.1fs. Respect robots.txt: %s.",
            type(self).__name__,
            vendor_config.name,
            vendor_config.rate_limit_seconds,
            respect_robots_txt,
        )

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._vendor_config.rate_limit_seconds:
            time.sleep(self._vendor_config.rate_limit_seconds - elapsed)
        self._last_call = time.monotonic()

    def _robots_allows(self, url: str) -> bool:
        if not self._respect_robots_txt:
            return True
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = self._robots_cache.get(parsed.netloc)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                resp = self._client.get(robots_url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    # No robots.txt or 4xx/5xx — parse empty body so robotparser
                    # treats the site as fully allowed (RFC 9309 default).
                    rp.parse([])
            except httpx.HTTPError:
                log.warning("Could not fetch robots.txt at %s; assuming disallow.", robots_url)
                return False
            self._robots_cache[parsed.netloc] = rp
        return rp.can_fetch(self._user_agent, url)

    def _get(self, url: str) -> httpx.Response | None:
        if not self._robots_allows(url):
            log.warning("robots.txt forbids %s for UA %r; skipping.", url, self._user_agent)
            return None
        for attempt in range(self._max_retries):
            self._throttle()
            try:
                resp = self._client.get(url)
            except httpx.HTTPError as exc:
                log.warning("Request error on attempt %d for %s: %s", attempt + 1, url, exc)
                time.sleep(self._backoff * (2**attempt))
                continue
            if resp.status_code in (429, 503):
                log.info(
                    "Got %d from %s; backing off (%.1fs) attempt %d/%d",
                    resp.status_code,
                    url,
                    self._backoff * (2**attempt),
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(self._backoff * (2**attempt))
                continue
            return resp
        return None

    @abstractmethod
    def _fetch_price(self, smiles: str) -> float | None:
        """Return per-gram USD price or None if unknown/unavailable."""

    def lookup(self, smiles: str) -> float | None:
        try:
            return self._fetch_price(smiles)
        except Exception as exc:
            log.warning("Scraper %s failed on %s: %s", type(self).__name__, smiles, exc)
            return None


# ---------- Factory ---------------------------------------------------------


_LOOKUP_REGISTRY: dict[str, type] = {
    "pubchem": PubChemClient,
}


def make_lookup(config: PreprocessingConfig) -> PriceLookup:
    """Build a PriceLookup stack from config.

    - backend="stub" → StubPriceLookup
    - backend="chained" → CachedPriceLookup(ChainedPriceLookup(...))
      built from the `chain` list, honoring scraper enablement flags.
    - backend="aichemy_pricing" → standalone aichemy_pricing package via
      _InchikeyAdapter (SMILES → InChIKey → resolver → chain → USD/g).
    """
    cfg = config.prices

    if cfg.backend == "stub":
        return StubPriceLookup()

    if cfg.backend == "aichemy_pricing":
        from aichemy_pricing import (
            LookupByInchikey,
            PubChemSdfResolver,
            build_default_chain,
        )

        catalog_dir = Path(cfg.aichemy_pricing.catalog_dir)
        cache_path = Path(cfg.aichemy_pricing.cache_path)
        sdf_files = sorted(
            list(catalog_dir.glob("*.sdf")) + list(catalog_dir.glob("*.sdf.gz"))
        )
        if not sdf_files:
            log.warning(
                "aichemy_pricing backend selected but no SDFs found under %s; "
                "falling back to StubPriceLookup",
                catalog_dir,
            )
            return StubPriceLookup()
        resolver = PubChemSdfResolver.from_files(sdf_files)
        chain = build_default_chain(cache_path=cache_path)
        return _InchikeyAdapter(LookupByInchikey(resolver=resolver, chain=chain))

    lookups: list[PriceLookup] = []
    for name in cfg.chain:
        if name == "curated":
            from aichemy.preprocessing.augment.prices_curated import (
                CuratedPriceLookup,
            )

            lookups.append(CuratedPriceLookup())
        elif name == "pubchem":
            if cfg.pubchem.enabled:
                lookups.append(
                    PubChemClient(
                        rate_limit_seconds=cfg.pubchem.rate_limit_seconds,
                        timeout_seconds=cfg.pubchem.timeout_seconds,
                    )
                )
        elif name == "scraper":
            if cfg.scraper.enabled:
                for vendor in cfg.scraper.vendors:
                    if vendor.enabled:
                        scraper_cls = _LOOKUP_REGISTRY.get(f"scraper:{vendor.name}")
                        if scraper_cls is None:
                            log.warning(
                                "No scraper registered for vendor %r; skipping.", vendor.name
                            )
                            continue
                        lookups.append(
                            scraper_cls(
                                vendor_config=vendor,
                                user_agent=cfg.scraper.user_agent,
                                respect_robots_txt=cfg.scraper.respect_robots_txt,
                                max_retries=cfg.scraper.max_retries,
                                backoff_base_seconds=cfg.scraper.backoff_base_seconds,
                            )
                        )
        else:
            log.warning("Unknown price lookup name in chain: %r; skipping.", name)

    chain = ChainedPriceLookup(lookups)
    return CachedPriceLookup(chain, cfg.cache_path, ttl_days=cfg.cache_ttl_days)


def register_scraper(vendor_name: str, scraper_cls: type) -> None:
    """Register a concrete `ScraperBase` subclass under a vendor name.

    Call this at import time in vendor-specific submodules so `make_lookup`
    can instantiate them when enabled in config.
    """
    _LOOKUP_REGISTRY[f"scraper:{vendor_name}"] = scraper_cls


# ---------- Stage orchestrator ---------------------------------------------


def augment_prices(
    molecules: pl.DataFrame,
    lookup: PriceLookup,
) -> pl.DataFrame:
    """Populate `price_per_gram` on a molecules DataFrame via the lookup.

    Iterates unique SMILES to avoid repeat lookups (the cache decorator
    would absorb the cost anyway, but this is cheaper still). Missing
    prices remain None — the downstream MILP can still run with partial
    pricing.
    """
    if "canonical_smiles" not in molecules.columns:
        raise ValueError("augment_prices requires a 'canonical_smiles' column")

    unique_smiles: list[str] = molecules.get_column("canonical_smiles").unique().to_list()
    prices: dict[str, float | None] = {s: lookup.lookup(s) for s in unique_smiles}

    return molecules.with_columns(
        pl.col("canonical_smiles")
        .map_elements(lambda s: prices.get(s), return_dtype=pl.Float64)
        .alias("price_per_gram"),
    )


# ---------- aichemy_pricing adapter -----------------------------------------
#
# Bridges the standalone aichemy_pricing package (InChIKey -> PriceQuote with
# native currency + pack size) onto AIchemy's PriceLookup protocol (SMILES ->
# USD/g float). Static FX table; refresh quarterly or wire a live FX feed.

import datetime as _dt  # local alias to avoid leaking 'date' into the module ns

_FX_AS_OF: _dt.date = _dt.date(2026, 4, 25)
_FX_MAX_AGE = _dt.timedelta(days=120)

# USD per 1 unit of the foreign currency. Source: ECB reference rates on
# _FX_AS_OF. MUST cover every member of `aichemy_pricing.types.Currency` —
# the integration test asserts coverage via typing.get_args(Currency).
_FX_TO_USD_AS_OF_2026_04_25: dict[str, float] = {
    "USD": 1.000,
    "GBP": 1.330,    # 1 GBP = 1.33 USD
    "EUR": 1.090,    # 1 EUR = 1.09 USD
    "CNY": 0.138,    # 1 CNY = 0.138 USD
    "JPY": 0.0064,   # 1 JPY = 0.0064 USD
    "SEK": 0.094,    # 1 SEK = 0.094 USD
}


def _check_fx_freshness() -> None:
    """Emit one warning at module-import when the FX table is older than the
    threshold. Without this, prices silently compound drift over months —
    CNY in particular moves 5–10% intra-year. The 30-day cache TTL means a
    stale rate is reused for every quote captured during the cache window."""
    age = _dt.date.today() - _FX_AS_OF
    if age > _FX_MAX_AGE:
        log.warning(
            "aichemy_pricing FX table is %d days old (as-of %s, max-age %d "
            "days). Refresh ECB reference rates and bump _FX_AS_OF, or wire "
            "a live FX feed.",
            age.days,
            _FX_AS_OF.isoformat(),
            _FX_MAX_AGE.days,
        )


_check_fx_freshness()


class _InchikeyAdapter:
    """Wrap an `aichemy_pricing.LookupByInchikey` so it satisfies AIchemy's
    PriceLookup protocol (SMILES -> USD/g float).

    Per call:
      1. SMILES -> InChIKey via RDKit (lazy import; only when this backend
         is selected).
      2. Delegate to LookupByInchikey -> PriceQuote | None.
      3. Convert price_per_gram_native -> USD via static FX table.
      4. Return float, or None on any miss.
    """

    def __init__(
        self,
        inner: object,  # aichemy_pricing.LookupByInchikey — typed loosely so
                        # this module imports cleanly without the pricing extra.
        fx_to_usd: dict[str, float] | None = None,
    ) -> None:
        self._inner = inner
        self._fx = fx_to_usd or _FX_TO_USD_AS_OF_2026_04_25

    def lookup(self, smiles: str) -> float | None:
        from rdkit import Chem  # lazy import (only when this backend is used)

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        try:
            inchikey = Chem.MolToInchiKey(mol)
        except Exception as exc:  # InChI lib raises on radicals / odd valences
            log.warning("MolToInchiKey raised on %r: %s", smiles, exc)
            return None
        if not inchikey:
            return None
        quote = self._inner.lookup(inchikey)  # type: ignore[attr-defined]
        if quote is None:
            return None
        rate = self._fx.get(quote.currency)
        if rate is None:
            log.warning(
                "aichemy_pricing returned %s; no FX rate for %s — dropping quote",
                quote,
                quote.currency,
            )
            return None
        return quote.price_per_gram_native * rate
