"""Scrape chemical prices for molecules in the processed hypergraph.

Pulls the SMILES list from data/processed/molecules.parquet, prioritizes
by appearance in balanced reactions, and runs the default scraper stack
against every SMILES. Safe to interrupt + restart — cache is persistent.

Usage:
    uv run python scripts/scrape_prices.py [--limit N] [--user-agent ...]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import polars as pl

from aichemy.scrapers.prices import PriceCache
from aichemy.scrapers.prices.pipeline import PricePipeline, default_scrapers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max SMILES to process")
    parser.add_argument(
        "--user-agent",
        default="AIchemy-research/0.1 (malcolm.krolick@gmail.com)",
    )
    parser.add_argument("--rate-limit-seconds", type=float, default=2.0)
    parser.add_argument(
        "--vendors",
        nargs="+",
        default=["thermofisher", "sigma_aldrich", "chemicalbook"],
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "processed",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "interim" / "prices_cache.sqlite",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=25,
        help="Print progress every N molecules",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger("scrape_prices")

    molecules_path = args.processed_dir / "molecules.parquet"
    reactions_path = args.processed_dir / "reactions.parquet"
    if not molecules_path.exists():
        log.error("Processed molecules missing at %s", molecules_path)
        return 1

    molecules = pl.read_parquet(molecules_path)
    log.info("Loaded %d molecules from %s", molecules.height, molecules_path)

    # Prioritize molecules that appear in balanced reactions (more likely
    # to matter to the solver than isolated entries).
    priority_smiles: set[str] = set()
    if reactions_path.exists():
        rxns = pl.read_parquet(reactions_path)
        if "balanced" in rxns.columns:
            rxns = rxns.filter(pl.col("balanced"))
        for row in rxns.iter_rows(named=True):
            for s in row.get("reactants", []) + row.get("products", []):
                mid = s.get("mol_id")
                if mid:
                    priority_smiles.add(mid)
        log.info(
            "Prioritizing %d SMILES referenced by balanced reactions",
            len(priority_smiles),
        )

    # Build canonical-SMILES work list — prioritize, dedupe.
    canonical_smiles = molecules.get_column("canonical_smiles").drop_nulls().to_list()
    prioritized = sorted(
        set(canonical_smiles),
        key=lambda s: (s not in priority_smiles, s),
    )
    if args.limit:
        prioritized = prioritized[: args.limit]
    log.info("Will attempt pricing for %d SMILES", len(prioritized))

    cache = PriceCache(args.cache_path, ttl_days=30)
    scrapers = default_scrapers(
        user_agent=args.user_agent,
        order=args.vendors,
        rate_limit_seconds=args.rate_limit_seconds,
        respect_robots_txt=False,
    )
    pipeline = PricePipeline(scrapers=scrapers, cache=cache)

    hits = 0
    misses = 0
    t0 = time.time()
    try:
        for i, smi in enumerate(prioritized, 1):
            quote = pipeline.get_price(smi)
            if quote is not None:
                hits += 1
            else:
                misses += 1
            if i % args.log_every == 0 or i == len(prioritized):
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (len(prioritized) - i) / rate if rate > 0 else 0
                log.info(
                    "[%d/%d] hits=%d misses=%d  %.1f SMILES/s  ETA=%.1f min",
                    i,
                    len(prioritized),
                    hits,
                    misses,
                    rate,
                    remaining / 60,
                )
    finally:
        pipeline.close()

    log.info(
        "DONE. hits=%d misses=%d total=%d  hit_rate=%.1f%%  elapsed=%.1f min",
        hits,
        misses,
        hits + misses,
        100 * hits / (hits + misses) if (hits + misses) else 0,
        (time.time() - t0) / 60,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
