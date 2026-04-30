"""USPTO-only license-fee hyperparameter sweep + 4×4 grid plot.

Filters reactions.parquet to ``source == "uspto"`` (the patent-text-mined
subset, which is the only one where licensing actually applies — MetaNetX
records biological reactions which can't be patented), then sweeps the
``(r_process, r_comp)`` royalty grid via the in-process MILP. For each
cell, records the optimal profit and writes:

  - ``uspto_license_sweep_results.csv``     one row per cell
  - ``uspto_license_sweep_grid.png``        4x4 heatmap of profit($) vs (r_process, r_comp)
  - ``uspto_license_sweep_summary.json``    metadata + run-time totals

Usage:
    uv run python scripts/run_uspto_license_sweep.py
    uv run python scripts/run_uspto_license_sweep.py --grid 0,0.02,0.04,0.06
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--reactions",
        type=Path,
        default=Path("data/processed/reactions.parquet"),
    )
    p.add_argument(
        "--molecules",
        type=Path,
        default=Path("data/processed/molecules_with_mw.parquet"),
    )
    p.add_argument(
        "--grid",
        default="0,0.02,0.04,0.06",
        help="Comma-separated decimal fractions used for both r_process and r_comp axes.",
    )
    p.add_argument("--budget", type=float, default=10_000.0)
    p.add_argument("--max-reactions", type=int, default=10)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/writeup_artifacts"),
    )
    p.add_argument(
        "--patent-active-only",
        action="store_true",
        help=(
            "Filter to reactions with patent_active=True. Forces every reaction "
            "in the model to be license-bearing so royalty rates actually bind. "
            "Without this, the optimum often picks patent-free routes and the "
            "sweep is a flat plane."
        ),
    )
    p.add_argument(
        "--licensed-sales-only",
        action="store_true",
        help=(
            "Forbid selling any product that isn't composition_covered. Forces "
            "the composition-royalty term to bind on the optimal solution; "
            "without this, the optimum often produces a product nobody patented "
            "and r_comp has zero effect."
        ),
    )
    p.add_argument(
        "--filename-suffix",
        default="",
        help="Suffix inserted before .png/.csv/.json so variants don't overwrite.",
    )
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rates = [float(x) for x in args.grid.split(",") if x.strip()]
    print(f"[uspto-sweep] grid: {rates}", flush=True)

    print(f"[uspto-sweep] loading {args.reactions}", flush=True)
    reactions_all = pl.read_parquet(args.reactions)
    reactions = reactions_all.filter(pl.col("source") == "uspto")
    print(
        f"[uspto-sweep] filtered to USPTO: {reactions.height:,} of {reactions_all.height:,}",
        flush=True,
    )
    if args.patent_active_only:
        before = reactions.height
        reactions = reactions.filter(pl.col("patent_active"))
        print(
            f"[uspto-sweep] further filtered to patent_active=True: "
            f"{reactions.height:,} of {before:,}",
            flush=True,
        )

    print(f"[uspto-sweep] loading {args.molecules}", flush=True)
    molecules = pl.read_parquet(args.molecules)

    # Build the set of mol_ids the optimizer is allowed to sell. By default
    # any referenced molecule is sellable; --licensed-sales-only restricts to
    # composition_covered molecules (= products of any composition_covered
    # reaction in the active subset), forbidding every other product.
    forbidden_sell: list[str] = []
    if args.licensed_sales_only:
        comp_mol_ids: set[str] = set()
        for row in reactions.iter_rows(named=True):
            if row.get("composition_covered"):
                for prod in row["products"]:
                    comp_mol_ids.add(prod["mol_id"])
        # Any referenced molecule NOT in comp_mol_ids must be forbidden.
        referenced: set[str] = set()
        for row in reactions.iter_rows(named=True):
            for side in ("reactants", "products"):
                for p in row[side]:
                    referenced.add(p["mol_id"])
        forbidden_sell = sorted(referenced - comp_mol_ids)
        print(
            f"[uspto-sweep] composition_covered molecules: {len(comp_mol_ids):,} "
            f"of {len(referenced):,} referenced — forbidding {len(forbidden_sell):,} "
            f"non-licensed products from sale",
            flush=True,
        )

    rows = []
    started = time.monotonic()
    n_cells = len(rates) * len(rates)
    cell = 0
    for rp in rates:
        for rc in rates:
            cell += 1
            t0 = time.monotonic()
            cfg = SolverConfig(
                budget=args.budget,
                max_reactions=args.max_reactions,
                r_process=rp,
                r_comp=rc,
                forbidden_sell_molecules=forbidden_sell,
            )
            sol = build_and_solve(reactions, molecules, cfg)
            wall = time.monotonic() - t0
            row = {
                "r_process": rp,
                "r_comp": rc,
                "profit": float(sol.objective_value),
                "status": sol.status,
                "n_activated": len(sol.activated_reactions),
                "n_sold": len(sol.sold_molecules),
                "wall_seconds": wall,
            }
            rows.append(row)
            print(
                f"[uspto-sweep] cell {cell:>2}/{n_cells}  rp={rp:.2f} rc={rc:.2f}  "
                f"profit=${row['profit']:>14,.0f}  status={row['status']}  ({wall:.1f}s)",
                flush=True,
            )

    total_wall = time.monotonic() - started
    df = pl.DataFrame(rows)
    suffix = args.filename_suffix
    df.write_csv(args.out_dir / f"uspto_license_sweep_results{suffix}.csv")

    # --- 4x4 heatmap ---
    n = len(rates)
    grid = np.zeros((n, n), dtype=float)
    for r in rows:
        i = rates.index(r["r_process"])
        j = rates.index(r["r_comp"])
        grid[i, j] = r["profit"]

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(grid, origin="lower", cmap="viridis", aspect="auto")
    ax.set_xticks(range(n))
    ax.set_xticklabels([f"{r:.2f}" for r in rates])
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r:.2f}" for r in rates])
    ax.set_xlabel("r_comp (composition royalty rate)")
    ax.set_ylabel("r_process (process royalty rate)")
    ax.set_title(
        f"USPTO-only license-fee sweep: profit at "
        f"--max-reactions {args.max_reactions}, budget=${args.budget:,.0f}"
    )
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Profit ($)")
    # Annotate each cell with its $ value.
    for i in range(n):
        for j in range(n):
            ax.text(
                j,
                i,
                f"${grid[i, j]:,.0f}",
                ha="center",
                va="center",
                color="white" if grid[i, j] < grid.max() * 0.6 else "black",
                fontsize=8,
            )
    fig.tight_layout()
    grid_path = args.out_dir / f"uspto_license_sweep_grid{suffix}.png"
    fig.savefig(grid_path, dpi=160)
    plt.close(fig)
    print(f"\n[uspto-sweep] wrote {grid_path}", flush=True)

    # --- runtime extrapolation for the full corpus ---
    avg_uspto_secs = float(df["wall_seconds"].mean() or 0.0)
    full_n = reactions_all.height
    uspto_n = reactions.height
    full_corpus_extrapolated = avg_uspto_secs * full_n / max(uspto_n, 1)
    summary = {
        "rates": rates,
        "n_cells": n_cells,
        "uspto_reactions": int(uspto_n),
        "full_reactions": int(full_n),
        "total_wall_seconds": total_wall,
        "avg_per_cell_seconds_uspto_subset": avg_uspto_secs,
        "extrapolated_per_cell_seconds_full_corpus": full_corpus_extrapolated,
        "extrapolated_full_grid_seconds_full_corpus": full_corpus_extrapolated * n_cells,
        "budget": args.budget,
        "max_reactions": args.max_reactions,
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    summary["patent_active_only"] = bool(args.patent_active_only)
    summary["licensed_sales_only"] = bool(args.licensed_sales_only)
    summary["n_forbidden_products"] = len(forbidden_sell)
    (args.out_dir / f"uspto_license_sweep_summary{suffix}.json").write_text(
        json.dumps(summary, indent=2)
    )

    print(
        f"[uspto-sweep] avg cell wall = {avg_uspto_secs:.1f}s on {uspto_n:,} USPTO rxns; "
        f"extrapolated avg cell on the full {full_n:,}-rxn corpus = "
        f"{full_corpus_extrapolated:.0f}s "
        f"(full {n_cells}-cell grid ≈ {full_corpus_extrapolated * n_cells / 60:.1f} min)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
