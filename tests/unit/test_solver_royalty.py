import polars as pl

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _two_reaction_fixture(*, process_covered: bool, composition_covered: bool):
    """Single reaction A + B → C; price A=$1/g, B=$1/g, C=$10/g; yield 1.0."""
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
    reactions, molecules = _two_reaction_fixture(process_covered=True, composition_covered=True)
    sol_zero = build_and_solve(reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.0))
    reactions_legacy = reactions.drop(["patent_active", "process_covered", "composition_covered"])
    sol_legacy = build_and_solve(reactions_legacy, molecules, SolverConfig())
    assert abs(sol_zero.objective_value - sol_legacy.objective_value) < 1e-3


def test_process_royalty_reduces_objective_by_expected_amount():
    reactions, molecules = _two_reaction_fixture(process_covered=True, composition_covered=False)
    cfg_no = SolverConfig(r_process=0.0, r_comp=0.0)
    cfg_p = SolverConfig(r_process=0.5, r_comp=0.0)
    sol_no = build_and_solve(reactions, molecules, cfg_no)
    sol_p = build_and_solve(reactions, molecules, cfg_p)
    expected_delta = 0.5 * 10.0 * 1.0 * sol_no.activated_reactions[0]["flow"]
    assert abs((sol_no.objective_value - sol_p.objective_value) - expected_delta) < 1e-2


def test_composition_royalty_reduces_objective_by_expected_amount():
    reactions, molecules = _two_reaction_fixture(process_covered=False, composition_covered=True)
    sol_no = build_and_solve(reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.0))
    sol_c = build_and_solve(reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.5))
    # Royalty paid = r_comp · price · qty_sold(C) where qty_sold is the
    # productive (post-royalty) quantity. The zero-royalty case tolerates
    # zero-margin buy/resell arbitrage on C (buy_price == sell_price), so
    # sol_no.sold_qty(C) over-counts by the arbitrage volume; the royalty
    # case eliminates it. Both solutions reach the same objective minus
    # exactly r_comp · price · qty_sold_in_sol_c[C].
    sold_qty = next(s for s in sol_c.sold_molecules if s["mol_id"] == "C")["quantity"]
    expected_delta = 0.5 * 10.0 * sold_qty
    assert abs((sol_no.objective_value - sol_c.objective_value) - expected_delta) < 1e-2
