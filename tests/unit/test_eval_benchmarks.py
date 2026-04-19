"""Tests for eval benchmarks (Open Item 09)."""

from __future__ import annotations

import polars as pl

from aichemy.eval.benchmarks import (
    known_profitable_molecules,
    summarize_solution,
)
from aichemy.solver.model import Solution


def test_known_profitable_molecules_is_non_empty() -> None:
    catalog = known_profitable_molecules()
    assert len(catalog) > 0
    assert all(k.canonical_smiles for k in catalog)
    assert all(k.approx_price_per_gram_usd > 0 for k in catalog)


def test_summarize_solution_counts_match_inputs() -> None:
    sol = Solution(
        status="Optimal",
        objective_value=42.0,
        activated_reactions=[
            {"rxn_id": "r1", "flow": 1.0, "yield_rate": 0.9},
            {"rxn_id": "r2", "flow": 2.0, "yield_rate": 0.85},
        ],
        purchased_molecules=[{"mol_id": "A", "quantity": 1.0, "price_per_gram": 1.0, "cost": 1.0}],
        sold_molecules=[
            {"mol_id": "B", "quantity": 2.0, "price_per_gram": 10.0, "revenue": 20.0},
            {"mol_id": "C", "quantity": 3.0, "price_per_gram": 5.0, "revenue": 15.0},
        ],
    )
    report = summarize_solution(sol)
    assert report.objective_value == 42.0
    assert report.num_activated_reactions == 2
    assert report.num_sold_molecules == 2
    assert report.num_purchased_molecules == 1
    # Top-sold should be ordered by revenue desc
    assert report.top_sold[0]["mol_id"] == "B"


def test_summarize_solution_detects_known_molecule_hits() -> None:
    sol = Solution(
        status="Optimal",
        objective_value=100.0,
        activated_reactions=[],
        purchased_molecules=[],
        sold_molecules=[
            {
                "mol_id": "MNX_citric",
                "quantity": 5.0,
                "price_per_gram": 0.002,
                "revenue": 0.01,
            }
        ],
    )
    molecules = pl.DataFrame(
        {
            "mol_id": ["MNX_citric"],
            "canonical_smiles": ["OC(=O)CC(O)(CC(=O)O)C(=O)O"],  # citric acid
        }
    )
    report = summarize_solution(sol, molecules=molecules)
    assert "citric acid" in report.known_hits
