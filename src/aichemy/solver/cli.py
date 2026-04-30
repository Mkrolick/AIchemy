"""CLI entry point for the MILP solver: `aichemy solve`."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl
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
_MaxReactionsOpt = typer.Option(
    None,
    "--max-reactions",
    help="Cap on the number of activated reactions (synthesis-route length).",
)
_ForbidSellOpt = typer.Option(
    "",
    "--forbid-sell",
    help=(
        "Comma-separated mol_ids that the solver may not sell "
        "(q_sell pinned to 0). Example: --forbid-sell MNXM731718,MNXM319"
    ),
)
_BackendOpt = typer.Option("cbc", "--backend")
_VerboseOpt = typer.Option(False, "--verbose")
_OutputOpt = typer.Option(
    None, "--output", help="JSON output path (default: data/processed/solution.json)"
)
_BalanceFilterOpt = typer.Option(
    "rdkit_balanced",
    "--balance-filter",
    help=(
        "Which boolean column gates reactions: 'rdkit_balanced' (default, "
        "strict atom-count) or 'balanced' (looser per-source claim)."
    ),
)
_RProcessOpt = typer.Option(
    "0,0.02,0.04,0.06,0.08",
    "--r-process",
    help="Comma-separated decimal fractions for the process royalty axis.",
)
_RCompOpt = typer.Option(
    "0,0.02,0.04,0.06,0.08",
    "--r-comp",
    help="Comma-separated decimal fractions for the composition royalty axis.",
)
_SweepOutOpt = typer.Option(
    Path("data/processed/sensitivity"),
    "--out",
    help="Output directory.",
)


@solver_app.command("run")
def solve(
    config: Path = _ConfigOpt,
    override: list[Path] = _OverrideOpt,
    budget: float = _BudgetOpt,
    max_products: int | None = _MaxProductsOpt,
    max_reactions: int | None = _MaxReactionsOpt,
    forbid_sell: str = _ForbidSellOpt,
    backend: str = _BackendOpt,
    verbose: bool = _VerboseOpt,
    output: Path | None = _OutputOpt,
    balance_filter: str = _BalanceFilterOpt,
) -> None:
    """Solve the profit-maximization MILP on `data/processed/`."""
    cfg = load_config(config, override)
    forbidden = [m.strip() for m in forbid_sell.split(",") if m.strip()]
    solver_cfg = SolverConfig(
        budget=budget,
        max_products=max_products,
        max_reactions=max_reactions,
        forbidden_sell_molecules=forbidden,
        backend=backend,  # type: ignore[arg-type]
        verbose=verbose,
        output_path=output or processed_path(cfg, "solution.json"),
        balance_filter=balance_filter,  # type: ignore[arg-type]
    )

    reactions = read_reactions(processed_path(cfg, "reactions.parquet"))
    # Solver requires per-participant MW for mass-coherent balance. Prefer the
    # precomputed table from `aichemy augment molecule-weights`; fall back to
    # the bare molecules.parquet (the model will then compute MW on the fly
    # from canonical_smiles via RDKit, slower but correct).
    mw_path = processed_path(cfg, "molecules_with_mw.parquet")
    bare_path = processed_path(cfg, "molecules.parquet")
    if mw_path.exists():
        molecules = read_molecules(mw_path)
    elif bare_path.exists():
        molecules = read_molecules(bare_path)
    else:
        raise typer.BadParameter(
            f"Neither {mw_path} nor {bare_path} exists; "
            "run `uv run aichemy export` (and ideally also "
            "`aichemy augment molecule-weights`) first."
        )

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


def _run_sweep(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame,
    *,
    r_process_grid: list[float],
    r_comp_grid: list[float],
    out_dir: Path,
    base_config: SolverConfig,
) -> pl.DataFrame:
    """Loop the (r_process, r_comp) grid; write per-cell solutions + summary parquet.

    Per-cell output: ``out_dir/runs/r_process_<rp:.4f>_r_comp_<rc:.4f>/solution.json``.
    Summary: ``out_dir/summary.parquet`` with one row per grid point and a
    ``set_hash`` column for "decision invariance" plotting.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for rp in r_process_grid:
        for rc in r_comp_grid:
            cfg = base_config.model_copy(update={"r_process": rp, "r_comp": rc})
            sol = build_and_solve(reactions, molecules, cfg)
            cell_dir = out_dir / "runs" / f"r_process_{rp:.4f}_r_comp_{rc:.4f}"
            cell_dir.mkdir(parents=True, exist_ok=True)
            (cell_dir / "solution.json").write_text(json.dumps(sol.to_dict(), indent=2) + "\n")
            sold_ids = sorted(s["mol_id"] for s in sol.sold_molecules)
            set_hash = hashlib.sha256(",".join(sold_ids).encode()).hexdigest()[:16]
            rows.append(
                {
                    "r_process": rp,
                    "r_comp": rc,
                    "objective_value": (
                        float(sol.objective_value) if sol.status == "Optimal" else None
                    ),
                    "n_active_reactions": len(sol.activated_reactions),
                    "n_sold_products": len(sol.sold_molecules),
                    "set_hash": set_hash,
                    "infeasible": sol.status == "Infeasible",
                }
            )
    summary = pl.DataFrame(rows)
    summary.write_parquet(out_dir / "summary.parquet")
    return summary


@solver_app.command("sweep")
def sweep(
    config: Path = _ConfigOpt,
    override: list[Path] = _OverrideOpt,
    r_process: str = _RProcessOpt,
    r_comp: str = _RCompOpt,
    out: Path = _SweepOutOpt,
    backend: str = _BackendOpt,
    verbose: bool = _VerboseOpt,
    balance_filter: str = _BalanceFilterOpt,
) -> None:
    """Sweep the (r_process, r_comp) grid; write per-cell solutions + summary parquet."""
    cfg = load_config(config, override)
    base_cfg = SolverConfig(
        backend=backend,  # type: ignore[arg-type]
        verbose=verbose,
        output_path=processed_path(cfg, "solution.json"),
        balance_filter=balance_filter,  # type: ignore[arg-type]
    )

    reactions = read_reactions(processed_path(cfg, "reactions.parquet"))
    mw_path = processed_path(cfg, "molecules_with_mw.parquet")
    bare_path = processed_path(cfg, "molecules.parquet")
    if mw_path.exists():
        molecules = read_molecules(mw_path)
    elif bare_path.exists():
        molecules = read_molecules(bare_path)
    else:
        raise typer.BadParameter(
            f"Neither {mw_path} nor {bare_path} exists; "
            "run `uv run aichemy export` (and ideally also "
            "`aichemy augment molecule-weights`) first."
        )

    rp_grid = [float(x) for x in r_process.split(",")]
    rc_grid = [float(x) for x in r_comp.split(",")]
    typer.echo(f"[solve sweep] {len(rp_grid)}x{len(rc_grid)} = {len(rp_grid) * len(rc_grid)} cells")
    summary = _run_sweep(
        reactions,
        molecules,
        r_process_grid=rp_grid,
        r_comp_grid=rc_grid,
        out_dir=out,
        base_config=base_cfg,
    )
    typer.echo(
        f"[solve sweep] complete; summary → {out / 'summary.parquet'} ({summary.height} rows)"
    )
