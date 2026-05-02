"""Plot wall-clock vs corpus size with multi-seed mean ± std + bootstrap CI on slope.

Reads the JSONL produced by `scripts/run_complexity_sweep.py --seeds ...`
(records with a `seed` field). For each (size, mode) computes the mean
and std of wall_seconds across seeds, plots:

  - mean as marker+line
  - shaded band = ±1 std (across seeds)
  - thin scatter for individual seed points (translucent)
  - fitted log-log line with slope ± SE (OLS on the means; bootstrap CI via
    seed resampling)

Usage:
    uv run python scripts/plot_complexity_seeds.py
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _fit_loglog(sizes: list[int], times: list[float]) -> tuple[float, float, float]:
    """Return (slope, intercept, slope_se) for log10(t) = slope*log10(N) + intercept."""
    xs = np.log10(sizes)
    ys = np.log10(times)
    n = len(xs)
    slope, intercept = np.polyfit(xs, ys, 1)
    yhat = slope * xs + intercept
    resid = ys - yhat
    sse = (resid**2).sum()
    sxx = ((xs - xs.mean()) ** 2).sum()
    sigma2 = sse / (n - 2) if n > 2 else 0.0
    slope_se = (sigma2 / sxx) ** 0.5 if sxx > 0 else 0.0
    return slope, intercept, slope_se


def _bootstrap_slope_ci(
    by_seed: dict[int, dict[int, float]], n_boot: int = 2000, alpha: float = 0.05
) -> tuple[float, float]:
    """Resample seeds with replacement, refit on the per-resample mean curve."""
    seeds = list(by_seed.keys())
    sizes = sorted({sz for d in by_seed.values() for sz in d})
    rng = np.random.default_rng(0)
    slopes: list[float] = []
    for _ in range(n_boot):
        sample = rng.choice(seeds, size=len(seeds), replace=True)
        means: list[float] = []
        for sz in sizes:
            vals = [by_seed[s][sz] for s in sample if sz in by_seed[s]]
            if not vals:
                break
            means.append(float(np.mean(vals)))
        if len(means) != len(sizes):
            continue
        slope, _, _ = _fit_loglog(sizes, means)
        slopes.append(slope)
    lo, hi = np.percentile(slopes, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--jsonl",
        type=Path,
        default=Path("data/processed/complexity_sweep_seeds.jsonl"),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/writeup_artifacts/complexity_scaling_seeds.png"),
    )
    p.add_argument("--modes", default="MILP,LP")
    args = p.parse_args()

    plt.rcParams.update(
        {
            "axes.labelsize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
            "font.family": "sans-serif",
        }
    )

    with open(args.jsonl) as _f:
        records = [json.loads(line) for line in _f if line.strip()]
    modes = [m.strip() for m in args.modes.split(",")]
    style = {
        "MILP": ("o-", "#1f77b4"),
        "LP": ("^--", "#ff7f0e"),
        "MILP-cap20": ("s-.", "#2ca02c"),
    }

    fig, ax = plt.subplots(figsize=(6.0, 4.0))

    summary_lines: list[str] = []

    for mode in modes:
        rows = [r for r in records if r["mode"] == mode]
        if not rows:
            continue
        # by_seed[seed][size] = wall_seconds
        by_seed: dict[int, dict[int, float]] = defaultdict(dict)
        for r in rows:
            by_seed[int(r.get("seed", 42))][int(r["size"])] = float(r["wall_seconds"])
        sizes = sorted({sz for d in by_seed.values() for sz in d})
        means = []
        stds = []
        for sz in sizes:
            vals = [by_seed[s][sz] for s in by_seed if sz in by_seed[s]]
            means.append(float(np.mean(vals)))
            stds.append(float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0)

        marker, color = style.get(mode, ("o-", "gray"))

        # individual seed scatter (faint)
        for s in by_seed:
            xs = sorted(by_seed[s])
            ys = [by_seed[s][x] for x in xs]
            ax.plot(xs, ys, marker=".", linestyle="None", color=color, alpha=0.25, markersize=4)

        # mean line + ±1 std band
        ax.plot(sizes, means, marker, color=color, linewidth=1.8, markersize=5, label=mode)
        upper = [m + s for m, s in zip(means, stds, strict=True)]
        lower = [max(m - s, 1e-6) for m, s in zip(means, stds, strict=True)]
        ax.fill_between(sizes, lower, upper, color=color, alpha=0.18, linewidth=0)

        # fits
        slope_mean, _intercept, slope_se = _fit_loglog(sizes, means)
        ci_lo, ci_hi = _bootstrap_slope_ci(by_seed)
        summary_lines.append(
            f"{mode:<10} N^{slope_mean:.2f} (OLS-SE ±{slope_se:.2f}, "
            f"bootstrap 95% CI [{ci_lo:.2f}, {ci_hi:.2f}])"
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Reaction subset size N")
    ax.set_ylabel("Wall-clock per solve (s)")
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.55)
    ax.legend(loc="upper left", frameon=False)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out)
    plt.close(fig)

    print(f"wrote {args.out}\n")
    print("=== fit summary ===")
    for line in summary_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
