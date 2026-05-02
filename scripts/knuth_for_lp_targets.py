"""For each LP-chosen target, compute Knuth-Dijkstra's profit on the same molecule.

Reads `profit_curve_lp_balanced.jsonl`, runs Knuth-Dijkstra on the same
hypergraph, and for every LP iteration's `blocked_this_round` molecule
emits Knuth's cost-per-gram, sell-per-gram, and the standalone Knuth
profit (allocating the full budget to that one molecule). Profit can be
negative — it just means Knuth's per-gram model can't beat buying the
target outright (i.e., the LP is squeezing profit from shared
intermediates that Knuth's per-output cost-charging can't see).

Output schema mirrors profit_curve_*.jsonl so the plotter can overlay.

Usage:
    uv run python scripts/knuth_for_lp_targets.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from knuth_baseline import _build_rxn_meta, knuth_dijkstra_pergram

from aichemy.config import load_config
from aichemy.preprocessing.io import processed_path, read_molecules, read_reactions
from aichemy.solver.config import SolverConfig
from aichemy.solver.model import _build_mw_lookup, _build_price_lookup, _rescale_to_grams

INF = float("inf")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    p.add_argument("--budget", type=float, default=10_000.0)
    p.add_argument("--balance-filter", default="balanced")
    p.add_argument(
        "--lp-jsonl",
        type=Path,
        default=Path("data/processed/profit_curve_lp_balanced.jsonl"),
    )
    p.add_argument(
        "--out-jsonl",
        type=Path,
        default=Path("data/processed/knuth_for_lp_targets.jsonl"),
    )
    args = p.parse_args()

    lp_records = []
    with open(args.lp_jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lp_records.append(json.loads(line))
    lp_records.sort(key=lambda r: r["iteration"])
    print(f"[lookup] {len(lp_records)} LP iterations to evaluate")

    cfg = load_config(args.config, [])
    reactions = read_reactions(processed_path(cfg, "reactions.parquet"))
    molecules = read_molecules(processed_path(cfg, "molecules_with_mw.parquet"))
    print(f"[lookup] loaded {reactions.height:,} reactions, {molecules.height:,} molecules")

    rxn_meta = _build_rxn_meta(reactions, args.balance_filter)
    W = _build_mw_lookup(molecules)
    rxn_meta, _ = _rescale_to_grams(rxn_meta, W)
    C = {c for r in rxn_meta for c, _ in r["reactants"] + r["products"]}
    price_lookup = _build_price_lookup(molecules, C, SolverConfig(budget=args.budget))
    by_id = {row["mol_id"]: row for row in molecules.iter_rows(named=True)}

    initial_cost = {c: price_lookup[c][0] for c in C}
    t0 = time.monotonic()
    cost, _ = knuth_dijkstra_pergram(rxn_meta, initial_cost)
    wall = time.monotonic() - t0
    print(f"[lookup] Knuth solved in {wall:.2f}s")

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_jsonl, "w") as out:
        for rec in lp_records:
            mol_id = rec["blocked_this_round"]
            row = by_id.get(mol_id)
            sell_pg = float(row["price_per_gram"]) if row and row.get("price_per_gram") else None
            cost_pg = cost.get(mol_id, INF)
            if sell_pg is None or cost_pg == INF or cost_pg <= 0:
                profit = None
                margin = None
            else:
                margin = sell_pg / cost_pg - 1.0
                profit = args.budget * margin
            out.write(
                json.dumps(
                    {
                        "iteration": rec["iteration"],
                        "mol_id": mol_id,
                        "knuth_cost_per_gram": cost_pg if cost_pg != INF else None,
                        "knuth_sell_per_gram": sell_pg,
                        "knuth_margin": margin,
                        "knuth_profit": profit,
                        "lp_profit": rec["profit"],
                    }
                )
                + "\n"
            )
    print(f"[lookup] wrote {args.out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
