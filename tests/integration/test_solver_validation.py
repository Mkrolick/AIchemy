"""Scientific-correctness validation for the MILP solver.

Unlike the isolated unit tests in `tests/unit/test_solver.py`, these cases
either (a) have a closed-form optimum computed by hand that the solver
must match numerically, or (b) are real-data sanity checks with known
bounds (profit ≥ 0, activated reactions ⊆ balanced, etc.).
"""

from __future__ import annotations

import logging

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


def test_sell_big_m_does_not_clamp_high_mw_high_budget() -> None:
    """Big-M on ``q_sell ≤ M·w_m`` must scale with grams, not mol-extent.

    Fixture: cheap-input → expensive-output isomerization on glucose
    (MW≈180), budget $1M, max_flow=1000 (default), buy A @ $0.01/g, sell
    B @ $1.00/g. With max_flow binding, f_r = 1000 → q_sell_B =
    180.16·1000 ≈ 180,160 g; profit = 180,160 − 1,801.60 ≈ $178,358.

    Regression guard: the prior big-M was ``max_flow · 100 = 100,000`` —
    in mol-extent units, not grams. On this fixture it would clamp
    q_sell_B at 100,000 g (~$99,000 profit) and silently leave ~$79k on
    the table. The corrected big-M scales with the budget, so cheap
    inputs lift the bound rather than tightening it.
    """
    glucose = "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O"  # C6H12O6, MW=180.16
    reactions = _reactions(
        [
            {
                "rxn_id": "isomerize",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 1.0,
            },
        ]
    )
    molecules = pl.DataFrame(
        [
            {
                "mol_id": "A",
                "canonical_smiles": glucose,
                "inchi_key": "KEY_A",
                "carbon_count": 6,
                "price_per_gram": 0.01,
                "source_refs": ["A"],
            },
            {
                "mol_id": "B",
                "canonical_smiles": glucose,
                "inchi_key": "KEY_B",
                "carbon_count": 6,
                "price_per_gram": 1.0,
                "source_refs": ["B"],
            },
        ],
        schema_overrides={"price_per_gram": pl.Float64},
    )
    cfg = SolverConfig(budget=1_000_000.0)  # max_flow stays at the 1000 default
    solution = build_and_solve(reactions, molecules, cfg)

    assert solution.status == "Optimal"
    assert solution.objective_value == pytest.approx(178_358.4, abs=10.0)
    sold_b = next((s for s in solution.sold_molecules if s["mol_id"] == "B"), None)
    assert sold_b is not None
    assert sold_b["quantity"] == pytest.approx(180_160.0, abs=10.0)


def test_zero_yield_is_respected_not_treated_as_missing() -> None:
    """A reaction with explicit ``yield_rate=0.0`` produces zero product.

    Same fixture as ``test_hand_solved_linear_network`` (which gives $900 at
    yield=1.0), but with yield pinned to 0.0. Physical interpretation: the
    reaction consumes reactant but never yields product, so the only
    profit-positive action is to do nothing.

    Regression guard: ``yield_rate = row.get("yield_rate") or 0.85`` would
    silently rewrite 0.0 → 0.85 and the LP would find ~$750 of phantom
    profit on this fixture. The fallback must trigger only on ``None``.
    """
    reactions = _reactions(
        [
            {
                "rxn_id": "r1",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 0.0,
            },
        ]
    )
    molecules = _molecules({"A": 1.0, "B": 10.0})
    cfg = SolverConfig(budget=100.0, max_flow=10_000.0)
    solution = build_and_solve(reactions, molecules, cfg)

    assert solution.status == "Optimal"
    assert solution.objective_value == pytest.approx(0.0, abs=1e-3)


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


# ---------------- MW-aware mass balance ----------------------


