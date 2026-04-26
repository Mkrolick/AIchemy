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

    # Which boolean column gates which reactions enter the MILP.
    # "rdkit_balanced" (default, strict): per-element atom-count equality
    #   verified by RDKit in the balance_validate stage.
    # "balanced" (looser): per-source claim — SYN-RBL conf > 0.8 for USPTO,
    #   curator's is_balanced=='B' for MetaNetX. After the drop_unbalanced
    #   stage every surviving row has balanced=True, so this is effectively
    #   "no atom-count filter".
    balance_filter: Literal["balanced", "rdkit_balanced"] = "rdkit_balanced"

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

    # Royalty rate on process-covered reaction revenue (decimal fraction, [0, 1]).
    # Default 0.0 preserves legacy behavior when license data is absent or
    # the sweep CLI hasn't been invoked.
    r_process: float = 0.0

    # Royalty rate on composition-covered product revenue (decimal fraction, [0, 1]).
    r_comp: float = 0.0

    # Where to write the JSON summary of the solved problem.
    output_path: Path = Field(default_factory=lambda: Path("data/processed/solution.json"))
