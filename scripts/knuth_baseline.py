"""Knuth-Dijkstra B-hyperpath baseline for comparison vs LP/MILP.

Computes the cheapest per-gram cost to produce every reachable molecule
on the same reaction hypergraph the MILP solves over. The recurrence is

    c[v] = min over reactions r producing v of:
             (Σ_i a_{i,r} · c[reactant_i]) / (a_{v,r} · η_r)

where a_{·,r} are *gram* coefficients (mol stoichiometry × MW, after the
mass-basis rescale) and η_r is the yield. Catalog molecules anchor at
c[v] = price_per_gram_buy.

For multi-output reactions, each output's per-gram cost is computed
*independently* from the same reaction — Knuth charges 100% of the
reactant cost to each branch. This is the canonical limitation of
Knuth-Dijkstra on B-hypergraphs: shared sub-DAGs (which the LP captures
via mass balance) are not modeled here. That's the whole point of the
comparison.

Output: data/processed/profit_curve_knuth.jsonl, one record per rank in
the same schema profit_curve_loop.py uses, so the existing plot script
can overlay it on the MILP / LP curves.

Usage:
    uv run python scripts/knuth_baseline.py
    uv run python scripts/knuth_baseline.py --top-n 20 --budget 10000
"""

from __future__ import annotations

import argparse
import heapq
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from aichemy.config import load_config
from aichemy.preprocessing.io import processed_path, read_molecules, read_reactions
from aichemy.solver.config import SolverConfig
from aichemy.solver.model import (
    _build_mw_lookup,
    _build_price_lookup,
    _rescale_to_grams,
)

INF = float("inf")


def _build_rxn_meta(reactions: pl.DataFrame, balance_filter: str) -> list[dict[str, Any]]:
    """Mirror build_and_solve's filter + reactant/product extraction."""
    if balance_filter in reactions.columns:
        reactions = reactions.filter(pl.col(balance_filter))

    out: list[dict[str, Any]] = []
    for row in reactions.iter_rows(named=True):
        yr = row.get("yield_rate")
        yld = 0.85 if yr is None else float(yr)
        reactants = [(s["mol_id"], float(s["coefficient"])) for s in row["reactants"]]
        products = [(s["mol_id"], float(s["coefficient"])) for s in row["products"]]
        out.append(
            {
                "rxn_id": row["rxn_id"],
                "yield_rate": yld,
                "reactants": reactants,
                "products": products,
            }
        )
    return out


def knuth_dijkstra_pergram(
    rxn_meta: list[dict[str, Any]],
    initial_cost: dict[str, float],
) -> tuple[dict[str, float], dict[str, str]]:
    """Run Knuth-Dijkstra on the B-hypergraph in per-gram cost units.

    Args:
        rxn_meta: reactions with gram-rescaled (mol_id, a_grams) tuples
                  on each side and a 'yield_rate' field.
        initial_cost: c[v] for catalog molecules. Defaults to +inf for
                      any molecule not in this map.

    Returns:
        (cost_per_gram, best_reaction)
            cost_per_gram[v] = cheapest known per-gram cost ($/g)
            best_reaction[v] = rxn_id of the reaction that achieved it
                               (absent for catalog molecules)
    """
    cost: dict[str, float] = dict(initial_cost)
    best_rxn: dict[str, str] = {}
    settled: set[str] = set()
    pq: list[tuple[float, int, str]] = []
    counter = 0

    for c_id, c_val in initial_cost.items():
        if c_val < INF:
            heapq.heappush(pq, (c_val, counter, c_id))
            counter += 1

    rxn_by_id = {r["rxn_id"]: r for r in rxn_meta}
    reactions_with_reactant: dict[str, list[str]] = defaultdict(list)
    unsettled_count: dict[str, int] = {}
    for r in rxn_meta:
        unique_reactants = {c for (c, _) in r["reactants"]}
        unsettled_count[r["rxn_id"]] = len(unique_reactants)
        for c in unique_reactants:
            reactions_with_reactant[c].append(r["rxn_id"])

    n_relax = 0
    while pq:
        c_v, _, v = heapq.heappop(pq)
        if v in settled:
            continue
        if c_v > cost.get(v, INF):
            continue
        settled.add(v)

        for rxn_id in reactions_with_reactant.get(v, []):
            unsettled_count[rxn_id] -= 1
            if unsettled_count[rxn_id] != 0:
                continue
            r = rxn_by_id[rxn_id]
            yld = r["yield_rate"]
            if yld <= 0:
                continue
            reactant_total = 0.0
            bad = False
            for c_i, a_i in r["reactants"]:
                ci = cost.get(c_i, INF)
                if ci == INF:
                    bad = True
                    break
                reactant_total += a_i * ci
            if bad:
                continue
            for p_id, a_p in r["products"]:
                if a_p <= 0:
                    continue
                cost_via_r = reactant_total / (a_p * yld)
                if cost_via_r < cost.get(p_id, INF):
                    cost[p_id] = cost_via_r
                    best_rxn[p_id] = rxn_id
                    heapq.heappush(pq, (cost_via_r, counter, p_id))
                    counter += 1
                    n_relax += 1

    print(f"[knuth] {n_relax} relaxations, {len(cost):,} molecules with finite cost", flush=True)
    return cost, best_rxn


