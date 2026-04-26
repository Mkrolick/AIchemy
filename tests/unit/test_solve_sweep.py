"""Tests for the `solve sweep` CLI helper (Task 18)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from aichemy.solver.cli import _run_sweep
from aichemy.solver.config import SolverConfig


def _fixture():
    reactions = pl.DataFrame(
        {
            "rxn_id": ["RX1"],
            "yield_rate": [1.0],
            "reactants": [[{"mol_id": "A", "coefficient": 1.0}]],
            "products": [[{"mol_id": "C", "coefficient": 1.0}]],
            "rdkit_balanced": [True],
            "balanced": [True],
            "patent_active": [True],
            "process_covered": [True],
            "composition_covered": [True],
        }
    )
    molecules = pl.DataFrame({"mol_id": ["A", "C"], "price_per_gram": [1.0, 10.0]})
    return reactions, molecules


def test_sweep_writes_summary_with_one_row_per_grid_point(tmp_path: Path):
    reactions, molecules = _fixture()
    summary = _run_sweep(
        reactions,
        molecules,
        r_process_grid=[0.0, 0.05],
        r_comp_grid=[0.0, 0.05],
        out_dir=tmp_path,
        base_config=SolverConfig(),
    )
    assert summary.height == 4
    assert set(summary.columns) >= {
        "r_process",
        "r_comp",
        "objective_value",
        "n_active_reactions",
        "n_sold_products",
        "set_hash",
        "infeasible",
    }
    assert (tmp_path / "summary.parquet").exists()


def test_sweep_set_hash_changes_when_active_set_changes(tmp_path: Path):
    """Very high royalty turns the patent-covered route off → different set_hash."""
    reactions, molecules = _fixture()
    summary = _run_sweep(
        reactions,
        molecules,
        r_process_grid=[0.0, 0.99],
        r_comp_grid=[0.0],
        out_dir=tmp_path,
        base_config=SolverConfig(),
    )
    hashes = summary["set_hash"].to_list()
    assert hashes[0] != hashes[1]


def test_sweep_writes_per_cell_solution_files(tmp_path: Path):
    reactions, molecules = _fixture()
    _run_sweep(
        reactions,
        molecules,
        r_process_grid=[0.0],
        r_comp_grid=[0.0],
        out_dir=tmp_path,
        base_config=SolverConfig(),
    )
    cells = list((tmp_path / "runs").glob("r_process_*_r_comp_*"))
    assert len(cells) == 1
    sol = json.loads((cells[0] / "solution.json").read_text())
    assert "objective_value" in sol
