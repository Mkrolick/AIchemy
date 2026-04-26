"""`aichemy-price` — CLI for single-SKU and end-to-end price lookups.

Usage:
    aichemy-price --version
    aichemy-price lookup fluorochem F765353-1G
    aichemy-price lookup molbase 50-78-2 --json
    aichemy-price chain F765353-1G                         # walks every known
                                                            # vendor name through
                                                            # the full default chain
    aichemy-price resolve BSYNRYMUTXBXSQ-UHFFFAOYSA-N \\
        --catalog-dir data/raw/pubchem_substance/

Vendor short-names supported by `lookup` are the four with direct-HTTP
classes (fluorochem, molbase, tocris, medchemexpress). For Enamine /
Cayman / ChemCruz / Sigma, use `chain` or `resolve` — those vendors are
reached via the L3 Browserbase layers (Fetch for SSR, Browser API for SPAs).
"""
from __future__ import annotations

from pathlib import Path

import typer

from aichemy_pricing import (
    FluorochemVendor,
    MedChemExpressVendor,
    MolbaseVendor,
    PubChemSdfResolver,
    TocrisVendor,
    VendorRef,
    __version__,
    build_default_chain,
)
from aichemy_pricing.browserbase.browser_parsers import (
    REGISTRY as _BROWSER_REGISTRY,
)
from aichemy_pricing.browserbase.parsers import REGISTRY as _FETCH_REGISTRY
from aichemy_pricing.lookup_by_inchikey import LookupByInchikey

app = typer.Typer(help="aichemy-pricing CLI")

# Map vendor short-name -> direct-HTTP vendor class. Mutable for tests via
# monkeypatch. Enamine / Cayman / ChemCruz / Sigma are *not* here — they
# only reach the chain via L3 Browserbase paths.
_VENDORS: dict[str, type] = {
    "fluorochem": FluorochemVendor,
    "molbase": MolbaseVendor,
    "tocris": TocrisVendor,
    "medchemexpress": MedChemExpressVendor,
}


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_cb,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """aichemy-pricing CLI."""


@app.command()
def lookup(
    vendor: str = typer.Argument(
        ...,
        help=(
            "Vendor short-name; one of: fluorochem, molbase, tocris, "
            "medchemexpress"
        ),
    ),
    sku: str = typer.Argument(..., help="Vendor SKU"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    """Look up a single SKU at one direct-HTTP vendor."""
    if vendor not in _VENDORS:
        typer.echo(
            f"Unknown vendor: {vendor!r}; choose from {sorted(_VENDORS)}",
            err=True,
        )
        raise typer.Exit(2)
    try:
        v = _VENDORS[vendor]()
    except NotImplementedError as exc:
        # Discovery placeholder unfilled (Revision 27 — symmetric with the
        # chain factory's placeholder skip). Surface a clean exit rather
        # than a bare Python traceback.
        typer.echo(
            f"{vendor}: discovery placeholder unfilled — {exc}", err=True
        )
        raise typer.Exit(2) from exc
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
    sku: str = typer.Argument(
        ..., help="SKU to try across every known vendor in the default chain"
    ),
    cache_path: Path = typer.Option(
        Path(".aichemy_pricing_cache_chain.sqlite"),
        "--cache",
        help="SQLite cache path (re-used across invocations to save calls)",
    ),
) -> None:
    """Try every known vendor name on a SKU through the full default chain.

    Walks the union of direct-HTTP vendors (`_VENDORS`), the L3 Fetch
    parser registry, and the L3 Browser API parser registry — for each
    candidate vendor name builds a `VendorRef(vendor=name, sku=sku)` and
    runs it through `build_default_chain`. Prints the first hit. SKU
    format is vendor-specific; if you don't know which vendor a chemical
    matches, use `resolve` with an InChIKey + PubChem SDF directory.
    """
    pipeline = build_default_chain(cache_path=cache_path)
    candidates = (
        list(_VENDORS.keys())
        + list(_FETCH_REGISTRY.keys())
        + list(_BROWSER_REGISTRY.keys())
    )
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        ref = VendorRef(vendor=name, sku=sku)
        try:
            q = pipeline.lookup(ref)
        except Exception as exc:  # noqa: BLE001 — debug walk, surface and continue
            typer.echo(f"{name}: error — {exc}", err=True)
            continue
        if q is not None:
            typer.echo(f"{q.vendor}: {q.price} {q.currency} / {q.pack_size_g} g")
            raise typer.Exit(0)
    typer.echo("no vendor returned a price", err=True)
    raise typer.Exit(1)


@app.command()
def resolve(
    inchikey: str = typer.Argument(..., help="Standard InChIKey (27 chars)"),
    catalog_dir: Path = typer.Option(
        ..., "--catalog-dir", help="Directory with PubChem SDFs"
    ),
    cache_path: Path = typer.Option(
        Path(".aichemy_pricing_cache.sqlite"), "--cache"
    ),
) -> None:
    """Walk a PubChem SDF catalog -> default chain to price an InChIKey."""
    sdf_files = sorted(
        list(catalog_dir.glob("*.sdf")) + list(catalog_dir.glob("*.sdf.gz"))
    )
    if not sdf_files:
        typer.echo(f"no .sdf or .sdf.gz files in {catalog_dir}", err=True)
        raise typer.Exit(2)
    resolver = PubChemSdfResolver.from_files(sdf_files)
    pipeline = build_default_chain(cache_path=cache_path)
    adapter = LookupByInchikey(resolver=resolver, chain=pipeline)
    quote = adapter.lookup(inchikey)
    if quote is None:
        typer.echo("no quote", err=True)
        raise typer.Exit(1)
    typer.echo(quote.model_dump_json(indent=2))


if __name__ == "__main__":  # pragma: no cover
    app()
