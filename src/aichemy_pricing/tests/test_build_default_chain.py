"""Unit tests for build_default_chain."""

from __future__ import annotations

import logging

from aichemy_pricing import (
    CachedPriceLookup,
    ChainedPriceLookup,
    build_default_chain,
)


def test_build_default_chain_returns_cached_chain(tmp_path) -> None:
    chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    assert isinstance(chain, CachedPriceLookup)
    assert isinstance(chain.inner, ChainedPriceLookup)


def test_build_default_chain_omits_excluded_vendors_and_includes_required(
    tmp_path,
) -> None:
    chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    assert isinstance(chain.inner, ChainedPriceLookup)
    vendor_names = {m.name for m in chain.inner.members}
    excluded = {"apollo", "sigma", "sigma-aldrich", "tci", "bld", "bldpharm"}
    assert vendor_names.isdisjoint(excluded)
    # The 4 direct-HTTP vendor classes plus the two L3 Browserbase layers
    # must always be present. ChemCruz/Enamine reach the chain *through*
    # those L3 layers (parser registries), they are not chain members.
    required = {
        "fluorochem",
        "tocris",
        "molbase",
        "medchemexpress",
        "browserbase_fetch",
        "browserbase_browser",
    }
    assert required.issubset(vendor_names)


def test_build_default_chain_skips_placeholder_vendors_gracefully(
    tmp_path, monkeypatch, caplog
) -> None:
    """If a vendor's __init__ raises NotImplementedError (the placeholder
    fail-loud guard), the chain factory must catch it, log a warning, and
    continue — not crash. Mirrors the production behavior where
    augment_prices keeps running even with one undiscovered vendor."""
    import aichemy_pricing as pkg

    class _Boom:
        name = "boom"

        def __init__(self) -> None:
            raise NotImplementedError("simulated discovery placeholder")

    monkeypatch.setattr(pkg, "_DEFAULT_VENDOR_CLASSES", [_Boom, *pkg._DEFAULT_VENDOR_CLASSES])
    with caplog.at_level(logging.WARNING):
        chain = build_default_chain(cache_path=tmp_path / "c.sqlite")
    assert isinstance(chain.inner, ChainedPriceLookup)
    assert "boom" not in {m.name for m in chain.inner.members}
    assert any("simulated discovery placeholder" in r.message for r in caplog.records)
