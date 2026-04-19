"""Scaling benchmark for the MILP solver on real MetaNetX data.

Ordinarily skipped (`slow` marker); run explicitly with:
    uv run pytest tests/integration/test_solver_scaling.py -m slow

Empirical scaling (measured 2026-04-19, M-series laptop, CBC backend,
synthetic random prices):

    n=100    mols=267    time=<0.1s
    n=500    mols=1051   time=0.2s
    n=1000   mols=1874   time=0.6s
    n=5000   mols=6950   time=4.9s
    n=10000  mols=11357  time=17.7s
    n=20000  mols=17334  time=63.5s
    n=42760  mols=24816  time=352.9s  <-- full balanced MetaNetX set

Conclusion: CBC handles the full ~43k-reaction balanced network in ~6 min
on consumer hardware. For production research use this is acceptable;
Gurobi would be faster for iterative parameter sweeps.
"""

from __future__ import annotations

import random
import time
from pathlib import Path

import polars as pl
import pytest

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def _skip_if_no_real_data() -> None:
    if not (PROCESSED_DIR / "reactions.parquet").exists():
        pytest.skip("Real MetaNetX data not present (run `aichemy fetch-raw` + pipeline first)")


@pytest.mark.slow
def test_solver_handles_1000_reactions() -> None:
    """1k-reaction subset should solve in well under a minute."""
    _skip_if_no_real_data()

    reactions = pl.read_parquet(PROCESSED_DIR / "reactions.parquet").filter(pl.col("balanced"))
    all_molecules = pl.read_parquet(PROCESSED_DIR / "molecules.parquet")

    sample = reactions.sample(n=min(1000, reactions.height), seed=42)
    referenced: set[str] = set()
    for row in sample.iter_rows(named=True):
        for s in row["reactants"] + row["products"]:
            referenced.add(s["mol_id"])
    molecules = all_molecules.filter(pl.col("mol_id").is_in(list(referenced)))

    random.seed(42)
    prices = [random.uniform(0.1, 100.0) for _ in range(molecules.height)]
    molecules = molecules.with_columns(pl.Series("price_per_gram", prices, dtype=pl.Float64))

    t0 = time.time()
    solution = build_and_solve(sample, molecules, SolverConfig(budget=1000.0))
    elapsed = time.time() - t0

    assert solution.status == "Optimal"
    assert elapsed < 30.0, f"1k-reaction solve took {elapsed:.1f}s (>30s threshold)"


@pytest.mark.slow
def test_solver_handles_full_balanced_network() -> None:
    """Full ~43k balanced MetaNetX reactions — empirical time ~6 min.

    Guards: solution must be Optimal; time must be under 15 min.
    """
    _skip_if_no_real_data()

    reactions = pl.read_parquet(PROCESSED_DIR / "reactions.parquet").filter(pl.col("balanced"))
    all_molecules = pl.read_parquet(PROCESSED_DIR / "molecules.parquet")

    referenced: set[str] = set()
    for row in reactions.iter_rows(named=True):
        for s in row["reactants"] + row["products"]:
            referenced.add(s["mol_id"])
    molecules = all_molecules.filter(pl.col("mol_id").is_in(list(referenced)))

    random.seed(42)
    prices = [random.uniform(0.1, 100.0) for _ in range(molecules.height)]
    molecules = molecules.with_columns(pl.Series("price_per_gram", prices, dtype=pl.Float64))

    t0 = time.time()
    solution = build_and_solve(reactions, molecules, SolverConfig(budget=1000.0, max_products=20))
    elapsed = time.time() - t0

    assert solution.status == "Optimal"
    assert solution.objective_value >= 0  # do-nothing is always feasible
    assert elapsed < 900.0, f"Full-network solve took {elapsed:.1f}s (>15min threshold)"
