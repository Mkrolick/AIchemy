#!/usr/bin/env python3
"""Iterative profit-curve runner.

Repeatedly runs the MILP solver with --max-reactions=N. After each solve,
identifies the highest-revenue sold molecule, adds it to a growing
forbidden list, and re-runs. The result is a profit-vs-iteration curve
that maps how concentrated the value is in the top products.

Interrupt-safe:
    - State JSONL is appended after each iteration; Ctrl+C loses at most
      the current iteration.
    - Resume on next invocation: the script reads the existing JSONL,
      reconstructs the forbidden list, and continues numbering from the
      last recorded iteration + 1.

Usage:
    uv run python scripts/profit_curve_loop.py
    uv run python scripts/profit_curve_loop.py --max-reactions 10 --max-iterations 100

Outputs:
    data/processed/profit_curve.jsonl       # append-only record (one line per iteration)
    data/processed/profit_curve/iter_NNNN.json   # full solver output per iteration
    logs/profit_curve/iter_NNNN.log         # solver stdout/stderr per iteration

Each JSONL record:
    {
      "iteration": 1,
      "profit": 377877066.62,
      "blocked_this_round": "MNXM731718",
      "blocked_at_start_of_round": [],
      "top_revenue": 336468497.99,
      "n_sold": 6,
      "n_activated": 15,
      "wall_seconds": 44.3,
      "timestamp": "2026-04-29T04:00:00+00:00"
    }
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def run_one_iteration(
    iteration: int,
    forbidden: list[str],
    *,
    max_reactions: int | None,
    config: Path,
    out_dir: Path,
    log_dir: Path,
    lp_mode: bool = False,
    balance_filter: str | None = None,
    time_limit: int | None = None,
) -> dict | None:
    """Run one solve. Returns the JSONL record, or None if the loop should stop."""
    out_path = out_dir / f"iter_{iteration:04d}.json"
    log_path = log_dir / f"iter_{iteration:04d}.log"

    cmd = [
        "uv",
        "run",
        "aichemy",
        "solve",
        "run",
        "--config",
        str(config),
        "--output",
        str(out_path),
    ]
    if max_reactions is not None:
        cmd.extend(["--max-reactions", str(max_reactions)])
    if forbidden:
        cmd.extend(["--forbid-sell", ",".join(forbidden)])
    if lp_mode:
        # In LP mode the solver auto-strips the cardinality constraint; passing
        # --max-reactions is harmless but the cap won't bind.
        cmd.append("--lp-mode")
    if balance_filter is not None:
        cmd.extend(["--balance-filter", balance_filter])
    if time_limit is not None:
        cmd.extend(["--time-limit", str(time_limit)])

    print(
        f"[iter {iteration}] solving with {len(forbidden)} forbidden, output={out_path.name}",
        flush=True,
    )

    started = time.monotonic()
    with open(log_path, "w") as logf:
        result = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT)
    wall = time.monotonic() - started

    if result.returncode != 0:
        print(
            f"[iter {iteration}] solver failed (returncode={result.returncode}); see {log_path}",
            flush=True,
        )
        return None
    if not out_path.exists():
        print(
            f"[iter {iteration}] solver wrote no output; see {log_path}",
            flush=True,
        )
        return None

    sol = json.loads(out_path.read_text())
    sold = sol.get("sold_molecules", [])
    if not sold:
        print(f"[iter {iteration}] no products sold — terminating loop", flush=True)
        return None

    top = max(sold, key=lambda s: s.get("revenue", 0.0))
    return {
        "iteration": iteration,
        "profit": sol.get("objective_value", 0.0),
        "blocked_this_round": top["mol_id"],
        "top_revenue": top.get("revenue", 0.0),
        "blocked_at_start_of_round": list(forbidden),
        "n_sold": len(sold),
        "n_activated": len(sol.get("activated_reactions", [])),
        "wall_seconds": wall,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def load_resume_state(jsonl_path: Path) -> tuple[int, list[str]]:
    """Read existing JSONL (if any) and reconstruct (last_iteration, forbidden_list)."""
    if not jsonl_path.exists():
        return 0, []
    last = 0
    forbidden: list[str] = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            last = max(last, rec["iteration"])
            forbidden.append(rec["blocked_this_round"])
    return last, forbidden


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    p.add_argument(
        "--max-reactions",
        type=int,
        default=None,
        help="Cap on activated reactions per solve. Omit for uncapped MILP.",
    )
    p.add_argument("--max-iterations", type=int, default=100)
    p.add_argument(
        "--lp-mode",
        action="store_true",
        help=(
            "Run each solve as an LP relaxation (drops integer y_r / w_c). "
            "Default state-file and per-iteration output paths get an "
            "_lp suffix so the LP curve doesn't clobber the MILP curve."
        ),
    )
    p.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help=(
            "Append-only JSONL with one record per iteration. Used for resume. "
            "Defaults: data/processed/profit_curve.jsonl (MILP) or "
            "data/processed/profit_curve_lp.jsonl (LP)."
        ),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=(
            "Directory for per-iteration solution.json files. Defaults: "
            "data/processed/profit_curve/ (MILP) or "
            "data/processed/profit_curve_lp/ (LP)."
        ),
    )
    p.add_argument(
        "--log-dir",
        type=Path,
        default=None,
    )
    p.add_argument(
        "--balance-filter",
        choices=("balanced", "rdkit_balanced"),
        default=None,
        help=(
            "Pass-through to `aichemy solve run --balance-filter`. Omit to use "
            "the solver's own default ('balanced')."
        ),
    )
    p.add_argument(
        "--time-limit",
        type=int,
        default=None,
        help=(
            "Pass-through to `aichemy solve run --time-limit`: per-iter CBC "
            "wall-clock cap in seconds. Use for large MILPs where proving "
            "optimality is intractable but a near-optimal answer is acceptable."
        ),
    )
    args = p.parse_args()

    # Default paths depend on lp_mode so MILP and LP runs land in distinct files.
    suffix = "_lp" if args.lp_mode else ""
    if args.state_file is None:
        args.state_file = Path(f"data/processed/profit_curve{suffix}.jsonl")
    if args.out_dir is None:
        args.out_dir = Path(f"data/processed/profit_curve{suffix}")
    if args.log_dir is None:
        args.log_dir = Path(f"logs/profit_curve{suffix}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    args.state_file.parent.mkdir(parents=True, exist_ok=True)

    last_iter, forbidden = load_resume_state(args.state_file)
    if last_iter > 0:
        print(
            f"resuming: last_iter={last_iter}, already_forbidden={len(forbidden)}",
            flush=True,
        )

    # Graceful interrupt: set a flag, let the current iteration finish.
    # (SIGINT during subprocess.run will also be delivered to the child,
    # but if it kills CBC mid-solve, that iteration just won't get
    # recorded — the next start resumes cleanly.)
    interrupted = False

    def _on_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True
        print("\n[interrupt] will stop after current iteration completes", flush=True)

    signal.signal(signal.SIGINT, _on_sigint)

    iteration = last_iter
    while iteration < args.max_iterations:
        iteration += 1
        record = run_one_iteration(
            iteration,
            forbidden,
            max_reactions=args.max_reactions,
            config=args.config,
            out_dir=args.out_dir,
            log_dir=args.log_dir,
            lp_mode=args.lp_mode,
            balance_filter=args.balance_filter,
            time_limit=args.time_limit,
        )
        if record is None:
            break
        # Atomic append: open/write/close per iteration so an interrupt
        # mid-write loses at most one line.
        with open(args.state_file, "a") as f:
            f.write(json.dumps(record) + "\n")
        forbidden.append(record["blocked_this_round"])
        print(
            f"[iter {iteration}] profit=${record['profit']:,.0f} "
            f"blocked={record['blocked_this_round']} "
            f"top_rev=${record['top_revenue']:,.0f} "
            f"({record['wall_seconds']:.1f}s wall)",
            flush=True,
        )
        if interrupted:
            print(f"[interrupt] stopped cleanly after iteration {iteration}", flush=True)
            break

    print(f"\ndone. {iteration} iterations recorded in {args.state_file}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
