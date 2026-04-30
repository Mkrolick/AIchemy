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

    # Cardinality cap on the number of reactions activated.
    # Set to None to allow any number. Useful for synthesis-route lengths
    # where the user wants only a small number of distinct steps.
    max_reactions: int | None = None

    # Molecules that are not allowed to be sold (q_sell pinned to 0).
    # Useful for "what-if I can't monetize this specific compound" analyses
    # — e.g., regulatory restrictions, internal-use targets, or to force
    # the optimizer to find an alternate revenue path.
    forbidden_sell_molecules: list[str] = Field(default_factory=list)

    # When True, multiply each stoichiometric coefficient by the
    # participant's molecular weight (g/mol) before building the mass-
    # balance constraint. This makes coef·f represent grams of m on both
    # sides of the equation (matching q_buy / q_sell, which are gram-
    # denominated via price_per_gram). Under mass_basis=True, f[r]
    # becomes "mol of reaction extent" by construction; min_flow / max_flow
    # are likewise in mol-extents (kept numerically identical because for
    # typical chemistry MW=100-500 g/mol, max_flow=1000 still gives 100-500
    # kg of throughput — well above the budget-realistic bound).
    #
    # Default False preserves pre-fix behavior (which is dimensionally
    # inconsistent for MW-asymmetric reactions like 2 H2O -> 2 H2 + O2,
    # but stable as a regression baseline). The MILP solver loads MW from
    # data/processed/molecules_with_mw.parquet (produced by
    # `aichemy augment molecule-weights`); reactions with any participant
    # missing a usable MW are dropped with a tally logged.
    mass_basis: bool = False

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