def test_mass_balance_respects_mw_asymmetry() -> None:
    """`2 H₂O → 2 H₂ + O₂` — textbook MW-asymmetric reaction.

    Stoich (mol): 2 H₂O on the left, 2 H₂ + 1 O₂ on the right.
    MW (g/mol):   18.02   on the left, 2.02 + 32.00 on the right.
    Mass balance in grams works out: 2·18.02 = 2·2.02 + 1·32.00 (36.04 = 36.04).

    Setup: budget=$36 (enough to buy exactly 36g of H₂O at $1/g, i.e.
    2 mol-extents). Both H₂ ($10/g) and O₂ ($10/g) sellable.

    Expected with the always-on mass-basis math:
      f = mol-extent. One f consumes 2·18.02 g of H₂O and produces
      2·2.02 g H₂ + 1·32.00 g O₂. 36 g H₂O → 36 g of products →
      revenue 36×$10 = $360 → profit ≈ $324.
    """
    reactions = _reactions(
        [
            {
                "rxn_id": "h2o_split",
                "reactants": [{"mol_id": "H2O", "coefficient": 2.0}],
                "products": [
                    {"mol_id": "H2", "coefficient": 2.0},
                    {"mol_id": "O2", "coefficient": 1.0},
                ],
                "yield_rate": 1.0,
            },
        ]
    )
    molecules = pl.DataFrame(
        [
            {
                "mol_id": "H2O",
                "canonical_smiles": "O",
                "inchi_key": "KEY_H2O",
                "carbon_count": 0,
                "price_per_gram": 1.0,
                "source_refs": ["H2O"],
            },
            {
                "mol_id": "H2",
                "canonical_smiles": "[H][H]",
                "inchi_key": "KEY_H2",
                "carbon_count": 0,
                "price_per_gram": 10.0,
                "source_refs": ["H2"],
            },
            {
                "mol_id": "O2",
                "canonical_smiles": "O=O",
                "inchi_key": "KEY_O2",
                "carbon_count": 0,
                "price_per_gram": 10.0,
                "source_refs": ["O2"],
            },
        ],
        schema_overrides={"price_per_gram": pl.Float64},
    )

    sol = build_and_solve(reactions, molecules, SolverConfig(budget=36.0, max_flow=10_000.0))

    assert sol.status == "Optimal"
    assert sol.objective_value == pytest.approx(324.0, abs=1.0)

    # Verify gram-level mass conservation across the whole solution.
    grams_in = sum(p["quantity"] for p in sol.purchased_molecules)
    grams_out = sum(s["quantity"] for s in sol.sold_molecules)
    assert grams_in == pytest.approx(grams_out, rel=1e-3)

    # Pin per-product sold quantities — the aggregate grams check above
    # is satisfied if the optimizer sells only one product at a degenerate
    # ratio. Per mol-extent the reaction produces 2·2.02=4.04 g H₂ and
    # 1·32.00=32 g O₂; both must show up at f≈1 (budget binds at 36/36.04).
    sold_by_id = {s["mol_id"]: s["quantity"] for s in sol.sold_molecules}
    assert sold_by_id["H2"] == pytest.approx(4.04, abs=0.05)
    assert sold_by_id["O2"] == pytest.approx(32.0, abs=0.05)


