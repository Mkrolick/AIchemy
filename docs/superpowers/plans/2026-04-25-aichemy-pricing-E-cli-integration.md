# Sub-Plan E: `aichemy-pricing` — CLI, Public API, and AIchemy Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Parent plan:** `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`
> **Verification source:** `experiments/chem-pricing-verification/CLAIMS.md`
> **Depends on:** Sub-Plans A, B, C, D (consumes everything they deliver)
> **Delivers:**
> - `aichemy-price` console script with `lookup`, `chain`, and `resolve` subcommands
> - `aichemy_pricing.build_default_chain(cache_path)` factory exposing the curated tier-1+2+3 chain
> - `aichemy_pricing.LookupByInchikey` adapter that runs Resolver → Chain
> - Top-level `__init__.py` that re-exports the full public API
> - Wire-up into `aichemy.preprocessing.augment.prices` so the AIchemy pipeline can use the new package via `prices.backend = "aichemy_pricing"`
> - End-to-end verification (offline tests pass; live tests pass on demand; existing AIchemy tests don't regress)
> - README section documenting the package + CLI

**Goal:** Glue everything together. Wire the seven vendors and three resolvers into a default tiered chain; expose a CLI for single-SKU and end-to-end debugging; integrate with the AIchemy preprocessing pipeline as an optional backend; verify end-to-end.

**Architecture:** `__init__.py` re-exports the full surface. `cli.py` uses Typer and a vendor registry to dispatch. `LookupByInchikey` composes `VendorResolver` (any of the three from sub-plan B) with `PriceLookup` (the chain from `build_default_chain`) so callers can ask "give me prices for InChIKey X" and get back a list of `PriceQuote`. The AIchemy integration is a one-file edit in `aichemy.preprocessing.augment.prices` that adds a `"aichemy_pricing"` branch to the existing `make_lookup` factory.

**Tech Stack:** Python 3.11, `typer` for the CLI, all prior tech from sub-plans A–D.

---

## File Structure

```
src/aichemy_pricing/
├── __init__.py                            # MODIFY — full re-export
├── lookup_by_inchikey.py                  # CREATE — adapter (resolver → chain)
└── cli.py                                 # CREATE — Typer app

src/aichemy_pricing/tests/
├── test_lookup_by_inchikey.py             # CREATE (3 tests)
├── test_build_default_chain.py            # CREATE (2 tests)
├── test_cli.py                            # CREATE (5 tests)
└── test_integration.py                    # CREATE (2 end-to-end tests)

src/aichemy/preprocessing/augment/prices.py  # MODIFY — add `aichemy_pricing` backend branch
configs/default.yaml                         # MODIFY — document new backend in comment
README.md                                    # MODIFY — add "Vendor pricing" section
tests/integration/test_pricing_package_integration.py  # CREATE (1 e2e test)
```

---

## Task E1: `lookup_by_inchikey.py` — adapter (Resolver → Chain)

**Why:** Vendors take `VendorRef`; resolvers produce `ResolverHit`s from an InChIKey. The adapter walks (resolver → first hit → chain.lookup) so a caller with only an InChIKey can get a price.

**Files:**
- Create: `src/aichemy_pricing/lookup_by_inchikey.py`
- Create: `src/aichemy_pricing/tests/test_lookup_by_inchikey.py`

- [ ] **Step 1: Failing tests**

```python
# src/aichemy_pricing/tests/test_lookup_by_inchikey.py
"""Unit tests for LookupByInchikey adapter."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aichemy_pricing.lookup_by_inchikey import LookupByInchikey
from aichemy_pricing.types import PriceQuote, ResolverHit, VendorRef


class _StaticResolver:
    name = "static"
    def __init__(self, hits: list[ResolverHit]) -> None:
        self.hits = hits
    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return [h for h in self.hits if h.inchikey == inchikey]


class _ConditionalChain:
    """Returns a price for any ref whose vendor is in `priced_vendors`."""
    name = "chain"
    def __init__(self, priced_vendors: set[str]) -> None:
        self.priced_vendors = priced_vendors
    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        if ref.vendor in self.priced_vendors:
            return PriceQuote(
                vendor=ref.vendor, sku=ref.sku, price=1.0, currency="USD", pack_size_g=1.0,
                fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        return None


def test_lookup_returns_first_priced_vendor_per_inchikey() -> None:
    ik = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    resolver = _StaticResolver([
        ResolverHit(inchikey=ik, vendor="apollo",   sku="X"),  # apollo not priced
        ResolverHit(inchikey=ik, vendor="enamine",  sku="EN300-1"),
        ResolverHit(inchikey=ik, vendor="fluorochem", sku="F1-1G"),
    ])
    chain = _ConditionalChain({"enamine", "fluorochem"})
    out = LookupByInchikey(resolver=resolver, chain=chain).lookup(ik)
    assert out is not None
    assert out.vendor == "enamine"  # first priced hit


def test_lookup_returns_none_when_no_resolver_hits() -> None:
    resolver = _StaticResolver([])
    chain = _ConditionalChain({"enamine"})
    assert LookupByInchikey(resolver=resolver, chain=chain).lookup("BSYNRYMUTXBXSQ-UHFFFAOYSA-N") is None


def test_lookup_returns_none_when_no_chain_member_prices_any_resolver_hit() -> None:
    ik = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    resolver = _StaticResolver([ResolverHit(inchikey=ik, vendor="apollo", sku="X")])
    chain = _ConditionalChain({"enamine"})  # apollo not in chain
    assert LookupByInchikey(resolver=resolver, chain=chain).lookup(ik) is None
```

- [ ] **Step 2: Implement**

```python
# src/aichemy_pricing/lookup_by_inchikey.py
"""Adapter that composes a VendorResolver with a PriceLookup chain.

Caller asks: "give me a price for this InChIKey".
Internals:
  1. resolver.resolve(ik) → list[ResolverHit] (in vendor priority order)
  2. for each hit, ref = VendorRef(vendor=hit.vendor, sku=hit.sku, ...)
     chain.lookup(ref) → PriceQuote | None
  3. return first non-None quote, or None if all chain misses.
"""
from __future__ import annotations

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
```

- [ ] **Step 3: Run; pass (3 tests)**

- [ ] **Step 4: Commit**

```bash
git add src/aichemy_pricing/lookup_by_inchikey.py src/aichemy_pricing/tests/test_lookup_by_inchikey.py
git commit -m "feat(pricing): LookupByInchikey adapter (Resolver → Chain)"
```

---

## Task E2: `__init__.py` — full re-export + `build_default_chain`

**Files:**
- Modify: `src/aichemy_pricing/__init__.py`
- Create: `src/aichemy_pricing/tests/test_build_default_chain.py`

- [ ] **Step 1: Replace `__init__.py`**

```python
# src/aichemy_pricing/__init__.py
"""aichemy-pricing — chemical-vendor price resolution.

Standalone package: zero imports from `aichemy.*`. Installable + testable
on its own (`uv sync --extra pricing`; `pytest src/aichemy_pricing/tests/`).

Public API:
    PriceQuote, VendorRef, ResolverHit             # types
    PriceLookup, VendorResolver                    # protocols
    ChainedPriceLookup, CachedPriceLookup          # composition
    TokenBucket                                    # rate limit primitive
    make_plain_client, make_cf_client              # HTTP factories
    PubChemSdfResolver, EnamineSdfResolver,        # offline resolvers
        ZincTrancheResolver
    FluorochemVendor, MolbaseVendor, TocrisVendor, # Tier 1 (plain HTTP)
    EnamineVendor, CaymanVendor, ChemCruzVendor,   # Tier 2 (XHR / SSR-light-CF)
    MedChemExpressVendor                           # Tier 3 (curl_cffi)
    LookupByInchikey                               # resolver → chain adapter
    build_default_chain(cache_path)                # opinionated factory

Verification anchors: every URL/schema fact each vendor encodes is tagged
to a CLAIM-XX in `experiments/chem-pricing-verification/CLAIMS.md`.

Excluded by design:
 - Apollo Scientific (CLAIM-11 — FALSIFIED, e-commerce surface gone)
 - Sigma-Aldrich, TCI Chemicals (CLAIM-12, CLAIM-13 — Akamai requires
   residential proxies; deferred to a future Tier-4 plan)
 - BLDpharm (CLAIM-16 — URL pattern in original report is wrong; real
   pattern not yet discovered)
"""
from __future__ import annotations

from pathlib import Path

from aichemy_pricing._version import __version__
from aichemy_pricing.chain import CachedPriceLookup, ChainedPriceLookup
from aichemy_pricing.http import make_cf_client, make_plain_client
from aichemy_pricing.lookup_by_inchikey import LookupByInchikey
from aichemy_pricing.protocol import PriceLookup, VendorResolver
from aichemy_pricing.ratelimit import TokenBucket
from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver
from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver
from aichemy_pricing.resolvers.zinc_tranches import ZincTrancheResolver
from aichemy_pricing.types import Currency, PriceQuote, ResolverHit, VendorRef
from aichemy_pricing.vendors.cayman import CaymanVendor
from aichemy_pricing.vendors.chemcruz import ChemCruzVendor
from aichemy_pricing.vendors.enamine import EnamineVendor
from aichemy_pricing.vendors.fluorochem import FluorochemVendor
from aichemy_pricing.vendors.medchemexpress import MedChemExpressVendor
from aichemy_pricing.vendors.molbase import MolbaseVendor
from aichemy_pricing.vendors.tocris import TocrisVendor

__all__ = [
    "__version__",
    "Currency", "PriceQuote", "VendorRef", "ResolverHit",
    "PriceLookup", "VendorResolver",
    "ChainedPriceLookup", "CachedPriceLookup",
    "TokenBucket",
    "make_plain_client", "make_cf_client",
    "PubChemSdfResolver", "EnamineSdfResolver", "ZincTrancheResolver",
    "FluorochemVendor", "MolbaseVendor", "TocrisVendor",
    "EnamineVendor", "CaymanVendor", "ChemCruzVendor", "MedChemExpressVendor",
    "LookupByInchikey",
    "build_default_chain",
    "_DEFAULT_VENDOR_CLASSES",  # mutable for tests; not part of stable API
]


_DEFAULT_VENDOR_CLASSES: list[type] = [
    FluorochemVendor,
    MolbaseVendor,
    TocrisVendor,
    EnamineVendor,
    CaymanVendor,
    ChemCruzVendor,
    MedChemExpressVendor,
]


def build_default_chain(cache_path: Path | str) -> CachedPriceLookup:
    """Standard tiered vendor chain: Tier 1 (plain HTTP) → Tier 2 (JS-rendered
    or light-CF) → Tier 3 (Cloudflare-aware), all wrapped in a SQLite cache.

    Tier 1 first because it's cheapest and most reliable. MedChemExpress (Tier 3)
    last because curl_cffi setup has the highest baseline cost per call.

    Excludes Sigma-Aldrich, TCI, Apollo, and BLD per the verification report.

    **Placeholder-aware construction** (Revision 16): Tier-2 vendors that
    require manual DevTools discovery (Enamine `_API_URL`, Cayman `_API_URL`)
    raise `NotImplementedError` from `__init__` until a human completes the
    discovery step. We catch that here so the chain factory remains callable
    even when one or more discovery placeholders are unfilled — production
    degrades gracefully (vendor skipped + warning logged), and E2 unit tests
    can run without the out-of-band manual work.
    """
    import logging
    log = logging.getLogger(__name__)
    members: list = []
    for cls in _DEFAULT_VENDOR_CLASSES:
        try:
            members.append(cls())
        except NotImplementedError as exc:
            log.warning(
                "build_default_chain: skipping %s — %s",
                cls.__name__, exc,
            )
    return CachedPriceLookup(ChainedPriceLookup(members), db_path=cache_path, ttl_days=30)
```

- [ ] **Step 2: Failing test for `build_default_chain`**

```python
# src/aichemy_pricing/tests/test_build_default_chain.py
"""Unit tests for build_default_chain."""
from __future__ import annotations

from aichemy_pricing import (
    CachedPriceLookup, ChainedPriceLookup, build_default_chain,
)


def test_build_default_chain_returns_cached_chain(tmp_path) -> None:
    chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    assert isinstance(chain, CachedPriceLookup)
    assert isinstance(chain.inner, ChainedPriceLookup)


def test_build_default_chain_omits_apollo_sigma_tci_bld(tmp_path) -> None:
    chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    vendor_names = {m.name for m in chain.inner.members}
    excluded = {"apollo", "sigma", "sigma-aldrich", "tci", "bld", "bldpharm"}
    assert vendor_names.isdisjoint(excluded)
    # The verified-working Tier 1 vendors must always be present (no placeholder).
    # Tier-2 vendors with discovery placeholders (enamine, cayman) MAY be absent
    # if `_API_URL` hasn't been filled in yet — Revision 16 makes the chain
    # factory skip those rather than crash. The `excluded` invariant remains
    # the load-bearing check.
    assert {"fluorochem", "molbase", "tocris", "chemcruz",
            "medchemexpress"}.issubset(vendor_names)


def test_build_default_chain_skips_placeholder_vendors_gracefully(tmp_path, monkeypatch, caplog) -> None:
    """If a Tier-2/3 vendor's __init__ raises NotImplementedError (the
    placeholder guard from Revision 6), the chain factory must catch it,
    log a warning, and continue — not crash. Mirrors the production behavior
    where `augment_prices` keeps running even with one undiscovered vendor."""
    import logging
    from aichemy_pricing import build_default_chain
    from aichemy_pricing.vendors.fluorochem import FluorochemVendor

    class _Boom(FluorochemVendor):
        name = "boom"
        def __init__(self):  # noqa: D401 — test-only placeholder simulation
            raise NotImplementedError("simulated discovery placeholder")

    # Patch the class list to include _Boom in addition to the real vendors.
    from aichemy_pricing import __init__ as pkg
    monkeypatch.setattr(pkg, "_DEFAULT_VENDOR_CLASSES",
                        [_Boom] + pkg._DEFAULT_VENDOR_CLASSES)
    with caplog.at_level(logging.WARNING):
        chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    # _Boom must be absent from the chain.
    assert "boom" not in {m.name for m in chain.inner.members}
    # And we must have logged the skip.
    assert any("simulated discovery placeholder" in r.message for r in caplog.records)
```

- [ ] **Step 3: Run; pass**

```bash
uv run pytest src/aichemy_pricing/tests/test_build_default_chain.py -v
```

- [ ] **Step 4: Smoke test the public API**

```bash
uv run python -c "
import aichemy_pricing as p
print('exports:', sorted([x for x in p.__all__ if not x.startswith('_')]))
"
```

Expected: prints the full list including all 7 vendors, 3 resolvers, helpers.

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/__init__.py src/aichemy_pricing/tests/test_build_default_chain.py
git commit -m "feat(pricing): re-export public API + build_default_chain factory"
```

---

## Task E3: `cli.py` — `aichemy-price` console script

**Files:**
- Create: `src/aichemy_pricing/cli.py`
- Create: `src/aichemy_pricing/tests/test_cli.py`

- [ ] **Step 1: Failing tests**

```python
# src/aichemy_pricing/tests/test_cli.py
"""Unit tests for `aichemy-price` CLI."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from aichemy_pricing import cli as cli_module
from aichemy_pricing.cli import app
from aichemy_pricing.types import PriceQuote, VendorRef


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_version_flag(runner: CliRunner) -> None:
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    from aichemy_pricing import __version__
    assert __version__ in res.stdout


def test_cli_lookup_unknown_vendor_returns_2(runner: CliRunner) -> None:
    res = runner.invoke(app, ["lookup", "no-such-vendor", "X"])
    assert res.exit_code == 2
    assert "Unknown vendor" in (res.stdout + res.stderr)


def test_cli_lookup_calls_vendor(runner: CliRunner, monkeypatch) -> None:
    captured: dict[str, object] = {}
    quote = PriceQuote(
        vendor="fluorochem", sku="F765353-1G", price=230.0, currency="GBP",
        pack_size_g=1.0, fetched_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )

    class FakeVendor:
        name = "fluorochem"
        def lookup(self, ref: VendorRef) -> PriceQuote:
            captured["ref"] = ref
            return quote

    monkeypatch.setitem(cli_module._VENDORS, "fluorochem", FakeVendor)
    res = runner.invoke(app, ["lookup", "fluorochem", "F765353-1G"])
    assert res.exit_code == 0
    assert "230" in res.stdout and "GBP" in res.stdout
    assert isinstance(captured["ref"], VendorRef)


def test_cli_lookup_json_flag_dumps_pricequote(runner: CliRunner, monkeypatch) -> None:
    quote = PriceQuote(
        vendor="x", sku="y", price=1.0, currency="USD", pack_size_g=1.0,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    class FakeVendor:
        name = "x"
        def lookup(self, ref: VendorRef) -> PriceQuote:
            return quote

    monkeypatch.setitem(cli_module._VENDORS, "x", FakeVendor)
    res = runner.invoke(app, ["lookup", "x", "y", "--json"])
    assert res.exit_code == 0
    import json as _j
    parsed = _j.loads(res.stdout)
    assert parsed["price"] == 1.0
    assert parsed["currency"] == "USD"


def test_cli_lookup_returns_1_when_no_quote(runner: CliRunner, monkeypatch) -> None:
    class MissVendor:
        name = "miss"
        def lookup(self, ref: VendorRef) -> None:
            return None

    monkeypatch.setitem(cli_module._VENDORS, "miss", MissVendor)
    res = runner.invoke(app, ["lookup", "miss", "x"])
    assert res.exit_code == 1


def test_cli_lookup_placeholder_vendor_returns_2(runner: CliRunner, monkeypatch) -> None:
    """Vendors with unfilled discovery placeholders raise NotImplementedError
    from __init__ (Revision 6 fail-loud guard). The CLI must surface a clean
    typer.Exit(2), not a bare Python traceback."""
    class _Placeholder:
        name = "placeholder"
        def __init__(self) -> None:
            raise NotImplementedError("placeholder._API_URL not yet discovered")

    monkeypatch.setitem(cli_module._VENDORS, "placeholder", _Placeholder)
    res = runner.invoke(app, ["lookup", "placeholder", "X"])
    assert res.exit_code == 2
    assert "discovery placeholder" in (res.stdout + res.stderr).lower()
```

- [ ] **Step 2: Implement**

```python
# src/aichemy_pricing/cli.py
"""`aichemy-price` — CLI for single-SKU and end-to-end price lookups.

Usage:
    aichemy-price --version
    aichemy-price lookup fluorochem F765353-1G
    aichemy-price lookup molbase 50-78-2 --json
    aichemy-price chain F765353-1G                       # tries all vendors in order
    aichemy-price resolve BSYNRYMUTXBXSQ-UHFFFAOYSA-N \\
        --catalog-dir data/raw/pubchem_substance/        # offline JOIN, then chain
"""
from __future__ import annotations

from pathlib import Path

import typer

from aichemy_pricing import (
    EnamineSdfResolver, EnamineVendor, FluorochemVendor, MedChemExpressVendor,
    MolbaseVendor, PubChemSdfResolver, TocrisVendor, VendorRef, __version__,
    build_default_chain,
)
from aichemy_pricing.lookup_by_inchikey import LookupByInchikey
from aichemy_pricing.vendors.cayman import CaymanVendor
from aichemy_pricing.vendors.chemcruz import ChemCruzVendor

app = typer.Typer(help="aichemy-pricing CLI")

# Map vendor short-name → constructor. Mutable for tests via monkeypatch.
_VENDORS: dict[str, type] = {
    "fluorochem": FluorochemVendor,
    "molbase": MolbaseVendor,
    "tocris": TocrisVendor,
    "enamine": EnamineVendor,
    "cayman": CaymanVendor,
    "chemcruz": ChemCruzVendor,
    "medchemexpress": MedChemExpressVendor,
}


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_cb, is_eager=True, help="Show version and exit",
    ),
) -> None:
    """aichemy-pricing CLI."""


@app.command()
def lookup(
    vendor: str = typer.Argument(..., help="Vendor short-name; one of: fluorochem, molbase, tocris, enamine, cayman, chemcruz, medchemexpress"),
    sku: str = typer.Argument(..., help="Vendor SKU"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    """Look up a single SKU at one vendor."""
    if vendor not in _VENDORS:
        typer.echo(
            f"Unknown vendor: {vendor!r}; choose from {sorted(_VENDORS)}", err=True,
        )
        raise typer.Exit(2)
    try:
        v = _VENDORS[vendor]()
    except NotImplementedError as exc:
        # Discovery placeholder unfilled (Revision 6 fail-loud guard on
        # EnamineVendor / CaymanVendor). Surface as a clean exit rather than
        # a bare Python traceback — symmetric with `chain` (Revision 9) and
        # `build_default_chain` (Revision 16).
        typer.echo(f"{vendor}: discovery placeholder unfilled — {exc}", err=True)
        raise typer.Exit(2)
    quote = v.lookup(VendorRef(vendor=vendor, sku=sku))
    if quote is None:
        typer.echo("no quote (404 / unparseable / not stocked)", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(quote.model_dump_json(indent=2))
    else:
        typer.echo(f"{quote.price} {quote.currency} / {quote.pack_size_g} g")


@app.command()
def chain(
    sku: str = typer.Argument(..., help="SKU to try across all vendors in order"),
) -> None:
    """Try every vendor on a SKU in registration order, print the first hit.

    SKU format is vendor-specific; if you don't know which vendor a chemical
    matches, use `resolve` instead with an InChIKey + PubChem SDF directory.
    No cache by design — this command is for ad-hoc debugging, not pipeline
    use; use the `aichemy_pricing` library directly for cached lookups.
    """
    for vendor_name, vendor_cls in _VENDORS.items():
        ref = VendorRef(vendor=vendor_name, sku=sku)
        try:
            q = vendor_cls().lookup(ref)
        except Exception as exc:  # noqa: BLE001 — CLI debug; surface and continue
            typer.echo(f"{vendor_name}: error — {exc}", err=True)
            continue
        if q is not None:
            typer.echo(f"{q.vendor}: {q.price} {q.currency} / {q.pack_size_g} g")
            raise typer.Exit(0)
    typer.echo("no vendor returned a price", err=True)
    raise typer.Exit(1)


@app.command()
def resolve(
    inchikey: str = typer.Argument(..., help="Standard InChIKey (27 chars)"),
    catalog_dir: Path = typer.Option(..., "--catalog-dir", help="Directory with PubChem SDFs"),
    cache_path: Path = typer.Option(Path(".aichemy_pricing_cache.sqlite"), "--cache"),
) -> None:
    """Walk a PubChem SDF catalog → chain to find a price for an InChIKey."""
    sdf_files = sorted(catalog_dir.glob("*.sdf"))
    if not sdf_files:
        typer.echo(f"no .sdf files in {catalog_dir}", err=True)
        raise typer.Exit(2)
    resolver = PubChemSdfResolver.from_files(sdf_files)
    chain = build_default_chain(cache_path=cache_path)
    adapter = LookupByInchikey(resolver=resolver, chain=chain)
    quote = adapter.lookup(inchikey)
    if quote is None:
        typer.echo("no quote", err=True)
        raise typer.Exit(1)
    typer.echo(quote.model_dump_json(indent=2))


if __name__ == "__main__":  # pragma: no cover
    app()
```

- [ ] **Step 3: Run; pass (5 tests)**

```bash
uv run pytest src/aichemy_pricing/tests/test_cli.py -v
```

- [ ] **Step 4: Smoke test against the live CLI**

```bash
uv run aichemy-price --version
uv run aichemy-price lookup fluorochem F765353-1G || true   # may fail offline; non-zero acceptable
```

- [ ] **Step 5: Commit**

```bash
git add src/aichemy_pricing/cli.py src/aichemy_pricing/tests/test_cli.py
git commit -m "feat(pricing): aichemy-price CLI (lookup, chain, resolve)"
```

---

## Task E4: AIchemy pipeline integration

**Files:**
- Modify: `src/aichemy/preprocessing/augment/prices.py`
- Modify: `configs/default.yaml` (comment-only update)
- Create: `tests/integration/test_pricing_package_integration.py`

- [ ] **Step 1: Read current `make_lookup` factory + the config schema it consumes**

```bash
grep -n "def make_lookup\|backend" src/aichemy/preprocessing/augment/prices.py | head -30
grep -n "class PricesConfig\|backend.*Literal\|extra.*forbid" src/aichemy/config.py
```

Note: `PricesConfig` in `src/aichemy/config.py` declares `model_config = {"extra": "forbid"}` and `backend: Literal["stub", "chained"]`. Both must be widened **before** Step 2/3 edits — otherwise YAML and CLI commands fail at config-load with a Pydantic ValidationError.

- [ ] **Step 1b: Widen `PricesConfig` schema in `src/aichemy/config.py`**

Add a new typed sub-config and extend the Literal:

```python
class AichemyPricingConfig(BaseModel):
    """Backend-specific config for the standalone `aichemy_pricing` package.

    Path fields point at the offline catalog (PubChem SDF dir + a SQLite cache
    location). Free-form sub-keys are forbidden so typos surface at load time.
    """
    model_config = {"extra": "forbid"}

    catalog_dir: Path = Field(default_factory=lambda: Path("data/raw/pubchem_substance"))
    cache_path: Path = Field(default_factory=lambda: Path("data/interim/aichemy_pricing_cache.sqlite"))


class PricesConfig(BaseModel):
    model_config = {"extra": "forbid"}

    backend: Literal["stub", "chained", "aichemy_pricing"] = "chained"  # ← widen
    chain: list[str] = Field(default_factory=lambda: ["curated", "pubchem"])
    cache_path: Path = Field(default_factory=lambda: Path("data/interim/prices_cache.sqlite"))
    cache_ttl_days: int = 30
    pubchem: PubChemConfig = Field(default_factory=PubChemConfig)
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    aichemy_pricing: AichemyPricingConfig = Field(default_factory=AichemyPricingConfig)  # ← add
```

Add a unit test in `tests/unit/test_config.py` that loads `configs/default.yaml` and asserts `cfg.prices.backend in {"stub", "chained", "aichemy_pricing"}` and `cfg.prices.aichemy_pricing.catalog_dir.name == "pubchem_substance"`. Without this, a future regression that drops the field from the schema would only surface as a CLI runtime error.

- [ ] **Step 2: Add `aichemy_pricing` backend branch + `_InchikeyAdapter`**

The existing AIchemy interface (per `src/aichemy/preprocessing/augment/prices.py`):

```python
class PriceLookup(Protocol):
    """A source that maps a canonical SMILES string to a per-gram USD price."""
    def lookup(self, smiles: str) -> float | None: ...
```

…returns a `float` USD-per-gram, while the new package returns a `PriceQuote` keyed by InChIKey. The adapter bridges them: SMILES → InChIKey via RDKit → `LookupByInchikey` → `PriceQuote` → convert to USD/g.

Append to `src/aichemy/preprocessing/augment/prices.py`:

```python
# ---------- aichemy_pricing adapter -----------------------------------------

# Static FX table (USD per 1 unit of foreign currency). Documented as-of date
# matters: rates drift; refresh quarterly or wire a live FX source.
# Source: ECB reference rates on _FX_AS_OF below.
import datetime as _dt  # local alias to avoid polluting public module namespace

_FX_AS_OF: _dt.date = _dt.date(2026, 4, 25)
_FX_MAX_AGE = _dt.timedelta(days=120)

_FX_TO_USD_AS_OF_2026_04_25: dict[str, float] = {
    "USD": 1.000,
    "GBP": 1.330,   # 1 GBP = 1.33 USD
    "EUR": 1.090,   # 1 EUR = 1.09 USD
    "CNY": 0.138,   # 1 CNY = 0.138 USD
    "JPY": 0.0064,
    "SEK": 0.094,
}


def _check_fx_freshness() -> None:
    """Emit a single warning at module-import time if the FX table is older
    than the freshness threshold. Without this, prices silently compound drift
    over months — CNY in particular moves 5–10% intra-year. The 30-day quote
    cache TTL means a stale table is used for every quote captured during the
    cache window, then re-multiplied at the same rate when re-fetched."""
    age = _dt.date.today() - _FX_AS_OF
    if age > _FX_MAX_AGE:
        log.warning(
            "aichemy_pricing FX table is %d days old (as-of %s, max-age %d days). "
            "Refresh ECB reference rates and bump _FX_AS_OF, or wire a live FX feed.",
            age.days, _FX_AS_OF.isoformat(), _FX_MAX_AGE.days,
        )


_check_fx_freshness()


class _InchikeyAdapter:
    """Wraps an `aichemy_pricing.LookupByInchikey` so it satisfies AIchemy's
    `PriceLookup` protocol (SMILES → USD/g float).

    Steps per call:
      1. Compute InChIKey from canonical SMILES via RDKit.
      2. Delegate to LookupByInchikey → PriceQuote | None.
      3. Convert `price_per_gram_native` to USD via static FX table.
      4. Return float or None.
    """

    def __init__(
        self,
        inner,  # aichemy_pricing.LookupByInchikey — typed loosely to keep the
                # main aichemy package's import surface stable when the optional
                # `pricing` extra is absent.
        fx_to_usd: dict[str, float] | None = None,
    ) -> None:
        self._inner = inner
        self._fx = fx_to_usd or _FX_TO_USD_AS_OF_2026_04_25

    def lookup(self, smiles: str) -> float | None:
        from rdkit import Chem  # lazy import: only when this backend is used

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        try:
            inchikey = Chem.MolToInchiKey(mol)
        except Exception as exc:  # InChI lib raises on radicals/non-standard valences
            log.warning("MolToInchiKey raised on %r: %s", smiles, exc)
            return None
        if not inchikey:
            return None
        quote = self._inner.lookup(inchikey)
        if quote is None:
            return None
        rate = self._fx.get(quote.currency)
        if rate is None:
            log.warning(
                "aichemy_pricing returned %s; no FX rate for %s — dropping quote",
                quote, quote.currency,
            )
            return None
        return quote.price_per_gram_native * rate
```

Then the `make_lookup` factory branch:

```python
# Inside aichemy.preprocessing.augment.prices.make_lookup, after existing branches:

if cfg.backend == "aichemy_pricing":
    from pathlib import Path

    from aichemy_pricing import (
        LookupByInchikey, PubChemSdfResolver, build_default_chain,
    )

    catalog_dir = Path(cfg.aichemy_pricing.catalog_dir)
    cache_path = Path(cfg.aichemy_pricing.cache_path)
    sdf_files = sorted(catalog_dir.glob("*.sdf*"))
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
```

- [ ] **Step 3: Document the new branch in `configs/default.yaml`**

Add a comment under `prices:`:

```yaml
prices:
  backend: stub                # stub | chained | aichemy_pricing
  # When backend == "aichemy_pricing", consumes the standalone package.
  # See docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md
  aichemy_pricing:
    catalog_dir: data/raw/pubchem_substance/
    cache_path: data/interim/aichemy_pricing_cache.sqlite
```

(No model-level config validation is required for v1 — keep it as a free-form sub-key. Sub-plan F can add the pydantic model later.)

- [ ] **Step 4: Integration test (+ FX-table completeness assertion)**

```python
# tests/integration/test_pricing_package_integration.py
"""End-to-end: AIchemy pipeline picks up aichemy_pricing as a backend.

This test does NOT hit the network — it uses a captured Fluorochem fixture
and a synthetic SDF that maps a known InChIKey to F765353.
"""
from __future__ import annotations

import json
import typing
from pathlib import Path

import httpx
import pytest

# Skip at collection time if pricing extra isn't installed.
pytest.importorskip("aichemy_pricing")


def test_fx_table_covers_every_currency_literal() -> None:
    """The `_InchikeyAdapter` returns None when a quote arrives in a currency
    missing from the FX table, with a warning log. That's a silent yield drop
    waiting to happen if anyone adds a new `Currency` literal without also
    extending the FX table. Lock that invariant in.
    """
    from aichemy.preprocessing.augment.prices import _FX_TO_USD_AS_OF_2026_04_25
    from aichemy_pricing.types import Currency

    declared_currencies = set(typing.get_args(Currency))
    fx_currencies = set(_FX_TO_USD_AS_OF_2026_04_25)
    missing = declared_currencies - fx_currencies
    assert not missing, (
        f"Currency literal members missing from FX table: {missing}. "
        f"Either add an FX rate or shrink the Currency literal."
    )


def test_aichemy_pipeline_can_use_aichemy_pricing_backend(tmp_path, monkeypatch) -> None:
    """Wire the new backend through and confirm a price round-trips."""
    from aichemy_pricing import build_default_chain
    from aichemy_pricing.types import VendorRef

    fixture = Path("src/aichemy_pricing/tests/data/fluorochem_F765353.json").read_bytes()

    def mock_send(self, request, **kw):  # noqa: ARG001
        if "fluorochem" in str(request.url):
            return httpx.Response(200, content=fixture, request=request)
        return httpx.Response(404, request=request)
    monkeypatch.setattr(httpx.Client, "send", mock_send)

    chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    quote = chain.lookup(VendorRef(vendor="fluorochem", sku="F765353-1G"))
    assert quote is not None
    assert quote.currency == "GBP"
```

- [ ] **Step 5: Run all tests; no regressions**

```bash
uv run pytest tests/ -v
uv run pytest src/aichemy_pricing/tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aichemy/preprocessing/augment/prices.py configs/default.yaml tests/integration/test_pricing_package_integration.py
git commit -m "feat(aichemy): wire aichemy_pricing as augment-prices backend"
```

---

## Task E5: README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Vendor pricing" section**

Append to `README.md`:

```markdown
## Vendor pricing

`aichemy-pricing` is a standalone package (sibling to `aichemy`) that resolves
chemical identifiers to per-gram USD/GBP/EUR prices via a tiered chain of
verified vendor sources.

**Install + verify:**
```bash
uv sync --extra pricing
uv run aichemy-price --version
```

**Single-SKU debugging:**
```bash
uv run aichemy-price lookup fluorochem F765353-1G
uv run aichemy-price lookup molbase 50-78-2 --json
```

**Try all vendors in chain:**
```bash
uv run aichemy-price chain F765353-1G
```

**InChIKey → price (offline JOIN + scrape):**
```bash
uv run aichemy-price resolve BSYNRYMUTXBXSQ-UHFFFAOYSA-N \
    --catalog-dir data/raw/pubchem_substance/
```

**Use as an AIchemy backend:**
```yaml
# configs/default.yaml
prices:
  backend: aichemy_pricing
```

The implementation plan and verification trail live at:
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md` (master)
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-{A,B,C,D,E}-*.md` (sub-plans)
- `experiments/chem-pricing-verification/VERIFICATION.md` (29/29 claims verdict-ed)

Vendors covered: Fluorochem, Molbase, Tocris, Enamine, Cayman Chemical,
Santa Cruz/ChemCruz, MedChemExpress.
Excluded: Apollo Scientific (CLAIM-11 FALSIFIED), Sigma-Aldrich + TCI
(behind Akamai — deferred), BLDpharm (CLAIM-16 — URL TBD).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README — vendor pricing section"
```

---

## Task E6: End-to-end verification

- [ ] **Step 1: Standalone test suite passes**

```bash
uv run pytest src/aichemy_pricing/tests/ -v --tb=short
```

Expected: all offline tests pass; live tests skipped.

- [ ] **Step 2: Live verification (on demand)**

```bash
uv run pytest src/aichemy_pricing/tests/ -m live -v --tb=short
```

Expected: at least Fluorochem and Tocris live tests pass; Enamine / Cayman / MCE pass after their D1.0 / D2.0 / D4 capture steps are run.

- [ ] **Step 3: AIchemy pipeline regression**

```bash
uv run pytest tests/ -v
```

Expected: no failures.

- [ ] **Step 4: Type-check entire pricing package**

```bash
uv run mypy src/aichemy_pricing/
```

Expected: Success.

- [ ] **Step 5: Lint**

```bash
uv run ruff check src/aichemy_pricing/
uv run ruff format --check src/aichemy_pricing/
```

Expected: clean.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit --allow-empty -m "test(pricing): end-to-end verification — all offline tests green"
```

---

## Unit Tests Summary (Sub-Plan E)

| Test file | Test count | Notes |
|---|---:|---|
| `test_lookup_by_inchikey.py` | 3 | First priced vendor wins; no resolver hits → None; no chain hits → None |
| `test_build_default_chain.py` | 3 | Returns `CachedPriceLookup(ChainedPriceLookup(...))`; excluded vendors absent; **placeholder vendors skipped with warning (Revision 16)** |
| `test_cli.py` | 6 | `--version`; unknown vendor → exit 2; lookup dispatch; `--json` flag; no-quote → exit 1; **placeholder vendor → exit 2 with clean message (Revision 27)** |
| `tests/integration/test_pricing_package_integration.py` | 2 | FX-table covers every Currency literal; pipeline backend round-trips a Fluorochem fixture quote |
| **Total** | **14** | All offline; no `live` markers in this sub-plan. |

**Cumulative test counts across all sub-plans:**

| Sub-plan | Offline | Live |
|---|---:|---:|
| A | 21 | 0 |
| B | 17 | 1 |
| C | 15 | 3 |
| D | 16 | 4 |
| E | 14 | 0 |
| **Total** | **83** | **8** |

**All tests:**
```bash
uv run pytest src/aichemy_pricing/tests/ tests/integration/test_pricing_package_integration.py -v
```

**Type-check + lint:**
```bash
uv run mypy src/aichemy_pricing/ && uv run ruff check src/aichemy_pricing/
```

---

## Self-review

**Spec coverage:** Every interface declared in the parent plan is now exposed via `__init__.py`. The CLI has `lookup` (single vendor), `chain` (try all), and `resolve` (InChIKey → price). The `LookupByInchikey` adapter glues resolvers to the chain. The AIchemy integration adds a single `aichemy_pricing` backend branch without touching the existing `stub` or `chained` paths. README documents the install + CLI usage.

**Placeholder scan:** No "TBD" / "implement later" — every step has actual code or a documented external action (DevTools discovery in sub-plan D, fixture capture in sub-plans C/D). The `_InchikeyAdapter` in Task E4 step 2 is now fully implemented inline (constructor + RDKit InChIKey computation + static FX-to-USD table dated 2026-04-25 + structured logging on missing FX rate). The FX table is intentionally minimal and documented as drift-prone; refresh quarterly or wire a live FX feed.

**Type consistency:** All re-exported symbols match what sub-plans A–D promised. `build_default_chain` returns `CachedPriceLookup`; `LookupByInchikey.lookup(inchikey: str) -> PriceQuote | None`; CLI exit codes are stable (`0` success, `1` no quote, `2` bad input).
