"""Tests for the MILP solver (Open Item 07)."""

from __future__ import annotations

import polars as pl

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _sample_molecules(prices: dict[str, float]) -> pl.DataFrame:
    rows = [
        {
            "mol_id": mid,
            "canonical_smiles": "C",
            "inchi_key": f"KEY{mid}",
            "carbon_count": 1,
            "price_per_gram": prices.get(mid),
            "source_refs": [mid],
        }
        for mid in {"A", "B", "C", "D"}
    ]
    return pl.DataFrame(rows, schema_overrides={"price_per_gram": pl.Float64})


def _sample_reactions(reactions: list[dict]) -> pl.DataFrame:
    # Pad with required fields.
    for r in reactions:
        r.setdefault("yield_rate", 0.9)
        r.setdefault("type", "chemical")
        r.setdefault("balanced", True)
        r.setdefault("source", "test")
        r.setdefault("delta_g", None)
        r.setdefault("reaction_smiles", ">>")
        r.setdefault("ec_class", None)
    return pl.DataFrame(reactions)


def test_empty_reactions_returns_trivial_solution() -> None:
    solution = build_and_solve(
        _sample_reactions([]),
        _sample_molecules({}),
        SolverConfig(),
    )
    assert solution.objective_value == 0.0
    assert solution.activated_reactions == []


def test_profitable_single_reaction_gets_activated() -> None:
    # A (cheap $1/g) -> B ($10/g) via r1 with yield 0.9 gives profit per-flow.
    reactions = _sample_reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 0.9,
            },
        ]
    )
    molecules = _sample_molecules({"A": 1.0, "B": 10.0})
    solution = build_and_solve(reactions, molecules, SolverConfig(budget=1000.0))
    assert solution.status == "Optimal"
    assert len(solution.activated_reactions) == 1
    assert solution.activated_reactions[0]["rxn_id"] == "r1"
    # Profit should be positive (sells B at $10/g, buys A at $1/g, yield 0.9).
    assert solution.objective_value > 0


def test_unbalanced_reactions_excluded() -> None:
    reactions = _sample_reactions(
        [
            {
                "rxn_id": "r_unbal",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "balanced": False,
            },
        ]
    )
    molecules = _sample_molecules({"A": 1.0, "B": 10.0})
    solution = build_and_solve(reactions, molecules, SolverConfig())
    assert solution.objective_value == 0.0
    assert "filtering" in solution.status or solution.activated_reactions == []


def test_budget_constraint_caps_purchases() -> None:
    reactions = _sample_reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 0.9,
            },
        ]
    )
    # Buying A costs $1/g; with budget=5 we can only buy 5g.
    molecules = _sample_molecules({"A": 1.0, "B": 10.0})
    solution = build_and_solve(reactions, molecules, SolverConfig(budget=5.0))
    # Total cost of A purchases must be ≤ 5.
    total_cost = sum(p["cost"] for p in solution.purchased_molecules)
    assert total_cost <= 5.0 + 1e-6


def test_max_products_cardinality() -> None:
    # Two independent profitable reactions; cap max_products=1.
    reactions = _sample_reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
            },
            {
                "rxn_id": "r2",
                "reactants": [{"mol_id": "C", "coefficient": 1.0}],
                "products": [{"mol_id": "D", "coefficient": 1.0}],
            },
        ]
    )
    molecules = _sample_molecules({"A": 1.0, "B": 10.0, "C": 1.0, "D": 10.0})
    solution = build_and_solve(reactions, molecules, SolverConfig(budget=1000.0, max_products=1))
    # Only one product can be sold.
    assert len(solution.sold_molecules) <= 1
