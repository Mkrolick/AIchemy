#!/usr/bin/env python3
"""Plot the iterative-forbid-top profit-curve loop's outputs.

Reads ``data/processed/profit_curve.jsonl`` (one record per iteration of
the loop produced by ``scripts/profit_curve_loop.py``) and writes:

  - ``profit_vs_rank_top20.png``   profit ($) vs iteration rank, first 20
  - ``solve_time_vs_rank_top20.png`` wall-seconds per solve, first 20

Both plots use only the first 20 iterations (the "top 20 solves" of the
loop, since each iteration finds the next-best route after blocking the
prior winner).

Usage:
    uv run python scripts/plot_profit_curve.py
    uv run python scripts/plot_profit_curve.py --jsonl path/to/curve.jsonl --out-dir custom/out
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--jsonl",
        type=Path,
        default=Path("data/processed/profit_curve.jsonl"),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/writeup_artifacts"),
    )
    p.add_argument("--top-n", type=int, default=20)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    with open(args.jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    records.sort(key=lambda r: r["iteration"])
    records = records[: args.top_n]
    print(f"loaded {len(records)} iterations from {args.jsonl}", flush=True)

    iters = [r["iteration"] for r in records]
    profits = [r["profit"] for r in records]
    secs = [r["wall_seconds"] for r in records]

    # ---------------- profit vs rank ----------------
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(iters, profits, "o-", color="#1f77b4", linewidth=1.6, markersize=5)
    ax.set_xlabel("Solve rank (iteration)")
    ax.set_ylabel("Solver profit ($)")
    ax.set_title(f"Top-{len(records)} solves: profit vs rank (top product blocked each iteration)")
    ax.set_yscale("log")
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.set_xticks(iters[:: max(1, len(iters) // 10)])
    fig.tight_layout()
    profit_path = args.out_dir / "profit_vs_rank_top20.png"
    fig.savefig(profit_path, dpi=160)
    plt.close(fig)
    print(f"wrote {profit_path}", flush=True)

    # ---------------- solve time vs rank ----------------
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(iters, secs, "s-", color="#d62728", linewidth=1.6, markersize=5)
    ax.set_xlabel("Solve rank (iteration)")
    ax.set_ylabel("Wall-clock per solve (seconds)")
    ax.set_title(f"Top-{len(records)} solves: per-solve runtime grows as the forbid list expands")
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.set_xticks(iters[:: max(1, len(iters) // 10)])
    fig.tight_layout()
    time_path = args.out_dir / "solve_time_vs_rank_top20.png"
    fig.savefig(time_path, dpi=160)
    plt.close(fig)
    print(f"wrote {time_path}", flush=True)

    # Side note: simple summary stats for the writeup
    print(f"  profit[1] = ${profits[0]:,.0f}")
    print(f"  profit[{len(profits)}] = ${profits[-1]:,.0f}")
    print(f"  solve-time[1] = {secs[0]:.1f} s")
    print(f"  solve-time[{len(secs)}] = {secs[-1]:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
