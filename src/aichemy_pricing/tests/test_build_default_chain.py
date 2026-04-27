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
    # `tocris` is excluded too: HTML restructure leaves every lookup running
    # out the connection timeout. `browserbase_browser` is excluded: only the
    # `enamine` parser is registered there and every non-enamine ref ate
    # ~10s session-setup time. Both are still reachable via the DSN
    # dispatch path (build_default_dispatch).
    excluded = {
        "apollo",
        "sigma",
        "sigma-aldrich",
        "tci",
        "bld",
        "bldpharm",
        "tocris",
        "browserbase_browser",
    }
    assert vendor_names.isdisjoint(excluded)
    # Direct-HTTP vendor classes that survived the prune, plus L3a Fetch
    # (chemcruz parser registered, gated per-vendor — short-circuits cheaply
    # on misses).
    required = {
        "fluorochem",
        "molbase",
        "medchemexpress",
        "browserbase_fetch",
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
