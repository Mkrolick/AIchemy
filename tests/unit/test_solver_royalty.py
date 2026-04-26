"""Royalty terms in the MILP objective (Task 17).

Three invariants:
1. Zero-royalty equivalence — same objective as legacy when r_process=r_comp=0.
2. Process royalty reduces objective by exactly r_process · price_sell · η · f.
3. Composition royalty reduces objective by exactly r_comp · price_sell · q_sell.
"""

from __future__ import annotations

import polars as pl

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _two_reaction_fixture(*, process_covered: bool, composition_covered: bool):
    """Single reaction A + B → C; price A=1, B=1, C=10; yield 1.0; balanced=True."""
    reactions = pl.DataFrame(
        {
            "rxn_id": ["RX1"],
            "yield_rate": [1.0],
            "reactants": [
                [
                    {"mol_id": "A", "coefficient": 1.0},
                    {"mol_id": "B", "coefficient": 1.0},
                ]
            ],
            "products": [[{"mol_id": "C", "coefficient": 1.0}]],
            "rdkit_balanced": [True],
            "balanced": [True],
            "patent_active": [process_covered or composition_covered],
            "process_covered": [process_covered],
            "composition_covered": [composition_covered],
        }
    )
    molecules = pl.DataFrame(
        {
            "mol_id": ["A", "B", "C"],
            "price_per_gram": [1.0, 1.0, 10.0],
        }
    )
    return reactions, molecules


def test_zero_royalty_matches_baseline_objective():
    """At r_process=r_comp=0, royalty terms are no-ops; objective matches legacy."""
    reactions, molecules = _two_reaction_fixture(process_covered=True, composition_covered=True)
    sol_zero = build_and_solve(reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.0))
    # Drop license columns to simulate the pre-licensing solver path.
    reactions_legacy = reactions.drop(["patent_active", "process_covered", "composition_covered"])
    sol_legacy = build_and_solve(reactions_legacy, molecules, SolverConfig())
    assert abs(sol_zero.objective_value - sol_legacy.objective_value) < 1e-3


def test_process_royalty_reduces_objective_by_expected_amount():
    """At r_process=0.5, process-covered reaction pays 0.5 · price_sell[product] · η · f."""
    reactions, molecules = _two_reaction_fixture(process_covered=True, composition_covered=False)
    sol_no = build_and_solve(reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.0))
    sol_p = build_and_solve(reactions, molecules, SolverConfig(r_process=0.5, r_comp=0.0))
    flow = sol_no.activated_reactions[0]["flow"]
    expected_delta = 0.5 * 10.0 * 1.0 * flow  # rate · price[C] · yield · f
    assert abs((sol_no.objective_value - sol_p.objective_value) - expected_delta) < 1e-2


def test_composition_royalty_reduces_objective_by_expected_amount():
    """At r_comp=0.5, composition-covered product pays 0.5 · price_sell · q_sell.

    Uses a tight max_flow=1 / budget=2 config so the only economic activity is:
    buy 1 A + 1 B → produce 1 C → sell 1 C. Eliminates the LP's degenerate
    buy-resell of C (which would inflate q_sell[C] and make the delta
    sensitive to the optimizer's tie-breaking).
    """
    reactions, molecules = _two_reaction_fixture(process_covered=False, composition_covered=True)
    base = {"max_flow": 1.0, "budget": 2.0}
    sol_no = build_and_solve(reactions, molecules, SolverConfig(**base, r_process=0.0, r_comp=0.0))
    sol_c = build_and_solve(reactions, molecules, SolverConfig(**base, r_process=0.0, r_comp=0.5))
    sold_qty = next(s for s in sol_no.sold_molecules if s["mol_id"] == "C")["quantity"]
    expected_delta = 0.5 * 10.0 * sold_qty
    assert abs((sol_no.objective_value - sol_c.objective_value) - expected_delta) < 1e-2