def test_mass_balance_with_yield_loss_under_mw_asymmetry() -> None:
    """Same H₂O → H₂ + O₂ fixture as above but with yield_rate=0.5.

    Each mol-extent still consumes 36.04 g H₂O on the reactant side, but
    only produces 0.5·(2·2.02 + 32) = 18.02 g of products. Catches a
    regression that omits η on the product side (which would give the
    yield=1.0 answer ≈ $324 instead) — the model.py mass-balance applies
    `coef · yld · f` for producers but `coef · f` for reactants, and that
    asymmetry needs explicit coverage.

    Closed form: budget=$36 binds at f ≈ 36/36.04. Revenue per extent =
    360.4·0.5 = 180.2; cost per extent = 36.04 → profit per extent ≈
    144.16 → total profit ≈ 144.
    """
    reactions = _reactions(
        [
            {
                "rxn_id": "h2o_split",
                "reactants": [{"mol_id": "H2O", "coefficient": 2.0}],
                "products": [
                    {"mol_id": "H2", "coefficient": 2.0},
                    {"mol_id": "O2", "coefficient": 1.0},
                ],
                "yield_rate": 0.5,
            },
        ]
    )
    molecules = pl.DataFrame(
        [
            {
                "mol_id": "H2O",
                "canonical_smiles": "O",
                "inchi_key": "KEY_H2O",
                "carbon_count": 0,
                "price_per_gram": 1.0,
                "source_refs": ["H2O"],
            },
            {
                "mol_id": "H2",
                "canonical_smiles": "[H][H]",
                "inchi_key": "KEY_H2",
                "carbon_count": 0,
                "price_per_gram": 10.0,
                "source_refs": ["H2"],
            },
            {
                "mol_id": "O2",
                "canonical_smiles": "O=O",
                "inchi_key": "KEY_O2",
                "carbon_count": 0,
                "price_per_gram": 10.0,
                "source_refs": ["O2"],
            },
        ],
        schema_overrides={"price_per_gram": pl.Float64},
    )

    sol = build_and_solve(reactions, molecules, SolverConfig(budget=36.0, max_flow=10_000.0))

    assert sol.status == "Optimal"
    assert sol.objective_value == pytest.approx(144.0, abs=1.0)

    # Mass-balance with yield<1: grams_in = grams_out / yield (the missing
    # mass is the yield loss). Note: NOT grams_in == grams_out.
    grams_in = sum(p["quantity"] for p in sol.purchased_molecules)
    grams_out = sum(s["quantity"] for s in sol.sold_molecules)
    assert grams_out == pytest.approx(grams_in * 0.5, rel=1e-3)


def test_precomputed_mol_weight_wins_over_rdkit_fallback() -> None:
    """When the molecules DataFrame carries BOTH `mol_weight` and
    `canonical_smiles`, the precomputed `mol_weight` column must win —
    otherwise a future refactor that swaps the priority is silent.

    Fixture A → B with yield=1.0:
      mol_weight column: A=1, B=1 (uniform → coef·MW collapses to coef).
      canonical_smiles:  A=CCO (ethanol, MW≈46), B=CC(=O)O (acetic acid, MW≈60).

    If mol_weight wins: per mol-extent f costs $1 (1 g A) and earns $10
    (1 g B) → at budget=$10, f=10, profit ≈ $90.

    If RDKit wins: per mol-extent costs $46 and earns $600 → at budget=$10,
    f≈0.217, profit ≈ $120 — distinct enough to fail the $90 assertion.
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
    molecules = pl.DataFrame(
        [
            {
                "mol_id": "A",
                "canonical_smiles": "CCO",
                "mol_weight": 1.0,
                "inchi_key": "KEY_A",
                "carbon_count": 2,
                "price_per_gram": 1.0,
                "source_refs": ["A"],
            },
            {
                "mol_id": "B",
                "canonical_smiles": "CC(=O)O",
                "mol_weight": 1.0,
                "inchi_key": "KEY_B",
                "carbon_count": 2,
                "price_per_gram": 10.0,
                "source_refs": ["B"],
            },
        ],
        schema_overrides={"price_per_gram": pl.Float64, "mol_weight": pl.Float64},
    )

    sol = build_and_solve(reactions, molecules, SolverConfig(budget=10.0, max_flow=10_000.0))

    assert sol.status == "Optimal"
    assert sol.objective_value == pytest.approx(90.0, abs=1.0)


def test_max_flow_binds_in_mol_extent_units() -> None:
    """`max_flow` caps `f` in mol-extents, NOT grams. With max_flow=1 and
    MW=100, the activated reaction must run at exactly f=1 and move 100 g
    of A and 100 g of B. A regression that re-interprets max_flow as a
    gram-cap (or as a per-coef-grams cap) would give a dramatically
    different `flow` value and gram quantities.

    Budget is set to 1e9 so the budget never binds — only max_flow does.
    Without this fixture, every other test has the budget bind first, so
    the model.py docstring claim "max_flow is in mol-extent units" goes
    unverified by code.
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
    molecules = pl.DataFrame(
        {
            "mol_id": ["A", "B"],
            "mol_weight": [100.0, 100.0],
            "price_per_gram": [1.0, 10.0],
        }
    )
    sol = build_and_solve(reactions, molecules, SolverConfig(budget=1e9, max_flow=1.0))

    assert sol.status == "Optimal"
    # f must equal max_flow exactly; flow is the mol-extent value.
    assert len(sol.activated_reactions) == 1
    assert sol.activated_reactions[0]["flow"] == pytest.approx(1.0, abs=1e-3)

    # Per-molecule gram totals: q_buy_A = coef · MW · f = 1·100·1 = 100 g;
    # q_sell_B = 100 g. Profit = 100·$10 − 100·$1 = $900.
    purchased_a = next(p for p in sol.purchased_molecules if p["mol_id"] == "A")
    sold_b = next(s for s in sol.sold_molecules if s["mol_id"] == "B")
    assert purchased_a["quantity"] == pytest.approx(100.0, abs=1e-3)
    assert sold_b["quantity"] == pytest.approx(100.0, abs=1e-3)
    assert sol.objective_value == pytest.approx(900.0, abs=1e-2)


