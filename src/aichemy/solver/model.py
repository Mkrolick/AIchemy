"""MILP profit-maximization over the chemo-enzymatic reaction hypergraph.

Follows the formulation from `proposal.md`:

Decision variables
------------------
    f_r ∈ ℝ≥0         molar flow through reaction r
    y_r ∈ {0, 1}      whether reaction r is activated
    w_m ∈ {0, 1}      whether molecule m is targeted for sale
    q_buy_m, q_sell_m ∈ ℝ≥0  quantities purchased / sold

Objective
---------
    max  Σ_m  π_sell_m · q_sell_m  −  Σ_m  π_buy_m · q_buy_m

Constraints
-----------
    Mass balance per molecule m:
        q_buy_m + Σ_r (a_r,m · η_r · f_r  for m a PRODUCT of r)
      = q_sell_m + Σ_r (a_r,m · f_r       for m a REACTANT of r)

    Flow activation bounds:
        min_flow · y_r  ≤  f_r  ≤  max_flow · y_r

    Sellable quantity bound (linearizes w_m · q_sell_m):
        q_sell_m  ≤  M · w_m           where M = max_flow · max stoichiometric coefficient

    Budget:
        Σ_m π_buy_m · q_buy_m  ≤  B

    Product cardinality (optional):
        Σ_m w_m  ≤  max_products
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import polars as pl
import pulp

from aichemy.solver.config import SolverConfig

log = logging.getLogger(__name__)


@dataclass
class Solution:
    """Solved MILP output.

    Attributes:
        status: pulp status string (e.g. "Optimal", "Infeasible")
        objective_value: total profit ($)
        activated_reactions: list of {rxn_id, flow, yield_rate} dicts
        purchased_molecules: list of {mol_id, quantity, price_per_gram, cost} dicts
        sold_molecules: list of {mol_id, quantity, price_per_gram, revenue} dicts
    """

    status: str
    objective_value: float
    activated_reactions: list[dict[str, Any]]
    purchased_molecules: list[dict[str, Any]]
    sold_molecules: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "objective_value": float(self.objective_value),
            "activated_reactions": self.activated_reactions,
            "purchased_molecules": self.purchased_molecules,
            "sold_molecules": self.sold_molecules,
        }


def build_and_solve(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame,
    config: SolverConfig,
) -> Solution:
    """Build the MILP, solve it, return the Solution.

    Filters reactions to those with ``config.balance_filter == True`` (default
    ``rdkit_balanced``; ``balanced`` for the looser per-source claim). Uses
    ``price_per_gram`` from molecules; falls back to
    ``config.default_{buy,sell}_price`` for unpriced molecules.
    """
    # Filter to balanced reactions only — unbalanced rows would violate mass
    # conservation in the MILP. Column choice (strict rdkit_balanced vs looser
    # balanced) is selectable via SolverConfig.balance_filter.
    col = config.balance_filter
    if col in reactions.columns:
        reactions = reactions.filter(pl.col(col))
    if reactions.height == 0:
        return Solution("No reactions after filtering", 0.0, [], [], [])

    # Reaction-level composition_covered → molecule-level: any product of a
    # composition-covered reaction is itself composition-covered for royalty.
    if "composition_covered" in reactions.columns:
        comp_mol_ids: set[str] = set()
        for row in reactions.iter_rows(named=True):
            if row.get("composition_covered"):
                for stoich in row["products"]:
                    comp_mol_ids.add(stoich["mol_id"])
        molecules = molecules.with_columns(
            pl.col("mol_id").is_in(list(comp_mol_ids)).alias("composition_covered")
        )

    # Universe of molecules is every mol_id referenced by a surviving reaction.
    referenced: set[str] = set()
    rxn_meta: list[dict[str, Any]] = []
    for row in reactions.iter_rows(named=True):
        rxn_id = row["rxn_id"]
        yield_rate = row.get("yield_rate") or 0.85  # fallback to prior-mean
        reactants = [
            (stoich["mol_id"], float(stoich["coefficient"])) for stoich in row["reactants"]
        ]
        products = [(stoich["mol_id"], float(stoich["coefficient"])) for stoich in row["products"]]
        for mol_id, _ in reactants + products:
            referenced.add(mol_id)
        rxn_meta.append(
            {
                "rxn_id": rxn_id,
                "yield_rate": yield_rate,
                "reactants": reactants,
                "products": products,
                "process_covered": bool(row.get("process_covered") or False),
            }
        )

    # Price lookup: molecule mol_id → (buy_price, sell_price).
    price_lookup = _build_price_lookup(molecules, referenced, config)

    composition_covered: set[str] = set()
    if "composition_covered" in molecules.columns:
        for r in molecules.iter_rows(named=True):
            if r.get("composition_covered"):
                composition_covered.add(r["mol_id"])

    # Build pulp problem.
    prob = pulp.LpProblem("AIchemy_profit", pulp.LpMaximize)

    # Variables
    f = {
        m["rxn_id"]: pulp.LpVariable(
            f"f_{_safe(m['rxn_id'])}",
            lowBound=0.0,
            upBound=config.max_flow,
        )
        for m in rxn_meta
    }
    y = {
        m["rxn_id"]: pulp.LpVariable(
            f"y_{_safe(m['rxn_id'])}",
            cat=pulp.LpBinary,
        )
        for m in rxn_meta
    }
    q_buy = {
        mol_id: pulp.LpVariable(f"qbuy_{_safe(mol_id)}", lowBound=0.0) for mol_id in referenced
    }
    q_sell = {
        mol_id: pulp.LpVariable(f"qsell_{_safe(mol_id)}", lowBound=0.0) for mol_id in referenced
    }
    w = {mol_id: pulp.LpVariable(f"w_{_safe(mol_id)}", cat=pulp.LpBinary) for mol_id in referenced}

    # Objective: sell revenue − buy cost − process royalty − composition royalty
    revenue = pulp.lpSum(price_lookup[m][1] * q_sell[m] for m in referenced)
    cost = pulp.lpSum(price_lookup[m][0] * q_buy[m] for m in referenced)

    process_royalty = pulp.lpSum(
        config.r_process
        * sum(price_lookup[mid][1] for (mid, _) in m["products"])
        * m["yield_rate"]
        * f[m["rxn_id"]]
        for m in rxn_meta
        if m["process_covered"]
    )
    composition_royalty = pulp.lpSum(
        config.r_comp * price_lookup[m][1] * q_sell[m]
        for m in referenced
        if m in composition_covered
    )

    prob += (revenue - cost - process_royalty - composition_royalty, "total_profit")

    # Mass balance: for each molecule, supply = consumption.
    for mol_id in referenced:
        supply = q_buy[mol_id] + pulp.lpSum(
            coef * m["yield_rate"] * f[m["rxn_id"]]
            for m in rxn_meta
            for (mid, coef) in m["products"]
            if mid == mol_id
        )
        consumption = q_sell[mol_id] + pulp.lpSum(
            coef * f[m["rxn_id"]]
            for m in rxn_meta
            for (mid, coef) in m["reactants"]
            if mid == mol_id
        )
        prob += supply == consumption, f"mass_balance_{_safe(mol_id)}"

    # Flow activation bounds
    for m in rxn_meta:
        rxn_id = m["rxn_id"]
        prob += f[rxn_id] >= config.min_flow * y[rxn_id], f"flow_lb_{_safe(rxn_id)}"
        prob += f[rxn_id] <= config.max_flow * y[rxn_id], f"flow_ub_{_safe(rxn_id)}"

    # Sellable-quantity bound (w_m switches sell_m on/off)
    sell_big_m = config.max_flow * 100.0  # generous upper bound
    for mol_id in referenced:
        prob += q_sell[mol_id] <= sell_big_m * w[mol_id], f"sell_switch_{_safe(mol_id)}"

    # Budget
    prob += (
        pulp.lpSum(price_lookup[m][0] * q_buy[m] for m in referenced) <= config.budget,
        "budget",
    )

    # Product cardinality
    if config.max_products is not None:
        prob += (
            pulp.lpSum(w[m] for m in referenced) <= config.max_products,
            "product_cap",
        )

    # Solve
    solver = _make_solver(config)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    objective = pulp.value(prob.objective) or 0.0

    # Extract activated reactions + non-trivial buys/sells
    activated: list[dict[str, Any]] = []
    for m in rxn_meta:
        val = pulp.value(f[m["rxn_id"]]) or 0.0
        if val > config.min_flow / 2:
            activated.append(
                {"rxn_id": m["rxn_id"], "flow": float(val), "yield_rate": m["yield_rate"]}
            )

    purchased: list[dict[str, Any]] = []
    sold: list[dict[str, Any]] = []
    for mol_id in referenced:
        bq = pulp.value(q_buy[mol_id]) or 0.0
        sq = pulp.value(q_sell[mol_id]) or 0.0
        buy_p, sell_p = price_lookup[mol_id]
        if bq > 1e-6:
            purchased.append(
                {
                    "mol_id": mol_id,
                    "quantity": float(bq),
                    "price_per_gram": buy_p,
                    "cost": float(bq * buy_p),
                }
            )
        if sq > 1e-6:
            sold.append(
                {
                    "mol_id": mol_id,
                    "quantity": float(sq),
                    "price_per_gram": sell_p,
                    "revenue": float(sq * sell_p),
                }
            )

    return Solution(
        status=status,
        objective_value=float(objective),
        activated_reactions=activated,
        purchased_molecules=purchased,
        sold_molecules=sold,
    )


def _build_price_lookup(
    molecules: pl.DataFrame,
    referenced: set[str],
    config: SolverConfig,
) -> dict[str, tuple[float, float]]:
    """Build mol_id → (buy_price, sell_price) map.

    Simple heuristic: uses `price_per_gram` for both buy and sell when
    present; falls back to configured defaults otherwise.
    """
    price_lookup: dict[str, tuple[float, float]] = {}
    by_id = {row["mol_id"]: row for row in molecules.iter_rows(named=True)}
    for mol_id in referenced:
        row = by_id.get(mol_id)
        if row and row.get("price_per_gram") is not None:
            p = float(row["price_per_gram"])
            price_lookup[mol_id] = (p, p)
        else:
            price_lookup[mol_id] = (config.default_buy_price, config.default_sell_price)
    return price_lookup


def _make_solver(config: SolverConfig) -> pulp.LpSolver:
    import shutil

    if config.backend == "gurobi":
        try:
            return pulp.GUROBI_CMD(msg=config.verbose)
        except Exception as exc:
            log.warning("Gurobi backend unavailable (%s); falling back to CBC.", exc)

    # Prefer a system-installed CBC (brew install cbc) since pulp's bundled
    # CBC is x86_64-only and won't run on Apple Silicon.
    system_cbc = shutil.which("cbc")
    if system_cbc:
        return pulp.COIN_CMD(path=system_cbc, msg=config.verbose)
    return pulp.PULP_CBC_CMD(msg=config.verbose)


def _safe(name: str) -> str:
    """pulp variable names can't contain certain chars — sanitize."""
    return (
        name.replace(":", "_")
        .replace("/", "_")
        .replace("+", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace("@", "_")
    )
