"""Solver configuration — extends the preprocessing `PreprocessingConfig`.

Kept in its own module so `aichemy.solver` stays an independent entry
point that doesn't force preprocessing imports when just running the
solver on precomputed parquets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SolverConfig(BaseModel):
    """Knobs for the MILP profit-maximization solver."""

    model_config = {"extra": "forbid"}

    # Budget for the buy side of the MILP ($ total).
    budget: float = 10_000.0

    # Default price used when ChemPrize / scraper / ZINC didn't produce one.
    # Set high to discourage purchasing; alternately set to None to forbid
    # buying anything without a real price (stricter, but may make the
    # problem infeasible).
    default_buy_price: float = 1_000.0

    # Default sell-side price for molecules without a catalog price.
    # Typically ≤ buy price to prevent arbitrage from gaps.
    default_sell_price: float = 0.0

    # Minimum non-zero flow when a reaction is activated (prevents
    # "epsilon-activations" that win the objective by cents).
    min_flow: float = 1e-3

    # Upper bound on per-reaction flow (prevents unbounded pathways).
    max_flow: float = 1_000.0

    # Cardinality cap on the number of products selected for sale.
    # Set to None to allow any number.
    max_products: int | None = None

    # Backend: "cbc" (bundled with pulp), "gurobi" (requires license).
    backend: Literal["cbc", "gurobi"] = "cbc"

    # Verbosity
    verbose: bool = False

    # Where to write the JSON summary of the solved problem.
    output_path: Path = Field(default_factory=lambda: Path("data/processed/solution.json"))
