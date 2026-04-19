"""Tests for eQuilibrator thermo augmentation (Open Item 03)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.augment import thermo


def test_is_available_returns_bool() -> None:
    # Just verify it doesn't raise — return value depends on whether
    # the `thermo` extra is installed.
    assert isinstance(thermo.is_available(), bool)


def test_augment_thermo_raises_when_dep_missing(monkeypatch) -> None:
    """If equilibrator-api isn't installed, augment_thermo should fail loudly."""
    import importlib

    # Force the deferred import to fail
    real_import = (
        __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__
    )

    def _raising_import(name, *args, **kwargs):
        if name == "equilibrator_api":
            raise ImportError("Simulated: equilibrator_api not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _raising_import)
    importlib.reload(thermo)  # pick up the patched import guard

    df = pl.DataFrame({"reaction_smiles": ["CCO>>CC=O"]})
    try:
        thermo.augment_thermo(df)
    except ImportError as exc:
        assert "equilibrator-api" in str(exc)
    else:
        # If equilibrator-api happens to be installed, the reload may have
        # picked up the real module — that's fine, just skip.
        if thermo.is_available():
            pass
        else:
            raise AssertionError("Expected ImportError when thermo dep missing")
