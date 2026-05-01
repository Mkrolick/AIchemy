"""MILP profit-maximization over the chemo-enzymatic reaction hypergraph.

Sets and parameters
-------------------
    R                       set of reactions
    C                       set of chemicals
    π_c^buy, π_c^sell       buy / sell unit price of chemical c
    a_{c,r}                 molar stoichiometric coefficient of c in reaction r
    η_r                     expected yield of reaction r (from ΔG)
    W_c                     molecular weight of chemical c
    B                       total budget
    ρ_proc, ρ_comp          process / composition royalty rates

Decision variables
------------------
    f_r ∈ ℝ≥0               molar flow through reaction r
    y_r ∈ {0, 1}            whether reaction r is activated
    w_c ∈ {0, 1}            whether chemical c is targeted for sale
    q_c^buy, q_c^sell ∈ ℝ≥0 grams of chemical c bought / sold

Objective
---------
    max  Σ_c π_c^sell · q_c^sell  −  Σ_c π_c^buy · q_c^buy
                                  −  ρ_proc Σ_{r∈R_proc} η_r f_r Σ_{c∈P_r} π_c^sell · a_{c,r} W_c
                                  −  ρ_comp Σ_{c∈C_comp} π_c^sell · q_c^sell

Constraints
-----------
    Mass balance per chemical c:
        q_c^buy + Σ_r (a_{c,r} · W_c · η_r · f_r  for c a PRODUCT of r)
      = q_c^sell + Σ_r (a_{c,r} · W_c · f_r       for c a REACTANT of r)

    Flow activation bounds:
        f_min · y_r  ≤  f_r  ≤  f_max · y_r

    Sellable quantity bound (linearizes w_c · q_c^sell):
        q_c^sell  ≤  M · w_c           where M = B / min_c π_c^buy

    Budget:
        Σ_c π_c^buy · q_c^buy  ≤  B

    Product cardinality (optional):  Σ_c w_c ≤ N_prod
    Reaction cardinality (optional): Σ_r y_r ≤ N_rxn

LP / MILP mode
--------------
The two binaries are gated by exactly the features that need them:
``y_r`` is declared only when ``min_flow > 0`` (forcing the disjunction
``f_r = 0 ∨ f_r ∈ [f_min, f_max]``) or ``max_reactions`` is set; ``w_c``
only when ``max_products`` is set. With none of these and no explicit
override, the model builds as a pure LP — no integer variables, no
flow-activation or sell-switch constraints, and ``f_r`` bounded only by
its variable upBound. ``SolverConfig.lp_mode=True`` forces the LP
relaxation regardless of the other knobs (cardinality caps and
``min_flow`` are silently ignored, with a warning logged).

Mass balance is gram-coherent
-----------------------------
The stoichiometric coefficient `a_{c,r}` from MetaNetX/USPTO is **molar**
(e.g. "2" for the H₂O on either side of `2 H₂O → 2 H₂ + O₂`). The buy /
sell quantities are in **grams** (multiplied by `price_per_gram` in the
objective). To make `a · f` evaluate to grams of c, the model multiplies
each coefficient by the chemical's molecular weight `W_c` (loaded from
`data/processed/molecules_with_mw.parquet`) before constraints are
emitted, so the mass balance enforces gram conservation end-to-end.
`f_r` is therefore "mol of reaction extent" by construction —
`(a_{c,r} · W_c) · f_r` is grams of c on both sides of the equation.

`f_min` / `f_max` (default 1e-3 / 1000) are in mol-extent units; for
typical chemistry W_c=100-500 g/mol, f_max=1000 gives 100-500 kg of
throughput — well above any budget-realistic bound, so the budget
constraint binds rather than f_max.

Reactions whose participants lack a usable W_c (RDKit can't parse the
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

    # Reaction-level composition_covered → chemical-level: any product of a
    # composition-covered reaction is itself composition-covered for royalty.
    # Defensive: only runs when the column is present (license data attached).
    if "composition_covered" in reactions.columns:
        C_comp_ids: set[str] = set()
        for row in reactions.iter_rows(named=True):
            if row.get("composition_covered"):
                for stoich in row["products"]:
                    C_comp_ids.add(stoich["mol_id"])
        molecules = molecules.with_columns(
            pl.col("mol_id").is_in(list(C_comp_ids)).alias("composition_covered")
        )

    # Universe of chemicals C = every chemical id referenced by a surviving reaction.
    C: set[str] = set()
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
        for c, _ in reactants + products:
            C.add(c)
        rxn_meta.append(
            {
                "rxn_id": rxn_id,
                "yield_rate": yield_rate,
                "reactants": reactants,
                "products": products,
                "process_covered": bool(row.get("process_covered") or False),
            }
        )

    # Mass-basis transform: rewrite each (c, a_mol) tuple to (c, a_mol · W_c)
    # so the mass balance is gram-coherent. Drops reactions where any
    # participant lacks a usable W_c (logging the tally). This is
    # unconditional — the dimensionally-inconsistent legacy mode was
    # removed; running the MILP without W would silently allow the solver
    # to violate mass conservation for W-asymmetric reactions.
    W = _build_mw_lookup(molecules)
    rxn_meta, dropped = _rescale_to_grams(rxn_meta, W)
    log.info(
        "[mass_basis] kept=%d dropped=%d (missing W_c for ≥1 participant)",
        len(rxn_meta),
        dropped,
    )
    # Reactions may have been dropped — rebuild C from survivors.
    C = {c for r in rxn_meta for (c, _) in r["reactants"] + r["products"]}

    # Composition-covered chemical set C_comp (drives the composition royalty term).
    C_comp: set[str] = set()
    if "composition_covered" in molecules.columns:
        for row in molecules.iter_rows(named=True):
            if row.get("composition_covered"):
                C_comp.add(row["mol_id"])

    # Price lookup: c → (π_c^buy, π_c^sell).
    price_lookup = _build_price_lookup(molecules, C, config)

    # Decide whether to declare integer variables. The two binaries are
    # independent: y_r is needed for the min-flow disjunction or the
    # reaction cardinality cap; w_c is needed for the product cardinality
    # cap. Dropping a binary also drops every constraint that references
    # it, leaving the model as a continuous LP for that side.
    force_lp = config.lp_mode
    need_y = (not force_lp) and (config.min_flow > 0 or config.max_reactions is not None)
    need_w = (not force_lp) and (config.max_products is not None)
    mode = "MILP" if (need_y or need_w) else "LP"
    log.info(
        "[solver] mode=%s reactions=%d chemicals=%d "
        "(lp_mode=%s, min_flow=%g, max_products=%s, max_reactions=%s)",
        mode,
        len(rxn_meta),
        len(C),
        force_lp,
        config.min_flow,
        config.max_products,
        config.max_reactions,
    )
    if force_lp and (config.max_products is not None or config.max_reactions is not None):
        log.warning(
            "[solver] lp_mode=True overrides cardinality caps "
            "(max_products=%s, max_reactions=%s) — caps will be IGNORED.",
            config.max_products,
            config.max_reactions,
        )

    # Build pulp problem.
    prob = pulp.LpProblem("AIchemy_profit", pulp.LpMaximize)

    # Variables
    f = {
        r["rxn_id"]: pulp.LpVariable(
            f"f_{_safe(r['rxn_id'])}",
            lowBound=0.0,
            upBound=config.max_flow,
        )
        for r in rxn_meta
    }
    # y_r: binary reaction-activation indicator. Declared only when its
    # linking constraint (flow_lb / flow_ub) or its cardinality cap is
    # actually live; otherwise the program runs LP-mode for reactions
    # and f_r is bounded only by its variable upBound (config.max_flow).
    y: dict[str, pulp.LpVariable] | None
    if need_y:
        y = {
            r["rxn_id"]: pulp.LpVariable(
                f"y_{_safe(r['rxn_id'])}",
                cat=pulp.LpBinary,
            )
            for r in rxn_meta
        }
    else:
        y = None
    q_buy = {c: pulp.LpVariable(f"qbuy_{_safe(c)}", lowBound=0.0) for c in C}
    forbidden_sell = set(config.forbidden_sell_molecules)
    q_sell = {
        c: pulp.LpVariable(
            f"qsell_{_safe(c)}",
            lowBound=0.0,
            # Pin forbidden products at 0 by clamping the variable's upper bound.
            # Cheaper than an explicit equality constraint and makes the
            # forbid-list visible in the LP file.
            upBound=0.0 if c in forbidden_sell else None,
        )
        for c in C
    }
    # w_c: binary "is c targeted for sale" indicator. Declared only when
    # the product cardinality cap is live; otherwise the LP determines
    # whether c is sold purely from the sign of q_c^sell at the optimum,
    # and w_c carries no information.
    w: dict[str, pulp.LpVariable] | None
    if need_w:
        w = {c: pulp.LpVariable(f"w_{_safe(c)}", cat=pulp.LpBinary) for c in C}
    else:
        w = None

    # Objective: sell revenue − buy cost − process royalty − composition royalty.
    # Royalty terms are zero whenever (a) license data isn't attached to the
    # input reactions/molecules, or (b) ρ_proc / ρ_comp are 0.
    revenue = pulp.lpSum(price_lookup[c][1] * q_sell[c] for c in C)
    cost = pulp.lpSum(price_lookup[c][0] * q_buy[c] for c in C)
    # Process royalty = ρ_proc · revenue from this reaction's products. Per
    # mol-extent of reaction r, grams of product c produced = a_{c,r}·W_c · η_r,
    # so revenue per extent = Σ_c π_c^sell · a_{c,r}·W_c · η_r. The coefficients
    # already incorporate the W_c multiply from _rescale_to_grams above.
    process_royalty = pulp.lpSum(
        config.r_process
        * sum(price_lookup[c_id][1] * a for (c_id, a) in r["products"])
        * r["yield_rate"]
        * f[r["rxn_id"]]
        for r in rxn_meta
        if r["process_covered"]
    )
    composition_royalty = pulp.lpSum(
        config.r_comp * price_lookup[c][1] * q_sell[c] for c in C if c in C_comp
    )
    prob += (revenue - cost - process_royalty - composition_royalty, "total_profit")

    # Mass balance: for each chemical c, supply = consumption.
    #
    # The naive form (scan all rxn_meta inside the per-chemical loop) is
    # O(|C|·|R|·P) — at full corpus that's ~1.3M × 365K × ~5 ≈ 5e12
    # comparisons and the model build dominates wall-clock (5+ minutes per
    # cell). Pre-index participants once for O(|C| + |R|·P) total (~2
    # million ops), making the build run in seconds.
    producers: dict[str, list[tuple[str, float, float]]] = {}
    consumers: dict[str, list[tuple[str, float]]] = {}
    for r in rxn_meta:
        rxn_id = r["rxn_id"]
        yld = r["yield_rate"]
        for c_id, a in r["products"]:
            producers.setdefault(c_id, []).append((rxn_id, a, yld))
        for c_id, a in r["reactants"]:
            consumers.setdefault(c_id, []).append((rxn_id, a))

    for c in C:
        supply = q_buy[c] + pulp.lpSum(
            a * yld * f[rxn_id] for (rxn_id, a, yld) in producers.get(c, [])
        )
        consumption = q_sell[c] + pulp.lpSum(
            a * f[rxn_id] for (rxn_id, a) in consumers.get(c, [])
        )
        prob += supply == consumption, f"mass_balance_{_safe(c)}"

    # Flow activation bounds — only meaningful when y_r exists. Without
    # y_r, f_r >= 0 (variable lowBound) and f_r <= max_flow (variable
    # upBound) already constrain the flow; the min-flow disjunction is
    # gone by design (LP-mode for reactions).
    if need_y:
        assert y is not None  # for type checker
        for r in rxn_meta:
            rxn_id = r["rxn_id"]
            prob += f[rxn_id] >= config.min_flow * y[rxn_id], f"flow_lb_{_safe(rxn_id)}"
            prob += f[rxn_id] <= config.max_flow * y[rxn_id], f"flow_ub_{_safe(rxn_id)}"

    # Sellable-quantity bound (w_c switches q_c^sell on/off). Only
    # meaningful when w_c exists. After mass-basis, q_sell is in grams:
    # B / min π_c^buy is the tightest valid bound, since Σ q_buy ≤
    # B / min π_c^buy and balanced reactions yield Σ q_sell ≤ Σ q_buy
    # under η ≤ 1. The earlier `max_flow · 100` was in mol-extent units,
    # not grams — silently clamping sales in high-W or cheap-input
    # regimes. Skip non-positive buy prices to avoid div-by-zero on
    # degenerate data; if no positive price exists at all, fall back to
    # a finite huge value.
    if need_w:
        assert w is not None  # for type checker
        positive_buys = [bp for (bp, _) in price_lookup.values() if bp > 0]
        sell_big_m = (
            config.budget / min(positive_buys) if positive_buys else config.budget * 1e6
        )
        for c in C:
            prob += q_sell[c] <= sell_big_m * w[c], f"sell_switch_{_safe(c)}"

    # Budget
    prob += (
        pulp.lpSum(price_lookup[c][0] * q_buy[c] for c in C) <= config.budget,
        "budget",
    )

    # Product cardinality. Only meaningful when w_c exists; lp_mode=True
    # drops w_c and silently ignores this cap (warning logged at solve
    # start).
    if config.max_products is not None and need_w:
        assert w is not None  # for type checker
        prob += (
            pulp.lpSum(w[c] for c in C) <= config.max_products,
            "product_cap",
        )

    # Reaction cardinality (synthesis-route length cap). Only meaningful
    # when y_r exists; lp_mode=True drops y_r and silently ignores this
    # cap (a warning is logged at solve start).
    if config.max_reactions is not None and need_y:
        assert y is not None  # for type checker
        prob += (
            pulp.lpSum(y[r["rxn_id"]] for r in rxn_meta) <= config.max_reactions,
            "reaction_cap",
        )

    # Solve
    solver = _make_solver(config)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    objective = pulp.value(prob.objective) or 0.0

    # Extract activated reactions + non-trivial buys/sells. Floor the
    # threshold at 1e-9 so LP-mode runs (min_flow=0) don't dump every
    # epsilon-flow into the result.
    activation_threshold = max(config.min_flow / 2, 1e-9)
    activated: list[dict[str, Any]] = []
    for r in rxn_meta:
        val = pulp.value(f[r["rxn_id"]]) or 0.0
        if val > activation_threshold:
            activated.append(
                {"rxn_id": r["rxn_id"], "flow": float(val), "yield_rate": r["yield_rate"]}
            )

    purchased: list[dict[str, Any]] = []
    sold: list[dict[str, Any]] = []
    for c in C:
        bq = pulp.value(q_buy[c]) or 0.0
        sq = pulp.value(q_sell[c]) or 0.0
        buy_p, sell_p = price_lookup[c]
        if bq > 1e-6:
            purchased.append(
                {
                    "mol_id": c,
                    "quantity": float(bq),
                    "price_per_gram": buy_p,
                    "cost": float(bq * buy_p),
                }
            )
        if sq > 1e-6:
            sold.append(
                {
                    "mol_id": c,
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
    C: set[str],
    config: SolverConfig,
) -> dict[str, tuple[float, float]]:
    """Build c → (π_c^buy, π_c^sell) map.

    Priced chemicals use ``price_per_gram`` for both buy and sell. Unpriced
    chemicals get a conservative pair derived from the empirical price
    distribution: max(known) for buy, min(known) for sell. This prevents
    the solver from "discovering profit" on chemicals whose true price is
    unknown — any pure-unpriced trade has objective ≤ 0. Falls back to the
    configured ``default_buy_price`` / ``default_sell_price`` only when no
    priced chemical exists at all.
    """
    by_id = {row["mol_id"]: row for row in molecules.iter_rows(named=True)}

    known_prices = [
        float(by_id[c]["price_per_gram"])
        for c in C
        if by_id.get(c) and by_id[c].get("price_per_gram") is not None
    ]
    if known_prices:
        unpriced_buy = max(known_prices)
        unpriced_sell = min(known_prices)
    else:
        unpriced_buy = config.default_buy_price
        unpriced_sell = config.default_sell_price

    price_lookup: dict[str, tuple[float, float]] = {}
    for c in C:
        row = by_id.get(c)
        if row and row.get("price_per_gram") is not None:
            p = float(row["price_per_gram"])
            price_lookup[c] = (p, p)
        else:
            price_lookup[c] = (unpriced_buy, unpriced_sell)
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

    Distinct multi-char replacements so chemically-distinct ids that
    differ only in disallowed chars (e.g., [H+] vs [H-]) don't collapse
    to the same name and trigger PuLP's "overlapping constraint names"
    error when both appear in mass_balance_<c> constraints.
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
    """Build a {c: W_c} dict for the mass-basis rescale.

    Prefers a precomputed `mol_weight` column (produced by
    `aichemy augment molecule-weights`). When that column isn't present
    — e.g., in unit tests that pass a tiny synthetic molecules table —
    falls back to computing W_c on the fly from `canonical_smiles` via
    RDKit. Tests stay self-contained without forcing fixtures to carry
    precomputed W_c.
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
    side: list[tuple[str, float]], W: dict[str, float | None]
) -> tuple[list[tuple[str, float]], bool]:
    """Multiply each (c, a_mol) tuple's coefficient by W_c.

    Returns (rescaled_list, ok). `ok` is False if any participant lacks
    a usable W_c (None, NaN, or non-positive); the caller is expected to
    drop the whole reaction in that case.
    """
    out: list[tuple[str, float]] = []
    for c_id, a in side:
        w_c = W.get(c_id)
        if w_c is None or math.isnan(w_c) or w_c <= 0:
            return [], False
        out.append((c_id, a * w_c))
    return out, True


def _rescale_to_grams(
    rxn_meta: list[dict[str, Any]], W: dict[str, float | None]
) -> tuple[list[dict[str, Any]], int]:
    """Rewrite all reactant/product coefs by W_c. Drop reactions where any
    participant lacks a usable W_c. Returns (kept_rxn_meta, n_dropped)."""
    kept: list[dict[str, Any]] = []
    dropped = 0
    for r in rxn_meta:
        scaled_react, ok_react = _scale_side(r["reactants"], W)
        scaled_prod, ok_prod = _scale_side(r["products"], W)
        if not (ok_react and ok_prod):
            dropped += 1
            continue
        kept.append({**r, "reactants": scaled_react, "products": scaled_prod})
    return kept, dropped
