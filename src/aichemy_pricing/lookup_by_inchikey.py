"""Adapters that compose a VendorResolver with a PriceLookup.

`LookupByInchikey` (legacy) routes every ResolverHit through a single chain
PriceLookup that internally tries each vendor in sequence. This was fine when
a SKU's vendor was unknown, but the resolver index already records the
authoritative DSN per hit — fanning out across every chain member just burns
HTTP calls on backends that won't recognise the SKU. At full corpus scale the
fan-out dominated wall-clock (especially the L3 Browserbase Browser API, ~10s
per call when it short-circuited).

`DirectDispatchInchikeyLookup` consumes a `dict[DSN -> PriceLookup]` instead.
Each ResolverHit dispatches to exactly one backend selected by its DSN, so a
hit for `vendor=29665` (Fluorochem) only calls the Fluorochem backend; an
Enamine hit (`vendor=822`) only calls the Browserbase Browser API; etc. Hits
with no mapping (Sigma-Aldrich, Cayman, Tocris) are skipped — those parsers
are absent or broken anyway.

`build_default_dispatch` (in `aichemy_pricing.__init__`) is the canonical
factory for the dispatch map.
"""

from __future__ import annotations

import logging as _logging
from dataclasses import dataclass

from aichemy_pricing.protocol import PriceLookup, VendorResolver
from aichemy_pricing.types import PriceQuote, VendorRef


@dataclass
class LookupByInchikey:
    resolver: VendorResolver
    chain: PriceLookup

    def lookup(self, inchikey: str) -> PriceQuote | None:
        for hit in self.resolver.resolve(inchikey):
            ref = VendorRef(vendor=hit.vendor, sku=hit.sku, canonical_url=hit.canonical_url)
            quote = self.chain.lookup(ref)
            if quote is not None:
                return quote
        return None


@dataclass
class VendorRewriter:
    """Wrap a PriceLookup, rewriting `ref.vendor` to a fixed parser name.

    Resolver hits carry the PubChem DSN (e.g. "25659"), but L3 Browserbase
    lookups gate on parser-registry keys (e.g. "chemcruz"). The rewriter
    bakes the parser name in so the dispatch map can pass DSNs through and
    have the backend see what its parser expects.
    """

    parser_vendor: str
    inner: PriceLookup

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        return self.inner.lookup(
            VendorRef(
                vendor=self.parser_vendor,
                sku=ref.sku,
                canonical_url=ref.canonical_url,
            )
        )


@dataclass
class DirectDispatchInchikeyLookup:
    resolver: VendorResolver
    dispatch: dict[str, PriceLookup]

    def lookup(self, inchikey: str) -> PriceQuote | None:
        log = _logging.getLogger(__name__)
        for hit in self.resolver.resolve(inchikey):
            backend = self.dispatch.get(hit.vendor)
            if backend is None:
                continue
            ref = VendorRef(vendor=hit.vendor, sku=hit.sku, canonical_url=hit.canonical_url)
            try:
                quote = backend.lookup(ref)
            except Exception as exc:
                # Mirrors ChainedPriceLookup's swallow-and-log: one parser bug
                # shouldn't abort the whole InChIKey -> drop to next hit.
                log.warning(
                    "Direct dispatch backend raised on %s/%s: %s",
                    hit.vendor,
                    hit.sku,
                    exc,
                )
                continue
            if quote is not None:
                return quote
        return None
