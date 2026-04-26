"""aichemy-pricing — chemical-vendor price resolution.

Standalone package: zero imports from `aichemy.*`. Installable + testable
on its own (`uv sync --extra pricing`; `pytest src/aichemy_pricing/tests/`).

Public API:
    PriceQuote, VendorRef, ResolverHit, Currency  # types
    PriceLookup, VendorResolver                   # protocols
    ChainedPriceLookup, CachedPriceLookup         # composition
    TokenBucket                                   # rate limit primitive
    make_plain_client, make_cf_client             # HTTP factories
    PubChemSdfResolver, EnamineSdfResolver,
        ZincTrancheResolver                       # offline resolvers
    FluorochemVendor, MolbaseVendor, TocrisVendor,
        MedChemExpressVendor                      # direct-HTTP vendors
    BrowserbaseFetchLookup, BrowserbaseBrowserLookup  # L3 (SSR + SPA)
    LookupByInchikey                              # resolver -> chain adapter
    build_default_chain(cache_path)               # opinionated factory

Excluded by design:
 - Apollo Scientific (CLAIM-11 — FALSIFIED)
 - Sigma-Aldrich, TCI Chemicals (Akamai requires residential proxies)
 - BLDpharm (CLAIM-16 — URL pattern not yet discovered)

Enamine, Cayman Chemical, Santa Cruz / ChemCruz, and Sigma are reachable
via the Browserbase L3 layer (Fetch for SSR, Browser API for SPAs); they
are not standalone vendor classes.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aichemy_pricing._version import __version__
from aichemy_pricing.browserbase import (
    BrowserbaseBrowserLookup,
    BrowserbaseFetchLookup,
)
from aichemy_pricing.chain import CachedPriceLookup, ChainedPriceLookup
from aichemy_pricing.http import make_cf_client, make_plain_client
from aichemy_pricing.lookup_by_inchikey import LookupByInchikey
from aichemy_pricing.protocol import PriceLookup, VendorResolver
from aichemy_pricing.ratelimit import TokenBucket
from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver
from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver
from aichemy_pricing.resolvers.zinc_tranches import ZincTrancheResolver
from aichemy_pricing.types import Currency, PriceQuote, ResolverHit, VendorRef
from aichemy_pricing.vendors.fluorochem import FluorochemVendor
from aichemy_pricing.vendors.medchemexpress import MedChemExpressVendor
from aichemy_pricing.vendors.molbase import MolbaseVendor
from aichemy_pricing.vendors.tocris import TocrisVendor

__all__ = [
    "_DEFAULT_VENDOR_CLASSES",  # mutable for tests; underscore = unstable
    "BrowserbaseBrowserLookup",
    "BrowserbaseFetchLookup",
    "CachedPriceLookup",
    "ChainedPriceLookup",
    "Currency",
    "EnamineSdfResolver",
    "FluorochemVendor",
    "LookupByInchikey",
    "MedChemExpressVendor",
    "MolbaseVendor",
    "PriceLookup",
    "PriceQuote",
    "PubChemSdfResolver",
    "ResolverHit",
    "TocrisVendor",
    "TokenBucket",
    "VendorRef",
    "VendorResolver",
    "ZincTrancheResolver",
    "__version__",
    "build_default_chain",
    "make_cf_client",
    "make_plain_client",
]


# Direct-HTTP vendor classes only. Enamine/Cayman/ChemCruz/Sigma reach the
# chain through the L3 Browserbase layers appended below.
_DEFAULT_VENDOR_CLASSES: list[type] = [
    FluorochemVendor,  # L1 — Azure-blob JSON, no auth
    TocrisVendor,  # L1 — SSR HTML, anonymous USD prices
    MolbaseVendor,  # L1 — SSR HTML, mostly Chinese suppliers
    MedChemExpressVendor,  # L2 — curl_cffi for Cloudflare
]


def build_default_chain(cache_path: Path | str) -> CachedPriceLookup:
    """Standard tiered vendor chain: direct-HTTP vendors first, then L3
    Browserbase layers, all wrapped in a SQLite cache.

    Order rationale: cheapest things fire first. L1 plain HTTPS (~100ms);
    L2 curl_cffi for Cloudflare (~1s); L3a Browserbase Fetch ($0.001/call,
    SSR-only); L3b Browserbase Browser API ($0.0003/call but ~10s of
    session time, JS-rendered SPAs).

    Placeholder-aware construction (Revision 16): if any vendor's
    __init__ raises NotImplementedError (used today as a fail-loud signal
    that an out-of-band discovery step is unfinished), we log a warning
    and skip that vendor instead of aborting the whole chain. The L3
    Browserbase lookups are appended unconditionally — both no-op when
    BROWSERBASE_API_KEY is unset, so they're always safe to include.
    """
    log = logging.getLogger(__name__)
    members: list[PriceLookup] = []
    for cls in _DEFAULT_VENDOR_CLASSES:
        try:
            members.append(cls())
        except NotImplementedError as exc:
            log.warning("build_default_chain: skipping %s — %s", cls.__name__, exc)
    # L3a — Browserbase Fetch (SSR HTML; chemcruz parser registered today).
    members.append(BrowserbaseFetchLookup())
    # L3b — Browserbase Browser API (JS-rendered SPAs; enamine registered today).
    members.append(BrowserbaseBrowserLookup())
    return CachedPriceLookup(ChainedPriceLookup(members), db_path=cache_path, ttl_days=30)
