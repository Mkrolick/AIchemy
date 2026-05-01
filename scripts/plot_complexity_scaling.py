"""Plot wall-clock vs corpus-size scaling for MILP and LP solvers.

Reads the JSONL produced by `scripts/run_complexity_sweep.py` and writes
a paper-clean log-log scatter+line of wall-clock seconds vs reaction
subset size, with both solver modes overlaid.

Usage:
    uv run python scripts/plot_complexity_scaling.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--jsonl",
        type=Path,
        default=Path("data/processed/complexity_sweep.jsonl"),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/writeup_artifacts/complexity_scaling.png"),
    )
    args = p.parse_args()

    df = pl.read_ndjson(args.jsonl).sort(["mode", "size"])

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

    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    styles = {
        "MILP": ("o-", "#1f77b4"),
        "LP": ("^--", "#ff7f0e"),
    }
    for mode, (marker, color) in styles.items():
        d = df.filter(pl.col("mode") == mode)
        if d.is_empty():
            continue
        ax.plot(
            d["size"].to_list(),
            d["wall_seconds"].to_list(),
            marker,
            color=color,
            linewidth=1.5,
            markersize=5,
            label=mode,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Reaction subset size")
    ax.set_ylabel("Wall-clock per solve (s)")
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.55)
    ax.legend(loc="upper left", frameon=False)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out)
    plt.close(fig)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
