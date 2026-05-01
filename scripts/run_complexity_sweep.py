"""Wall-clock vs corpus-size complexity sweep for MILP and LP solvers.

Samples nested subsets of the rdkit-balanced reaction corpus at a series
of sizes, runs `build_and_solve` in both MILP and LP modes for each
subset, and records wall-clock time, profit, and reaction/sale counts.

Output is appended to a JSONL so the sweep is interrupt-safe and
resumable: re-running with a partial JSONL skips the (size, mode) pairs
already recorded.

Usage:
    uv run python scripts/run_complexity_sweep.py
    uv run python scripts/run_complexity_sweep.py \
        --sizes 500,1000,2000,5000,10000,20000,50000,100000,200000
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _load_done(jsonl: Path) -> set[tuple[int, str]]:
    """Return the (size, mode) pairs already recorded in jsonl."""
    if not jsonl.exists():
        return set()
    done: set[tuple[int, str]] = set()
    with open(jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            done.add((int(r["size"]), str(r["mode"])))
    return done


def _filter_molecules(reactions: pl.DataFrame, molecules: pl.DataFrame) -> pl.DataFrame:
    """Restrict molecules to those referenced by the given reaction subset."""
    referenced: set[str] = set()
    for row in reactions.iter_rows(named=True):
        for side in ("reactants", "products"):
            for p in row[side]:
                referenced.add(p["mol_id"])
    return molecules.filter(pl.col("mol_id").is_in(list(referenced)))


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
        "--sizes",
        default="500,1000,2000,5000,10000,20000,50000,100000,200000",
        help="Comma-separated subset sizes. Special value 'full' = entire balanced corpus.",
    )
    p.add_argument("--seed", type=int, default=42, help="Shuffle seed for nested subsets.")
    p.add_argument("--budget", type=float, default=10_000.0)
    p.add_argument(
        "--include-full",
        action="store_true",
        help="Append the full corpus size to the sweep.",
    )
    p.add_argument(
        "--modes",
        default="MILP,LP",
        help="Comma-separated solver modes to run.",
    )
    p.add_argument(
        "--out-jsonl",
        type=Path,
        default=Path("data/processed/complexity_sweep.jsonl"),
    )
    args = p.parse_args()

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    done = _load_done(args.out_jsonl)
    if done:
        print(f"resume: {len(done)} (size, mode) pairs already recorded — will skip", flush=True)

    print(f"loading {args.reactions}", flush=True)
    reactions_all = pl.read_parquet(args.reactions).filter(pl.col("rdkit_balanced"))
    print(f"loading {args.molecules}", flush=True)
    molecules = pl.read_parquet(args.molecules)
    print(
        f"corpus: {reactions_all.height:,} rdkit_balanced reactions, "
        f"{molecules.height:,} molecules",
        flush=True,
    )

    shuffled = reactions_all.sample(n=reactions_all.height, seed=args.seed, with_replacement=False)

    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    if args.include_full and shuffled.height not in sizes:
        sizes.append(shuffled.height)
    sizes = sorted(set(sizes))
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    print(f"sizes: {sizes}\nmodes: {modes}", flush=True)

    out_f = open(args.out_jsonl, "a")
    try:
        for size in sizes:
            if size > shuffled.height:
                print(f"size {size:,} > corpus size {shuffled.height:,} — clipping", flush=True)
                size = shuffled.height
            sub = shuffled.head(size)
            mol_subset = _filter_molecules(sub, molecules)
            print(
                f"\n=== size={size:,} rxns, {mol_subset.height:,} mols ===",
                flush=True,
            )
            for mode in modes:
                if (size, mode) in done:
                    print(f"  {mode}: cached, skipping", flush=True)
                    continue
                cfg = SolverConfig(budget=args.budget, lp_mode=(mode == "LP"))
                t0 = time.monotonic()
                sol = build_and_solve(sub, mol_subset, cfg)
                wall = time.monotonic() - t0
                rec = {
                    "size": size,
                    "mode": mode,
                    "n_molecules": int(mol_subset.height),
                    "wall_seconds": wall,
                    "status": sol.status,
                    "profit": float(sol.objective_value),
                    "n_activated": len(sol.activated_reactions),
                    "n_sold": len(sol.sold_molecules),
                    "n_purchased": len(sol.purchased_molecules),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                out_f.write(json.dumps(rec) + "\n")
                out_f.flush()
                print(
                    f"  {mode}: {wall:7.2f}s  status={sol.status:<10}  "
                    f"profit=${rec['profit']:>14,.0f}  "
                    f"n_act={rec['n_activated']:>3}  n_sold={rec['n_sold']:>3}",
                    flush=True,
                )
    finally:
        out_f.close()

    print("\ndone.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
