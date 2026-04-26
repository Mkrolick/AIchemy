"""Scientific-correctness validation for the MILP solver.

Unlike the isolated unit tests in `tests/unit/test_solver.py`, these cases
either (a) have a closed-form optimum computed by hand that the solver
must match numerically, or (b) are real-data sanity checks with known
bounds (profit ≥ 0, activated reactions ⊆ balanced, etc.).
"""

from __future__ import annotations

import polars as pl
import pytest

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _molecules(prices: dict[str, float | None]) -> pl.DataFrame:
    rows = [
        {
            "mol_id": mid,
            "canonical_smiles": "C",
            "inchi_key": f"KEY{mid}",
            "carbon_count": 2,
            "price_per_gram": price,
            "source_refs": [mid],
        }
        for mid, price in prices.items()
    ]
    return pl.DataFrame(rows, schema_overrides={"price_per_gram": pl.Float64})


def _reactions(rows: list[dict]) -> pl.DataFrame:
    for r in rows:
        r.setdefault("yield_rate", 1.0)  # use 1.0 so arithmetic is trivial
        r.setdefault("type", "chemical")
        r.setdefault("balanced", True)
        r.setdefault("rdkit_balanced", True)
        r.setdefault("source", "test")
        r.setdefault("delta_g", None)
        r.setdefault("reaction_smiles", ">>")
        r.setdefault("ec_class", None)
    return pl.DataFrame(rows)


def test_hand_solved_linear_network() -> None:
    """Buy A @ $1/g, convert A -> B (yield 1.0), sell B @ $10/g, budget=$100.

    Closed-form optimum:
      - With yield=1.0 and budget=100, we can buy up to 100g of A (cost $100).
      - 100g A -> 100g B (no coefficient; yield=1.0).
      - Revenue: 100g × $10/g = $1000.
      - Profit = $1000 − $100 = $900.
      - max_flow caps f_r at 1000, so we're not flow-limited.
    """
    reactions = _reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 1.0,
            },
        ]
    )
    molecules = _molecules({"A": 1.0, "B": 10.0})
    cfg = SolverConfig(budget=100.0, max_flow=10_000.0)
    solution = build_and_solve(reactions, molecules, cfg)

    assert solution.status == "Optimal"
    # Hand-computed optimum: $900
    assert solution.objective_value == pytest.approx(900.0, abs=1e-3)

    # Exactly 100g of A should be purchased
    purchased_a = next((p for p in solution.purchased_molecules if p["mol_id"] == "A"), None)
    assert purchased_a is not None
    assert purchased_a["quantity"] == pytest.approx(100.0, abs=1e-3)

    # Exactly 100g of B should be sold
    sold_b = next((s for s in solution.sold_molecules if s["mol_id"] == "B"), None)
    assert sold_b is not None
    assert sold_b["quantity"] == pytest.approx(100.0, abs=1e-3)


def test_hand_solved_with_yield_loss() -> None:
    """Yield 0.5 means 100g A -> 50g B. Revenue = 50×$10 = $500. Profit = $400."""
    reactions = _reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 0.5,
            },
        ]
    )
    molecules = _molecules({"A": 1.0, "B": 10.0})
    cfg = SolverConfig(budget=100.0, max_flow=10_000.0)
    solution = build_and_solve(reactions, molecules, cfg)

    assert solution.status == "Optimal"
    assert solution.objective_value == pytest.approx(400.0, abs=1e-3)


def test_unprofitable_network_solves_to_zero() -> None:
    """Buy A @ $10/g, sell B @ $1/g with yield 1.0. No flow should activate.

    Profit per g: revenue 1×1 − cost 1×10 = −$9. Best action: do nothing.
    """
    reactions = _reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
            },
        ]
    )
    molecules = _molecules({"A": 10.0, "B": 1.0})
    solution = build_and_solve(reactions, molecules, SolverConfig(budget=100.0))

    assert solution.status == "Optimal"
    # Objective must be zero (do-nothing is always a feasible solution).
    assert solution.objective_value == pytest.approx(0.0, abs=1e-3)
    # No reactions should activate.
    assert len(solution.activated_reactions) == 0


def test_solver_prefers_higher_yield_route() -> None:
    """Two routes A -> B: r1 with yield 0.5, r2 with yield 0.9.

    Both cost the same input; r2 is strictly better. Expect r2 activated
    and r1 not activated.
    """
    reactions = _reactions(
        [
            {
                "rxn_id": "r_low",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 0.5,
            },
            {
                "rxn_id": "r_high",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 0.9,
            },
        ]
    )
    molecules = _molecules({"A": 1.0, "B": 10.0})
    solution = build_and_solve(reactions, molecules, SolverConfig(budget=100.0, max_flow=10_000.0))

    assert solution.status == "Optimal"
    activated_ids = {r["rxn_id"] for r in solution.activated_reactions}
    assert "r_high" in activated_ids
    assert "r_low" not in activated_ids

    # Profit: buy 100g A for $100, yield 0.9 -> 90g B, sell for $900.
    # Net profit: $900 - $100 = $800.
    assert solution.objective_value == pytest.approx(800.0, abs=1e-3)


def test_activated_reactions_are_always_from_balanced_set() -> None:
    """Invariant: no unbalanced reaction is ever in the activated set."""
    reactions = _reactions(
        [
            {
                "rxn_id": "r_bal",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "balanced": True,
                "rdkit_balanced": True,
            },
            {
                "rxn_id": "r_unbal",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "C", "coefficient": 1.0}],
                "balanced": False,
                "rdkit_balanced": False,
            },
        ]
    )
    molecules = _molecules({"A": 1.0, "B": 10.0, "C": 100.0})  # r_unbal would be more profitable
    solution = build_and_solve(reactions, molecules, SolverConfig(budget=100.0))
    activated = {r["rxn_id"] for r in solution.activated_reactions}
    assert "r_unbal" not in activated


def test_solver_is_deterministic() -> None:
    """Same input → same output (important for reproducibility)."""
    reactions = _reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 0.8,
            },
        ]
    )
    molecules = _molecules({"A": 1.0, "B": 10.0})
    cfg = SolverConfig(budget=100.0, max_flow=10_000.0)
    s1 = build_and_solve(reactions, molecules, cfg)
    s2 = build_and_solve(reactions, molecules, cfg)
    assert s1.objective_value == pytest.approx(s2.objective_value, abs=1e-6)
    assert len(s1.activated_reactions) == len(s2.activated_reactions)
