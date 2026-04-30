#!/usr/bin/env python3
"""Single-product-dominance hypothesis test on solver-generated solutions.

Constructs N independent random subsets of the rdkit-balanced reaction
network, solves each with the MILP, and records whether any single
product accounts for ≥ ``dominance_threshold`` of total revenue.

The trials produce a binary sequence (dominates / does not dominate).
A one-sided exact binomial test (H₀: p ≤ p₀, H_a: p > p₀, default
p₀=0.5) is run against the null hypothesis that dominance is a
chance-level outcome.

Output structure:
    {out_dir}/
        results.csv        # one row per trial
        summary.json       # n, k, p-value, decision at α
        report.md          # paste-ready paragraph for write-up
        trials/
            trial_NNN.json # full solver solution per trial

Usage:
    uv run python scripts/test_dominance_hypothesis.py \
        --n-trials 30 \
        --reactions-per-subset 500 \
        --dominance-threshold 0.5 \
        --alpha 0.01 \
        --out-dir data/processed/dominance_test
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from scipy.stats import binomtest

# Solver (used in-process; no subprocess spawn overhead).
from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _dominance_ratio(sold_molecules: list[dict]) -> tuple[float, str | None]:
    """Return (top_share_of_total_revenue, top_mol_id) for a solution.

    If no product is sold, returns (0.0, None).
    """
    if not sold_molecules:
        return 0.0, None
    revenues = [(s["mol_id"], s.get("revenue", 0.0)) for s in sold_molecules]
    total = sum(r for _, r in revenues)
    if total <= 0:
        return 0.0, None
    top_id, top_rev = max(revenues, key=lambda x: x[1])
    return top_rev / total, top_id


def _solve_one(
    trial_id: int,
    sub: pl.DataFrame,
    molecules: pl.DataFrame,
    cfg: SolverConfig,
) -> dict:
    """Solve on a pre-sampled subset; return a per-trial record."""
    # Restrict molecules to those referenced by the sampled reactions for
    # a faster build and a cleaner per-subset corpus.
    referenced: set[str] = set()
    for row in sub.iter_rows(named=True):
        for side in ("reactants", "products"):
            for p in row[side]:
                referenced.add(p["mol_id"])
    mol_subset = molecules.filter(pl.col("mol_id").is_in(list(referenced)))

    started = time.monotonic()
    sol = build_and_solve(sub, mol_subset, cfg)
    wall = time.monotonic() - started

    ratio, top_id = _dominance_ratio(sol.sold_molecules)
    return {
        "trial": trial_id,
        "n_reactions_sampled": sub.height,
        "n_molecules_referenced": mol_subset.height,
        "status": sol.status,
        "objective_value": float(sol.objective_value),
        "n_activated": len(sol.activated_reactions),
        "n_sold": len(sol.sold_molecules),
        "top_mol_id": top_id,
        "top_revenue": next(
            (s["revenue"] for s in sol.sold_molecules if s["mol_id"] == top_id), 0.0
        ),
        "total_revenue": sum(s.get("revenue", 0.0) for s in sol.sold_molecules),
        "dominance_ratio": ratio,
        "wall_seconds": wall,
        "solution": sol.to_dict(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--reactions",
        type=Path,
        default=Path("data/interim/selected/reactions.parquet"),
        help=(
            "Source reactions table. Default is the 100k curated subsample "
            "(data/interim/selected/reactions.parquet). For full-corpus runs "
            "pass data/processed/reactions.parquet."
        ),
    )
    p.add_argument(
        "--molecules", type=Path, default=Path("data/processed/molecules_with_mw.parquet")
    )
    p.add_argument("--n-trials", type=int, default=30)
    p.add_argument(
        "--dominance-threshold",
        type=float,
        default=0.5,
        help="A solution counts as 'dominated' if top-product revenue ≥ this fraction of total.",
    )
    p.add_argument(
        "--null-prob",
        type=float,
        default=0.5,
        help="Null hypothesis probability of dominance per trial (one-sided binomial test).",
    )
    p.add_argument("--alpha", type=float, default=0.01, help="Significance threshold.")
    p.add_argument("--budget", type=float, default=10_000.0)
    p.add_argument(
        "--max-reactions",
        type=int,
        default=10,
        help="Solver --max-reactions cap. Smaller = faster solves.",
    )
    p.add_argument(
        "--shuffle-seed",
        type=int,
        default=42,
        help="Seed for the global shuffle before partitioning into N disjoint chunks.",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/dominance_test"),
    )
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "trials").mkdir(parents=True, exist_ok=True)

    print(f"[dominance-test] loading {args.reactions}", flush=True)
    reactions = pl.read_parquet(args.reactions)
    print(f"[dominance-test] loading {args.molecules}", flush=True)
    molecules = pl.read_parquet(args.molecules)

    # Random shuffle, then disjoint partition into n_trials chunks. The
    # solver will further filter to rdkit_balanced internally; we don't
    # pre-filter here so the per-chunk size stays equal across trials.
    shuffled = reactions.sample(n=reactions.height, seed=args.shuffle_seed, with_replacement=False)
    base_size = shuffled.height // args.n_trials
    remainder = shuffled.height - base_size * args.n_trials
    print(
        f"[dominance-test] partitioning {shuffled.height:,} reactions into "
        f"{args.n_trials} disjoint chunks of ~{base_size:,} (remainder {remainder} "
        f"into the last chunk)",
        flush=True,
    )

    base_cfg = SolverConfig(budget=args.budget, max_reactions=args.max_reactions)

    records: list[dict] = []
    started = time.monotonic()
    cursor = 0
    for i in range(1, args.n_trials + 1):
        # Last chunk absorbs the remainder so all rows are used.
        chunk_size = base_size + (remainder if i == args.n_trials else 0)
        sub = shuffled.slice(cursor, chunk_size)
        cursor += chunk_size
        rec = _solve_one(
            trial_id=i,
            sub=sub,
            molecules=molecules,
            cfg=base_cfg,
        )
        # Save full solution to disk.
        (args.out_dir / "trials" / f"trial_{i:03d}.json").write_text(
            json.dumps(rec["solution"], indent=2)
        )
        # Drop the bulky `solution` field from the record table.
        rec.pop("solution", None)
        records.append(rec)
        elapsed = time.monotonic() - started
        eta = (args.n_trials - i) * (elapsed / i) if i else 0.0
        print(
            f"[dominance-test] trial {i:>2}/{args.n_trials}  "
            f"profit=${rec['objective_value']:>12,.0f}  "
            f"top={rec['top_mol_id']!s:<15}  "
            f"dom={rec['dominance_ratio']:.3f}  "
            f"({rec['wall_seconds']:.1f}s)  eta {eta:.0f}s",
            flush=True,
        )

    # Per-trial CSV.
    df = pl.DataFrame(records)
    df.write_csv(args.out_dir / "results.csv")

    # Binary outcome: did one product dominate (≥ threshold)?
    k = int((df["dominance_ratio"] >= args.dominance_threshold).sum())
    n = df.height

    # One-sided binomial test against H₀: p ≤ null_prob.
    bt = binomtest(k=k, n=n, p=args.null_prob, alternative="greater")
    p_value = float(bt.pvalue)
    decision = "reject H₀" if p_value < args.alpha else "fail to reject H₀"

    summary = {
        "n_trials": n,
        "n_dominated": k,
        "dominance_threshold": args.dominance_threshold,
        "null_prob": args.null_prob,
        "alpha": args.alpha,
        "binomial_p_value": p_value,
        "decision": decision,
        "source_reactions": str(args.reactions),
        "total_reactions_partitioned": int(shuffled.height),
        "shuffle_seed": args.shuffle_seed,
        "max_reactions": args.max_reactions,
        "budget": args.budget,
        "median_dominance_ratio": float(df["dominance_ratio"].median() or 0.0),
        "mean_dominance_ratio": float(df["dominance_ratio"].mean() or 0.0),
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # Paste-ready Markdown.
    report = (
        "# Single-product dominance hypothesis test\n\n"
        f"We test if the solver generates solutions where one sellable "
        f"product dominates the total return. We partition the {shuffled.height:,}-"
        f"reaction parsed network ({args.reactions.name}) into **{n}** "
        f"independent disjoint random subsets (~{shuffled.height // n:,} reactions "
        f"each, shuffle seed {args.shuffle_seed}) and run the MILP solver on "
        f"each (budget=${args.budget:,.0f}, --max-reactions {args.max_reactions}). "
        f"In each solution, we check the binary outcome of H₀ where no product "
        f"dominates and H_a where only one product dominates, where *dominance* "
        f"= top-product revenue / total revenue ≥ {args.dominance_threshold:.2f}. "
        f"We tested at a significance threshold of α = {args.alpha:.2f} via a "  # noqa: RUF001
        f"one-sided exact binomial test against H₀: p ≤ {args.null_prob:.2f}.\n\n"
        f"## Result\n\n"
        f"- **{k} of {n}** trials produced a single-product-dominated solution\n"
        f"- median dominance ratio: {summary['median_dominance_ratio']:.3f}\n"
        f"- mean dominance ratio: {summary['mean_dominance_ratio']:.3f}\n"
        f"- one-sided binomial p-value: **{p_value:.3g}**\n"
        f"- α = {args.alpha} → **{decision}**\n"  # noqa: RUF001
    )
    (args.out_dir / "report.md").write_text(report)

    print()
    print("=" * 60)
    print(report)
    print(f"[dominance-test] artifacts → {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
