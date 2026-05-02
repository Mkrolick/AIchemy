"""Regenerate the writeup PNGs without titles, in a paper-clean style.

Reads the existing artifacts:
  - data/processed/profit_curve.jsonl
  - data/processed/writeup_artifacts/uspto_license_sweep_results*.csv

Writes paper-ready PNGs (no titles, larger fonts, tight layout, 300 dpi).
Drop straight into Overleaf and use \\caption{...} on the LaTeX side.

Usage:
    uv run python scripts/regenerate_clean_plots.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl


def _set_paper_style() -> None:
    """Minimal styling tweaks suitable for a LaTeX paper figure."""
    plt.rcParams.update(
        {
            "axes.labelsize": 13,
            "axes.titlesize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
            "font.family": "sans-serif",
        }
    )


def _load_records(jsonl: Path, top_n: int) -> list[dict]:
    records = []
    with open(jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    records.sort(key=lambda r: r["iteration"])
    return records[:top_n]


_SERIES_PROFIT = [
    ("MILP (uncapped)", "o-", "#1f77b4"),
    ("MILP (cap=20)", "s-.", "#2ca02c"),
    ("LP", "^--", "#ff7f0e"),
]
_SERIES_TIME = [
    ("MILP (uncapped)", "s-", "#d62728"),
    ("MILP (cap=20)", "D-.", "#9467bd"),
    ("LP", "v--", "#2ca02c"),
]


def plot_profit_vs_rank(
    milp_jsonl: Path,
    lp_jsonl: Path | None,
    cap20_jsonl: Path | None,
    top_n: int,
    out: Path,
) -> None:
    """Profit vs solve rank, with MILP / MILP-cap20 / LP series overlaid."""
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    paths = [milp_jsonl, cap20_jsonl, lp_jsonl]
    for path, (label, marker, color) in zip(paths, _SERIES_PROFIT, strict=True):
        if path is None or not path.exists():
            continue
        rs = _load_records(path, top_n)
        if not rs:
            continue
        ax.plot(
            [r["iteration"] for r in rs],
            [r["profit"] for r in rs],
            marker,
            color=color,
            linewidth=1.4,
            markersize=4,
            label=label,
        )

    ax.set_xlabel("Solve rank")
    ax.set_ylabel("Profit (USD, millions)")
    from matplotlib.ticker import FuncFormatter

    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e6:,.0f}"))
    ax.set_ylim(bottom=0)
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.55)
    ax.set_xticks(range(0, top_n + 1, max(1, top_n // 10)))
    ax.set_xlim(0.5, top_n + 0.5)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_solve_time_vs_rank(
    milp_jsonl: Path,
    lp_jsonl: Path | None,
    cap20_jsonl: Path | None,
    top_n: int,
    out: Path,
) -> None:
    """Wall-clock per solve vs solve rank (minutes), 3-series overlay."""
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    paths = [milp_jsonl, cap20_jsonl, lp_jsonl]
    for path, (label, marker, color) in zip(paths, _SERIES_TIME, strict=True):
        if path is None or not path.exists():
            continue
        rs = _load_records(path, top_n)
        if not rs:
            continue
        ax.plot(
            [r["iteration"] for r in rs],
            [r["wall_seconds"] / 60.0 for r in rs],
            marker,
            color=color,
            linewidth=1.4,
            markersize=4,
            label=label,
        )

    ax.set_xlabel("Solve rank")
    ax.set_ylabel("Wall-clock per solve (min)")
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.55)
    ax.set_xticks(range(0, top_n + 1, max(1, top_n // 10)))
    ax.set_xlim(0.5, top_n + 0.5)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_license_sweep_heatmap(csv: Path, out: Path) -> None:
    df = pl.read_csv(csv)
    rates = sorted(set(df["r_process"].to_list()) | set(df["r_comp"].to_list()))
    n = len(rates)
    grid = np.zeros((n, n), dtype=float)
    for row in df.iter_rows(named=True):
        i = rates.index(row["r_process"])
        j = rates.index(row["r_comp"])
        grid[i, j] = row["profit"]

    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    im = ax.imshow(grid, origin="lower", cmap="viridis", aspect="auto")
    ax.set_xticks(range(n))
    ax.set_xticklabels([f"{r:.2f}" for r in rates])
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r:.2f}" for r in rates])
    ax.set_xlabel(r"$r_{\mathrm{comp}}$")
    ax.set_ylabel(r"$r_{\mathrm{process}}$")
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Profit (USD)")
    cbar.ax.tick_params(labelsize=9)
    # Annotate each cell with its $ value (compact units).
    vmax = grid.max()
    for i in range(n):
        for j in range(n):
            v = grid[i, j]
            if v >= 1e6:
                label = f"${v / 1e6:.2f}M"
            elif v >= 1e3:
                label = f"${v / 1e3:.0f}K"
            else:
                label = f"${v:.0f}"
            ax.text(
                j,
                i,
                label,
                ha="center",
                va="center",
                color="white" if v < vmax * 0.6 else "black",
                fontsize=9,
            )
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--jsonl",
        type=Path,
        default=Path("data/processed/profit_curve.jsonl"),
        help="MILP profit-curve JSONL.",
    )
    p.add_argument(
        "--lp-jsonl",
        type=Path,
        default=Path("data/processed/profit_curve_lp.jsonl"),
        help="LP-relaxation profit-curve JSONL (overlaid on plots if present).",
    )
    p.add_argument(
        "--cap20-jsonl",
        type=Path,
        default=Path("data/processed/profit_curve_cap20.jsonl"),
        help="MILP-cap=20 profit-curve JSONL (overlaid on plots if present).",
    )
    p.add_argument(
        "--art-dir",
        type=Path,
        default=Path("data/processed/writeup_artifacts"),
    )
    p.add_argument("--top-n", type=int, default=20)
    args = p.parse_args()

    _set_paper_style()

    plot_profit_vs_rank(
        args.jsonl,
        args.lp_jsonl,
        args.cap20_jsonl,
        args.top_n,
        args.art_dir / "profit_vs_rank_top20.png",
    )
    print(f"wrote {args.art_dir / 'profit_vs_rank_top20.png'}")

    plot_solve_time_vs_rank(
        args.jsonl,
        args.lp_jsonl,
        args.cap20_jsonl,
        args.top_n,
        args.art_dir / "solve_time_vs_rank_top20.png",
    )
    print(f"wrote {args.art_dir / 'solve_time_vs_rank_top20.png'}")

    for suffix in ("", "_licensed_only", "_licensed_sales"):
        csv = args.art_dir / f"uspto_license_sweep_results{suffix}.csv"
        png = args.art_dir / f"uspto_license_sweep_grid{suffix}.png"
        if not csv.exists():
            print(f"skip {png} (no source CSV: {csv})")
            continue
        plot_license_sweep_heatmap(csv, png)
        print(f"wrote {png}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
