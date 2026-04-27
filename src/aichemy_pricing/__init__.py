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
from aichemy_pricing.lookup_by_inchikey import (
    DirectDispatchInchikeyLookup,
    LookupByInchikey,
    VendorRewriter,
)
from aichemy_pricing.protocol import PriceLookup, VendorResolver
from aichemy_pricing.ratelimit import TokenBucket
from aichemy_pricing.resolvers.chained import ChainedVendorResolver
from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver
from aichemy_pricing.resolvers.pubchem_compound import PubChemCompoundResolver
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
    "ChainedVendorResolver",
    "Currency",
    "DirectDispatchInchikeyLookup",
    "EnamineSdfResolver",
    "FluorochemVendor",
    "LookupByInchikey",
    "MedChemExpressVendor",
    "MolbaseVendor",
    "PriceLookup",
    "PriceQuote",
    "PubChemCompoundResolver",
    "PubChemSdfResolver",
    "ResolverHit",
    "TocrisVendor",
    "TokenBucket",
    "VendorRef",
    "VendorResolver",
    "VendorRewriter",
    "ZincTrancheResolver",
    "__version__",
    "build_default_chain",
    "build_default_dispatch",
    "make_cf_client",
    "make_plain_client",
]


# Direct-HTTP vendor classes only. Enamine/Cayman/ChemCruz/Sigma reach the
# chain through the L3 Browserbase layers appended below.
#
# TocrisVendor is intentionally excluded: Tocris restructured their product
# HTML and the Pack-Size / List-Price markers the parser keys on are gone.
# Under load every lookup runs out the connection timeout, which dominated
# wall-clock for the 2026-04 validation cycle. Re-add once the parser is
# rebuilt against the current page layout (see findings doc 2026-04-26).
_DEFAULT_VENDOR_CLASSES: list[type] = [
    FluorochemVendor,  # L1 — Azure-blob JSON, no auth
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
    # L3b — Browserbase Browser API: disabled. Each fall-through ate ~10s of
    # session-setup time, which dominated wall-clock at scale even when its
    # parsers (enamine) didn't fire. Re-enable when there is a per-vendor
    # gate so non-enamine refs short-circuit before reaching it.
    return CachedPriceLookup(ChainedPriceLookup(members), db_path=cache_path, ttl_days=30)


# DSN -> (parser_vendor, backend_factory) for direct dispatch.
#   - DSN is the literal string in `PUBCHEM_EXT_DATASOURCE_NAME` and the
#     `vendor` field on ResolverHits coming out of PubChemCompoundResolver.
#   - parser_vendor is what the backend's parser registry / class expects
#     to see in `ref.vendor`. It only differs from DSN for L3 backends
#     (BrowserbaseFetchLookup keys on "chemcruz" not "25659";
#     BrowserbaseBrowserLookup keys on "enamine" not "822").
#
# Sigma-Aldrich, Cayman ("843"), and Tocris ("10600") are deliberately
# absent — their parsers either don't exist or are broken (Tocris HTML
# restructure). Hits at those DSNs never produced quotes in the chain
# fan-out either; skipping them is faithful to actual coverage and avoids
# wasted HTTP work.
_DEFAULT_DISPATCH_TABLE: dict[str, tuple[str, type]] = {
    "29665": ("fluorochem", FluorochemVendor),  # Fluorochem L1
    "959": ("medchemexpress", MedChemExpressVendor),  # MedChem L2
    "25659": ("chemcruz", BrowserbaseFetchLookup),  # Santa Cruz L3a
    "822": ("enamine", BrowserbaseBrowserLookup),  # Enamine L3b
}


def build_default_dispatch(cache_path: Path | str) -> dict[str, PriceLookup]:
    """DSN-keyed dispatch map for `DirectDispatchInchikeyLookup`.

    Each entry wraps a single backend in `VendorRewriter` (so the parser
    sees its registered vendor name) and `CachedPriceLookup` (shared SQLite
    file at `cache_path`; cache key is the original DSN+SKU so cross-DSN
    lookups don't collide).
    """
    log = logging.getLogger(__name__)
    out: dict[str, PriceLookup] = {}
    for dsn, (parser_vendor, cls) in _DEFAULT_DISPATCH_TABLE.items():
        try:
            backend = cls()
        except NotImplementedError as exc:
            log.warning("build_default_dispatch: skipping %s — %s", cls.__name__, exc)
            continue
        rewritten = VendorRewriter(parser_vendor=parser_vendor, inner=backend)
        out[dsn] = CachedPriceLookup(rewritten, db_path=cache_path, ttl_days=30)
    return out
