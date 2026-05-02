"""Two paper-clean plots overlaying Knuth-Dijkstra vs LP relaxation.

Reads the JSONLs:
  - data/processed/profit_curve_knuth_balanced.jsonl
  - data/processed/profit_curve_lp_balanced.jsonl

Writes:
  - <art-dir>/dijkstra_vs_lp_profit_vs_rank.png
  - <art-dir>/dijkstra_vs_lp_solve_time_vs_rank.png

Usage:
    uv run python scripts/plot_dijkstra_vs_lp.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def _set_paper_style() -> None:
    plt.rcParams.update(
        {
            "axes.labelsize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
            "font.family": "sans-serif",
        }
    )


def _load(jsonl: Path, top_n: int) -> list[dict]:
    rs = []
    with open(jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rs.append(json.loads(line))
    rs.sort(key=lambda r: r["iteration"])
    return rs[:top_n]


def plot_profit(knuth_for_lp: list[dict], lp: list[dict], top_n: int, out: Path) -> None:
    """LP iter N profit vs Knuth profit on the SAME molecule LP picked at iter N."""
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    if lp:
        ax.plot(
            [r["iteration"] for r in lp],
            [r["profit"] for r in lp],
            "^--",
            color="#ff7f0e",
            linewidth=1.4,
            markersize=4,
            label="LP relaxation",
        )
    if knuth_for_lp:
        ax.plot(
            [r["iteration"] for r in knuth_for_lp],
            [(r["knuth_profit"] or 0.0) for r in knuth_for_lp],
            "D-",
            color="#9467bd",
            linewidth=1.4,
            markersize=4,
            label="Knuth-Dijkstra (same target)",
        )

    from matplotlib.ticker import FuncFormatter

    ax.set_xlabel("Solve rank")
    ax.set_ylabel("Profit (USD, millions)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e6:,.0f}"))
    ax.set_ylim(bottom=0)
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.55)
    ax.set_xticks(range(0, top_n + 1, max(1, top_n // 10)))
    ax.set_xlim(0.5, top_n + 0.5)
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_solve_time(knuth: list[dict], lp: list[dict], top_n: int, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    if knuth:
        ax.plot(
            [r["iteration"] for r in knuth],
            [r["wall_seconds"] for r in knuth],
            "D-",
            color="#9467bd",
            linewidth=1.4,
            markersize=4,
            label="Knuth-Dijkstra (total / N)",
        )
    if lp:
        ax.plot(
            [r["iteration"] for r in lp],
            [r["wall_seconds"] for r in lp],
            "^--",
            color="#ff7f0e",
            linewidth=1.4,
            markersize=4,
            label="LP relaxation",
        )

    ax.set_xlabel("Solve rank")
    ax.set_ylabel("Wall-clock per solve (s)")
    ax.set_yscale("log")
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.55)
    ax.set_xticks(range(0, top_n + 1, max(1, top_n // 10)))
    ax.set_xlim(0.5, top_n + 0.5)
    ax.legend(loc="best", frameon=False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--knuth-jsonl",
        type=Path,
        default=Path("data/processed/profit_curve_knuth_balanced.jsonl"),
        help="Knuth's own top-N ranking (used for the wall-clock plot only).",
    )
    p.add_argument(
        "--knuth-for-lp-jsonl",
        type=Path,
        default=Path("data/processed/knuth_for_lp_targets.jsonl"),
        help="Knuth profit on each LP-chosen target (used for the profit plot).",
    )
    p.add_argument(
        "--lp-jsonl",
        type=Path,
        default=Path("data/processed/profit_curve_lp_balanced.jsonl"),
    )
    p.add_argument(
        "--art-dir",
        type=Path,
        default=Path("data/processed/writeup_artifacts"),
    )
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument(
        "--out-suffix",
        default="",
        help="Suffix appended to output PNG basenames, e.g. '_rdkit_balanced'.",
    )
    args = p.parse_args()

    _set_paper_style()
    args.art_dir.mkdir(parents=True, exist_ok=True)

    knuth = _load(args.knuth_jsonl, args.top_n) if args.knuth_jsonl.exists() else []
    knuth_for_lp = (
        _load(args.knuth_for_lp_jsonl, args.top_n) if args.knuth_for_lp_jsonl.exists() else []
    )
    lp = _load(args.lp_jsonl, args.top_n) if args.lp_jsonl.exists() else []

    sfx = args.out_suffix
    out_profit = args.art_dir / f"dijkstra_vs_lp_profit_vs_rank{sfx}.png"
    out_time = args.art_dir / f"dijkstra_vs_lp_solve_time_vs_rank{sfx}.png"
    plot_profit(knuth_for_lp, lp, args.top_n, out_profit)
    plot_solve_time(knuth, lp, args.top_n, out_time)
    print(f"wrote {out_profit}")
    print(f"wrote {out_time}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
