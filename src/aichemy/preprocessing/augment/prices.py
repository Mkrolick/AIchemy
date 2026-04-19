from __future__ import annotations

from typing import Protocol


class PriceLookup(Protocol):
    def lookup(self, smiles: str) -> float | None: ...


class StubPriceLookup:
    """In-memory PriceLookup for tests and early-dev workflows (ChemPrize not yet wired)."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices = prices or {}

    def lookup(self, smiles: str) -> float | None:
        return self._prices.get(smiles)
