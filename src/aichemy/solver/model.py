"""MILP profit-maximization over the chemo-enzymatic reaction hypergraph.

Follows the formulation from `proposal.md`:

Decision variables
------------------
    f_r ∈ ℝ≥0         flow through reaction r (see "Mass-balance basis" below)
    y_r ∈ {0, 1}      whether reaction r is activated
    w_m ∈ {0, 1}      whether molecule m is targeted for sale
    q_buy_m, q_sell_m ∈ ℝ≥0  quantities purchased / sold (in grams)

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

Mass balance is gram-coherent
-----------------------------
The stoichiometric coefficient `a_r,m` from MetaNetX/USPTO is **molar**
(e.g. "2" for the H₂O on either side of `2 H₂O → 2 H₂ + O₂`). The buy /
sell quantities are in **grams** (multiplied by `price_per_gram` in the
objective). To make `a · f` evaluate to grams of m, the model
multiplies each coefficient by the participant's molecular weight
(loaded from `data/processed/molecules_with_mw.parquet`) before
constraints are emitted, so the mass balance enforces gram conservation
end-to-end. `f_r` is therefore "mol of reaction extent" by construction
— `(a_r,m · MW_m) · f_r` is grams of m on both sides of the equation.

`min_flow` / `max_flow` (default 1e-3 / 1000) are in mol-extent units;
for typical chemistry MW=100-500 g/mol, max_flow=1000 gives 100-500 kg
of throughput — well above any budget-realistic bound, so the budget
constraint binds rather than max_flow.

Reactions whose participants lack a usable MW (RDKit can't parse the
SMILES, or the molecules table doesn't carry one) are dropped at
model-build time with a tally logged. In practice this affects only
abstract MetaNetX entries with no canonical_smiles (BIOMASS-class
sinks, polymer-pseudo-metabolites) — never any rdkit_balanced reaction
on the curated full-corpus dataset.
"""

from __future__ import annotations

