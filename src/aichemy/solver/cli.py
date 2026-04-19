"""CLI entry point for the MILP solver: `aichemy solve`."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from aichemy.config import load_config
from aichemy.preprocessing.io import (
    processed_path,
    read_molecules,
    read_reactions,
)
from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve

solver_app = typer.Typer(
    help="MILP profit-maximization solver over the processed hypergraph.",
    no_args_is_help=True,
)

_ConfigOpt = typer.Option(..., "--config", help="Preprocessing config YAML")
_OverrideOpt = typer.Option([], "--override", help="Config override YAMLs (repeatable)")
_BudgetOpt = typer.Option(10_000.0, "--budget")
_MaxProductsOpt = typer.Option(None, "--max-products")
_BackendOpt = typer.Option("cbc", "--backend")
_VerboseOpt = typer.Option(False, "--verbose")
_OutputOpt = typer.Option(
    None, "--output", help="JSON output path (default: data/processed/solution.json)"
)


@solver_app.command("run")
def solve(
    config: Path = _ConfigOpt,
    override: list[Path] = _OverrideOpt,
    budget: float = _BudgetOpt,
    max_products: int | None = _MaxProductsOpt,
    backend: str = _BackendOpt,
    verbose: bool = _VerboseOpt,
    output: Path | None = _OutputOpt,
) -> None:
    """Solve the profit-maximization MILP on `data/processed/`."""
    cfg = load_config(config, override)
    solver_cfg = SolverConfig(
        budget=budget,
        max_products=max_products,
        backend=backend,  # type: ignore[arg-type]
        verbose=verbose,
        output_path=output or processed_path(cfg, "solution.json"),
    )

    reactions = read_reactions(processed_path(cfg, "reactions.parquet"))
    molecules = read_molecules(processed_path(cfg, "molecules.parquet"))

    typer.echo(f"[solve] Loaded {reactions.height} reactions, {molecules.height} molecules.")

    solution = build_and_solve(reactions, molecules, solver_cfg)

    solver_cfg.output_path.parent.mkdir(parents=True, exist_ok=True)
    solver_cfg.output_path.write_text(json.dumps(solution.to_dict(), indent=2) + "\n")

    typer.echo(
        f"[solve] status={solution.status}  profit=${solution.objective_value:,.2f}  "
        f"activated={len(solution.activated_reactions)}  "
        f"sold={len(solution.sold_molecules)}  "
        f"→ {solver_cfg.output_path}"
    )
