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
    max_reactions: int,
    config: Path,
    out_dir: Path,
    log_dir: Path,
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
        "--max-reactions",
        str(max_reactions),
        "--output",
        str(out_path),
    ]
    if forbidden:
        cmd.extend(["--forbid-sell", ",".join(forbidden)])

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
    p.add_argument("--max-reactions", type=int, default=10)
    p.add_argument("--max-iterations", type=int, default=100)
    p.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/processed/profit_curve.jsonl"),
        help="Append-only JSONL with one record per iteration. Used for resume.",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/profit_curve"),
        help="Directory for per-iteration solution.json files.",
    )
    p.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs/profit_curve"),
    )
    args = p.parse_args()

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