import logging
import math
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
    # Defensive: only runs when the column is present (license data attached).
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
        # Fallback applies only when the value is missing (None) — `or` would
        # also swallow a legitimate yield of 0.0, silently rewriting a "this
        # reaction never produces product" row into the prior-mean and inviting
        # phantom-profit solutions on it.
        yr = row.get("yield_rate")
        yield_rate = 0.85 if yr is None else yr
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

    # Mass-basis transform: rewrite each (mol_id, coef_mol) tuple to
    # (mol_id, coef_mol * MW_m) so the mass balance is gram-coherent. Drops
    # reactions where any participant lacks a usable MW (logging the tally).
    # This is unconditional — the dimensionally-inconsistent legacy mode
    # was removed; running the MILP without MW would silently allow the
    # solver to violate mass conservation for MW-asymmetric reactions.
    mw_lookup = _build_mw_lookup(molecules)
    rxn_meta, dropped = _rescale_to_grams(rxn_meta, mw_lookup)
    log.info(
        "[mass_basis] kept=%d dropped=%d (missing MW for ≥1 participant)",
        len(rxn_meta),
        dropped,
    )
    # Reactions may have been dropped — rebuild `referenced` from survivors.
    referenced = {mid for m in rxn_meta for (mid, _) in m["reactants"] + m["products"]}

    # Composition-covered molecule set (drives the composition royalty term).
    composition_covered: set[str] = set()
    if "composition_covered" in molecules.columns:
        for r in molecules.iter_rows(named=True):
            if r.get("composition_covered"):
                composition_covered.add(r["mol_id"])

    # Price lookup: molecule mol_id → (buy_price, sell_price).
    price_lookup = _build_price_lookup(molecules, referenced, config)

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
    forbidden_sell = set(config.forbidden_sell_molecules)
    q_sell = {
        mol_id: pulp.LpVariable(
            f"qsell_{_safe(mol_id)}",
            lowBound=0.0,
            # Pin forbidden products at 0 by clamping the variable's upper bound.
            # Cheaper than an explicit equality constraint and makes the
            # forbid-list visible in the LP file.
            upBound=0.0 if mol_id in forbidden_sell else None,
        )
        for mol_id in referenced
    }
    w = {mol_id: pulp.LpVariable(f"w_{_safe(mol_id)}", cat=pulp.LpBinary) for mol_id in referenced}

    # Objective: sell revenue − buy cost − process royalty − composition royalty.
    # Royalty terms are zero whenever (a) license data isn't attached to the
    # input reactions/molecules, or (b) config.r_process / config.r_comp are 0.
    revenue = pulp.lpSum(price_lookup[m][1] * q_sell[m] for m in referenced)
    cost = pulp.lpSum(price_lookup[m][0] * q_buy[m] for m in referenced)
    # Process royalty = r_process · revenue from this reaction's products.
    # Per mol-extent of reaction r, grams of product m produced = coef_grams[m] · η_r,
    # so revenue per extent = Σ price_sell[m] · coef_grams[m] · η_r. Coef_grams
    # already incorporates the MW multiply from _rescale_to_grams above.
    process_royalty = pulp.lpSum(
        config.r_process
        * sum(price_lookup[mid][1] * coef for (mid, coef) in m["products"])
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
    #
    # The naive form (scan all rxn_meta inside the per-molecule loop) is
    # O(M·R·P) — at full corpus that's ~1.3M × 365K × ~5 ≈ 5e12 comparisons
    # and the model build dominates wall-clock (5+ minutes per cell). Pre-
    # index participants once for O(M + R·P) total (~2 million ops), making
    # the build run in seconds.
    producers: dict[str, list[tuple[str, float, float]]] = {}
    consumers: dict[str, list[tuple[str, float]]] = {}
    for m in rxn_meta:
        rxn_id = m["rxn_id"]
        yld = m["yield_rate"]
        for mid, coef in m["products"]:
            producers.setdefault(mid, []).append((rxn_id, coef, yld))
        for mid, coef in m["reactants"]:
            consumers.setdefault(mid, []).append((rxn_id, coef))

    for mol_id in referenced:
        supply = q_buy[mol_id] + pulp.lpSum(
            coef * yld * f[rxn_id] for (rxn_id, coef, yld) in producers.get(mol_id, [])
        )
        consumption = q_sell[mol_id] + pulp.lpSum(
            coef * f[rxn_id] for (rxn_id, coef) in consumers.get(mol_id, [])
        )
        prob += supply == consumption, f"mass_balance_{_safe(mol_id)}"

    # Flow activation bounds
    for m in rxn_meta:
        rxn_id = m["rxn_id"]
        prob += f[rxn_id] >= config.min_flow * y[rxn_id], f"flow_lb_{_safe(rxn_id)}"
        prob += f[rxn_id] <= config.max_flow * y[rxn_id], f"flow_ub_{_safe(rxn_id)}"

    # Sellable-quantity bound (w_m switches sell_m on/off). After mass-
    # basis, q_sell is in grams: budget/min_buy_price is the tightest
    # valid bound, since Σ q_buy ≤ budget/min_buy_price and balanced
    # reactions yield Σ q_sell ≤ Σ q_buy under η ≤ 1. The earlier
    # `max_flow · 100` was in mol-extent units, not grams — silently
    # clamping sales in high-MW or cheap-input regimes. Skip non-positive
    # buy prices to avoid div-by-zero on degenerate data; if no positive
    # price exists at all, fall back to a finite huge value.
    positive_buys = [bp for (bp, _) in price_lookup.values() if bp > 0]
    sell_big_m = config.budget / min(positive_buys) if positive_buys else config.budget * 1e6
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

    # Reaction cardinality (synthesis-route length cap)
    if config.max_reactions is not None:
        prob += (
            pulp.lpSum(y[m["rxn_id"]] for m in rxn_meta) <= config.max_reactions,
            "reaction_cap",
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

    Priced molecules use ``price_per_gram`` for both buy and sell. Unpriced
    molecules get a conservative pair derived from the empirical price
    distribution: max(known) for buy, min(known) for sell. This prevents
    the solver from "discovering profit" on molecules whose true price is
    unknown — any pure-unpriced trade has objective ≤ 0. Falls back to the
    configured ``default_buy_price`` / ``default_sell_price`` only when no
    priced molecule exists at all.
    """
    by_id = {row["mol_id"]: row for row in molecules.iter_rows(named=True)}

    known_prices = [
        float(by_id[m]["price_per_gram"])
        for m in referenced
        if by_id.get(m) and by_id[m].get("price_per_gram") is not None
    ]
    if known_prices:
        unpriced_buy = max(known_prices)
        unpriced_sell = min(known_prices)
    else:
        unpriced_buy = config.default_buy_price
        unpriced_sell = config.default_sell_price

    price_lookup: dict[str, tuple[float, float]] = {}
    for mol_id in referenced:
        row = by_id.get(mol_id)
        if row and row.get("price_per_gram") is not None:
            p = float(row["price_per_gram"])
            price_lookup[mol_id] = (p, p)
        else:
            price_lookup[mol_id] = (unpriced_buy, unpriced_sell)
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
    """pulp variable names can't contain certain chars — sanitize.

    Distinct multi-char replacements so chemically-distinct mol_ids that
    differ only in disallowed chars (e.g., [H+] vs [H-]) don't collapse
    to the same name and trigger PuLP's "overlapping constraint names"
    error when both appear in mass_balance_<mol_id> constraints.
    """
    return (
        name.replace(":", "_co_")
        .replace("/", "_sl_")
        .replace("+", "_pl_")
        .replace("-", "_mi_")
        .replace(".", "_dt_")
        .replace("@", "_at_")
    )


def _build_mw_lookup(molecules: pl.DataFrame) -> dict[str, float | None]:
    """Build a {mol_id: mol_weight} dict for the mass_basis rescale.

    Prefers a precomputed `mol_weight` column (produced by
    `aichemy augment molecule-weights`). When that column isn't present
    — e.g., in unit tests that pass a tiny synthetic molecules table —
    falls back to computing MW on the fly from `canonical_smiles` via
    RDKit. Tests stay self-contained without forcing fixtures to carry
    precomputed MW.
    """
    if "mol_weight" in molecules.columns:
        return {row["mol_id"]: row["mol_weight"] for row in molecules.iter_rows(named=True)}
    if "canonical_smiles" not in molecules.columns:
        return {}
    # Lazy import — only paid when fixtures lack mol_weight.
    from aichemy.preprocessing.augment.molecule_weights import augment_with_mw

    augmented = augment_with_mw(molecules.select(["mol_id", "canonical_smiles"]))
    return {row["mol_id"]: row["mol_weight"] for row in augmented.iter_rows(named=True)}


def _scale_side(
    side: list[tuple[str, float]], mw: dict[str, float | None]
) -> tuple[list[tuple[str, float]], bool]:
    """Multiply each (mol_id, coef_mol) tuple's coef by MW[mol_id].

    Returns (rescaled_list, ok). `ok` is False if any participant lacks
    a usable MW (None, NaN, or non-positive); the caller is expected to
    drop the whole reaction in that case.
    """
    out: list[tuple[str, float]] = []
    for mid, coef in side:
        w = mw.get(mid)
        if w is None or math.isnan(w) or w <= 0:
            return [], False
        out.append((mid, coef * w))
    return out, True


def _rescale_to_grams(
    rxn_meta: list[dict[str, Any]], mw: dict[str, float | None]
) -> tuple[list[dict[str, Any]], int]:
    """Rewrite all reactant/product coefs by MW. Drop reactions where any
    participant lacks a usable MW. Returns (kept_rxn_meta, n_dropped)."""
    kept: list[dict[str, Any]] = []
    dropped = 0
    for m in rxn_meta:
        scaled_r, ok_r = _scale_side(m["reactants"], mw)
        scaled_p, ok_p = _scale_side(m["products"], mw)
        if not (ok_r and ok_p):
            dropped += 1
            continue
        kept.append({**m, "reactants": scaled_r, "products": scaled_p})
    return kept, dropped