def _path_reactions(
    target: str,
    cost: dict[str, float],
    best_rxn: dict[str, str],
    rxn_by_id: dict[str, dict[str, Any]],
    catalog: set[str],
) -> set[str]:
    """Walk back from target to catalog roots; return the set of rxn_ids used.

    Doesn't deduplicate shared sub-paths — that's the over-counting feature.
    But for n_activated we just want the set of distinct reactions.
    """
    used: set[str] = set()
    stack = [target]
    seen: set[str] = set()
    while stack:
        m = stack.pop()
        if m in seen or m in catalog:
            continue
        seen.add(m)
        rxn_id = best_rxn.get(m)
        if rxn_id is None:
            continue
        used.add(rxn_id)
        for c_i, _ in rxn_by_id[rxn_id]["reactants"]:
            if c_i not in seen:
                stack.append(c_i)
    return used


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--budget", type=float, default=10_000.0)
    p.add_argument(
        "--balance-filter",
        default="rdkit_balanced",
        choices=("rdkit_balanced", "balanced"),
    )
    p.add_argument(
        "--out-jsonl",
        type=Path,
        default=Path("data/processed/profit_curve_knuth.jsonl"),
    )
    args = p.parse_args()

    cfg = load_config(args.config, [])
    reactions = read_reactions(processed_path(cfg, "reactions.parquet"))
    mw_path = processed_path(cfg, "molecules_with_mw.parquet")
    bare_path = processed_path(cfg, "molecules.parquet")
    if mw_path.exists():
        molecules = read_molecules(mw_path)
    elif bare_path.exists():
        molecules = read_molecules(bare_path)
    else:
        raise SystemExit(f"missing {mw_path} and {bare_path}")
    print(f"[knuth] loaded {reactions.height:,} reactions, {molecules.height:,} molecules")

    # Mirror MILP preprocessing.
    rxn_meta = _build_rxn_meta(reactions, args.balance_filter)
    print(f"[knuth] {len(rxn_meta):,} reactions after balance filter '{args.balance_filter}'")

    W = _build_mw_lookup(molecules)
    rxn_meta, dropped = _rescale_to_grams(rxn_meta, W)
    print(f"[knuth] {len(rxn_meta):,} reactions after mass-basis rescale ({dropped:,} dropped)")

    C: set[str] = set()
    for r in rxn_meta:
        for c, _ in r["reactants"] + r["products"]:
            C.add(c)
    solver_cfg = SolverConfig(budget=args.budget)
    price_lookup = _build_price_lookup(molecules, C, solver_cfg)

    # Catalog = every chemical, anchored at its price_lookup buy_price.
    # That matches what the LP uses: priced chemicals get their real
    # price_per_gram for both buy and sell; unpriced chemicals get
    # conservative fallbacks (max(known) for buy, min(known) for sell).
    # Knuth then only "discovers profit" on a target if a reaction route
    # strictly beats the direct buy-and-resell cost.
    by_id = {row["mol_id"]: row for row in molecules.iter_rows(named=True)}
    priced: set[str] = set()
    for c in C:
        row = by_id.get(c)
        if row and row.get("price_per_gram") is not None:
            priced.add(c)
    print(
        f"[knuth] {len(priced):,} priced molecules of {len(C):,} total "
        f"(remainder uses LP-style fallback prices)"
    )

    initial_cost: dict[str, float] = {c: price_lookup[c][0] for c in C}

    t0 = time.monotonic()
    cost, best_rxn = knuth_dijkstra_pergram(rxn_meta, initial_cost)
    wall = time.monotonic() - t0
    print(f"[knuth] solved in {wall:.2f}s")

    # Sellable targets: priced chemicals where Knuth's reaction route
    # strictly beats the direct-buy price. We rank by profit-per-dollar
    # = sell/cost - 1, since the budget binds and the natural total
    # profit when allocating the entire budget to one target is
    # B × (sell/cost - 1).
    rxn_by_id = {r["rxn_id"]: r for r in rxn_meta}
    candidates: list[dict[str, Any]] = []
    for c in priced:
        sell_pg = float(by_id[c]["price_per_gram"])
        cost_pg = cost.get(c, INF)
        if cost_pg >= sell_pg or cost_pg == INF or cost_pg <= 0:
            continue
        margin = sell_pg / cost_pg - 1.0
        profit_total = args.budget * margin
        candidates.append(
            {
                "mol_id": c,
                "cost_per_gram": cost_pg,
                "sell_per_gram": sell_pg,
                "margin": margin,
                "profit_total": profit_total,
            }
        )

    candidates.sort(key=lambda d: -d["profit_total"])
    print(f"[knuth] {len(candidates):,} sellable targets with positive margin")

    # Emit JSONL — one record per rank, in the same shape as profit_curve.jsonl.
    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    # Knuth wall-clock is amortized: one Knuth run produces the whole
    # ranking. Per-rank wall = total / N is a fair "average rank cost"
    # for the per-rank plot; the line will show as a flat horizontal at
    # that level, which is exactly the right visualization.
    per_rank_wall = wall / max(1, args.top_n)

    forbidden_so_far: list[str] = []
    with open(args.out_jsonl, "w") as f:
        for rank, cand in enumerate(candidates[: args.top_n], start=1):
            tgt = cand["mol_id"]
            # Terminate path reconstruction at any chemical lacking a
            # best_rxn entry — those were "bought directly" at the
            # initial buy price (whether real or fallback).
            used = _path_reactions(tgt, cost, best_rxn, rxn_by_id, catalog=set())
            grams = args.budget / cand["cost_per_gram"]
            top_revenue = grams * cand["sell_per_gram"]
            rec = {
                "iteration": rank,
                "profit": cand["profit_total"],
                "blocked_this_round": tgt,
                "top_revenue": top_revenue,
                "blocked_at_start_of_round": list(forbidden_so_far),
                "n_sold": 1,
                "n_activated": len(used),
                "wall_seconds": per_rank_wall,
                "cost_per_gram": cand["cost_per_gram"],
                "sell_per_gram": cand["sell_per_gram"],
                "margin": cand["margin"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            f.write(json.dumps(rec) + "\n")
            forbidden_so_far.append(tgt)
            print(
                f"  rank {rank:>2}: {tgt:<14}  "
                f"cost=${cand['cost_per_gram']:>10,.4f}/g  "
                f"sell=${cand['sell_per_gram']:>10,.4f}/g  "
                f"profit=${cand['profit_total']:>14,.0f}  "
                f"path={len(used)} rxns",
                flush=True,
            )

    print(f"\n[knuth] wrote {args.out_jsonl}")
    print(f"[knuth] total wall: {wall:.2f}s  per-rank: {per_rank_wall:.4f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
