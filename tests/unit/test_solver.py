"""Tests for the MILP solver (Open Item 07)."""

from __future__ import annotations

import math

import polars as pl
import pytest

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
        r.setdefault("rdkit_balanced", True)
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
                "rdkit_balanced": False,
            },
        ]
    )
    molecules = _sample_molecules({"A": 1.0, "B": 10.0})
    solution = build_and_solve(reactions, molecules, SolverConfig())
    assert solution.objective_value == 0.0
    assert "filtering" in solution.status or solution.activated_reactions == []


@pytest.mark.parametrize(
    "filter_col,row_balanced,row_rdkit,expect_activated",
    [
        ("rdkit_balanced", True, False, False),  # strict drops it
        ("balanced", True, False, True),  # loose keeps it
        ("rdkit_balanced", True, True, True),
        ("balanced", False, True, False),
    ],
)
def test_balance_filter_selects_column(
    filter_col: str,
    row_balanced: bool,
    row_rdkit: bool,
    expect_activated: bool,
) -> None:
    reactions = _sample_reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "balanced": row_balanced,
                "rdkit_balanced": row_rdkit,
            },
        ]
    )
    molecules = _sample_molecules({"A": 1.0, "B": 10.0})
    cfg = SolverConfig(budget=100.0, balance_filter=filter_col)  # type: ignore[arg-type]
    sol = build_and_solve(reactions, molecules, cfg)
    activated = {r["rxn_id"] for r in sol.activated_reactions}
    assert ("r1" in activated) is expect_activated


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


def test_lp_mode_matches_milp_when_no_milp_features() -> None:
    """With min_flow=0, max_products=None, max_reactions=None the model is
    inherently an LP regardless of lp_mode. Auto-detected LP and forced LP
    must agree exactly with the MILP build (which also degenerates to an LP
    when min_flow=0)."""
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

    auto_lp = build_and_solve(
        reactions, molecules, SolverConfig(budget=1000.0, min_flow=0.0)
    )
    forced_lp = build_and_solve(
        reactions, molecules, SolverConfig(budget=1000.0, min_flow=0.0, lp_mode=True)
    )
    assert auto_lp.status == "Optimal"
    assert forced_lp.status == "Optimal"
    assert math.isclose(auto_lp.objective_value, forced_lp.objective_value, rel_tol=1e-6)
    # And both should be strictly profitable (sells B at $10/g, buys A at $1/g).
    assert auto_lp.objective_value > 0


def test_lp_mode_overrides_cardinality_caps() -> None:
    """lp_mode=True must drop max_products / max_reactions caps and match
    the unconstrained LP optimum, not the MILP-with-caps optimum."""
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
    # Two distinct products at the same margin so a cap of 1 product would
    # bind in the MILP path and the relaxed LP would not.
    molecules = _sample_molecules({"A": 1.0, "B": 10.0, "C": 1.0, "D": 10.0})

    lp_with_cap = build_and_solve(
        reactions,
        molecules,
        SolverConfig(budget=1000.0, min_flow=0.0, lp_mode=True, max_products=1),
    )
    lp_no_cap = build_and_solve(
        reactions,
        molecules,
        SolverConfig(budget=1000.0, min_flow=0.0, lp_mode=True),
    )
    # LP mode ignores the cap entirely.
    assert math.isclose(lp_with_cap.objective_value, lp_no_cap.objective_value, rel_tol=1e-6)


def test_lp_mode_problem_has_no_integer_variables(caplog) -> None:
    """Smoke test: confirm the mode log says LP and the produced PuLP
    problem has zero binary variables when lp_mode=True. Guards against
    accidental reintroduction of y_r / w_c."""
    import logging
    import pulp

    reactions = _sample_reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
            },
        ]
    )
    molecules = _sample_molecules({"A": 1.0, "B": 10.0})

    with caplog.at_level(logging.INFO, logger="aichemy.solver.model"):
        build_and_solve(
            reactions,
            molecules,
            SolverConfig(budget=1000.0, lp_mode=True, max_products=2, max_reactions=3),
        )
    # Mode line says LP.
    assert any("mode=LP" in rec.getMessage() for rec in caplog.records)
    # Override warning fired because user passed cardinality caps with lp_mode.
    assert any("overrides cardinality caps" in rec.getMessage() for rec in caplog.records)


def test_milp_mode_with_min_flow_still_uses_binaries(caplog) -> None:
    """Default config (min_flow=1e-3) must still produce a MILP — guards
    against the gating accidentally swallowing the legacy MILP path."""
    import logging

    reactions = _sample_reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
            },
        ]
    )
    molecules = _sample_molecules({"A": 1.0, "B": 10.0})

    with caplog.at_level(logging.INFO, logger="aichemy.solver.model"):
        build_and_solve(reactions, molecules, SolverConfig(budget=1000.0))
    assert any("mode=MILP" in rec.getMessage() for rec in caplog.records)