def test_drops_reactions_with_unparseable_smiles(caplog: pytest.LogCaptureFixture) -> None:
    """A molecule whose SMILES can't be parsed → reactions referencing it
    are dropped at model-build time. The remaining network solves cleanly.

    Uses caplog to pin down the drop *mechanism* (kept=1, dropped=1) — the
    surviving-graph assertions below could pass for several wrong reasons
    (e.g. a kept-but-zero-flow reaction, or a buggy MW=0 that quietly
    zeroes the bad route).
    """
    caplog.set_level(logging.INFO, logger="aichemy.solver.model")
    reactions = _reactions(
        [
            {
                "rxn_id": "good",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "B", "coefficient": 1.0}],
                "yield_rate": 1.0,
            },
            {
                "rxn_id": "bad",
                "reactants": [{"mol_id": "A", "coefficient": 1.0}],
                "products": [{"mol_id": "MYSTERY", "coefficient": 1.0}],
                "yield_rate": 1.0,
            },
        ]
    )
    molecules = pl.DataFrame(
        [
            {
                "mol_id": "A",
                "canonical_smiles": "CCO",  # ethanol
                "inchi_key": "KEY_A",
                "carbon_count": 2,
                "price_per_gram": 1.0,
                "source_refs": ["A"],
            },
            {
                "mol_id": "B",
                "canonical_smiles": "CC(=O)O",  # acetic acid
                "inchi_key": "KEY_B",
                "carbon_count": 2,
                "price_per_gram": 10.0,
                "source_refs": ["B"],
            },
            {
                "mol_id": "MYSTERY",
                "canonical_smiles": "NOT_A_SMILES",  # parse fails → no MW
                "inchi_key": "KEY_M",
                "carbon_count": 0,
                "price_per_gram": 100.0,
                "source_refs": ["MYSTERY"],
            },
        ],
        schema_overrides={"price_per_gram": pl.Float64},
    )

    sol = build_and_solve(reactions, molecules, SolverConfig(budget=100.0, max_flow=10_000.0))

    assert sol.status == "Optimal"
    activated_ids = {r["rxn_id"] for r in sol.activated_reactions}
    assert "good" in activated_ids
    assert "bad" not in activated_ids
    sold_ids = {s["mol_id"] for s in sol.sold_molecules}
    assert "MYSTERY" not in sold_ids

    # Pin the drop mechanism explicitly via the model's `[mass_basis] kept=…
    # dropped=…` log line — proves the bad reaction was excluded at build
    # time, not silently kept with degenerate coefficients.
    mass_basis_logs = [r.getMessage() for r in caplog.records if "[mass_basis]" in r.getMessage()]
    assert any("kept=1 dropped=1" in msg for msg in mass_basis_logs), mass_basis_logs
