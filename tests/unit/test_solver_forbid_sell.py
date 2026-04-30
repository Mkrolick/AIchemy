"""Forbid-sell list pins q_sell[mol_id] = 0 for the given molecules."""

from __future__ import annotations

import polars as pl

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _fixture():
    """A → C ($10/g) and A → D ($5/g); both routes available, both products
    sellable. Optimizer should prefer C without restrictions."""
    reactions = pl.DataFrame(
        {
            "rxn_id": ["RX_C", "RX_D"],
            "yield_rate": [1.0, 1.0],
            "reactants": [
                [{"mol_id": "A", "coefficient": 1.0}],
                [{"mol_id": "A", "coefficient": 1.0}],
            ],
            "products": [
                [{"mol_id": "C", "coefficient": 1.0}],
                [{"mol_id": "D", "coefficient": 1.0}],
            ],
            "rdkit_balanced": [True, True],
            "balanced": [True, True],
            "patent_active": [False, False],
            "process_covered": [False, False],
            "composition_covered": [False, False],
        }
    )
    # mol_weight=1 everywhere → mass-balance reduces to the legacy unit-coef
    # regime so existing assertions about which products get sold still hold.
    molecules = pl.DataFrame(
        {
            "mol_id": ["A", "C", "D"],
            "mol_weight": [1.0, 1.0, 1.0],
            "price_per_gram": [1.0, 10.0, 5.0],
        }
    )
    return reactions, molecules


def test_baseline_sells_both_when_both_profitable():
    """Without a forbid list and with unbounded inputs, optimizer sells
    both products (both are profitable and there's no constraint forcing
    a choice)."""
    reactions, molecules = _fixture()
    sol = build_and_solve(reactions, molecules, SolverConfig())
    sold_ids = {s["mol_id"] for s in sol.sold_molecules}
    assert "C" in sold_ids and "D" in sold_ids


def test_forbid_sell_pushes_optimizer_to_alternate():
    """With C forbidden, optimizer should fall back to D ($5/g)."""
    reactions, molecules = _fixture()
    sol = build_and_solve(
        reactions,
        molecules,
        SolverConfig(forbidden_sell_molecules=["C"]),
    )
    sold_ids = {s["mol_id"] for s in sol.sold_molecules}
    assert "C" not in sold_ids
    assert "D" in sold_ids


def test_forbid_sell_with_no_alternate_yields_zero_revenue():
    """With both C and D forbidden, no profitable sale exists. Optimizer
    should still find a feasible (trivial) solution with zero revenue."""
    reactions, molecules = _fixture()
    sol = build_and_solve(
        reactions,
        molecules,
        SolverConfig(forbidden_sell_molecules=["C", "D"]),
    )
    sold_ids = {s["mol_id"] for s in sol.sold_molecules}
    assert sold_ids == set()
    assert sol.objective_value <= 0.001  # no profit possible


def test_forbid_sell_unknown_mol_id_is_no_op():
    """Forbidding a mol_id that doesn't appear in `referenced` is a no-op
    (no error, no constraint added). Equivalent to the baseline."""
    reactions, molecules = _fixture()
    sol = build_and_solve(
        reactions,
        molecules,
        SolverConfig(forbidden_sell_molecules=["DOES_NOT_EXIST"]),
    )
    sol_baseline = build_and_solve(reactions, molecules, SolverConfig())
    assert abs(sol.objective_value - sol_baseline.objective_value) < 1e-3
