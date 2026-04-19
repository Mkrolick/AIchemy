"""Scraper runner for a specific slice — enables parallel processes on disjoint work.

Each parallel worker runs on its own slice of the priority SMILES list, using a
separate Playwright browser. Cache is shared (SQLite handles concurrent writes).

Usage:
    uv run python scripts/scrape_prices_playwright_slice.py --slice 0 --n-slices 3 --limit 500
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import polars as pl

from aichemy.scrapers.prices.cache import PriceCache, _Miss
from aichemy.scrapers.prices.playwright_fishersci import PlaywrightFisherScraper


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", type=int, required=True, help="Worker index (0-based)")
    parser.add_argument("--n-slices", type=int, required=True)
    parser.add_argument("--limit", type=int, default=500, help="Slice total items from prioritized list")
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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s  slice{args.slice}  %(levelname)s  %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger("scrape_slice")

    mols = pl.read_parquet(args.processed_dir / "molecules.parquet")
    rxns_path = args.processed_dir / "reactions.parquet"
    id_to_smi = {
        row["mol_id"]: row["canonical_smiles"]
        for row in mols.iter_rows(named=True)
        if row.get("canonical_smiles")
    }
    priority_smiles: set[str] = set()
    if rxns_path.exists():
        rxns = pl.read_parquet(rxns_path)
        if "balanced" in rxns.columns:
            rxns = rxns.filter(pl.col("balanced"))
        for row in rxns.iter_rows(named=True):
            for s in row.get("reactants", []) + row.get("products", []):
                mid = s.get("mol_id")
                if mid and mid in id_to_smi:
                    priority_smiles.add(id_to_smi[mid])

    def _is_drug_like(smi: str) -> bool:
        if not smi or len(smi) < 5:
            return False
        if not any(c in smi for c in "CNOPScnops"):
            return False
        heavy = sum(1 for c in smi if c.isalpha() and c not in "lrnftaugsmdiob")
        return heavy >= 3

    smi_list = [s for s in mols.get_column("canonical_smiles").drop_nulls().to_list() if _is_drug_like(s)]
    prioritized = sorted(set(smi_list), key=lambda s: (s not in priority_smiles, s))[: args.limit]

    # Deterministic slicing
    my_slice = [s for i, s in enumerate(prioritized) if i % args.n_slices == args.slice]
    log.info("slice %d/%d processing %d SMILES", args.slice, args.n_slices, len(my_slice))

    cache = PriceCache(args.cache_path, ttl_days=30)
    scraper = PlaywrightFisherScraper()
    t0 = time.time()
    hits = 0
    misses = 0
    try:
        for i, smi in enumerate(my_slice, 1):
            cached = cache.get(smi, scraper.vendor_name)
            if cached is not None and not isinstance(cached, _Miss):
                hits += 1
                continue
            if isinstance(cached, _Miss):
                misses += 1
                continue
            try:
                quote = scraper.scrape(smi)
            except Exception as exc:
                log.warning("scrape error on %s: %s", smi[:50], exc)
                cache.put(smi, scraper.vendor_name, None)
                misses += 1
                continue
            cache.put(smi, scraper.vendor_name, quote)
            if quote is not None:
                hits += 1
                log.info("HIT %d: %s = $%.4f/g", hits, smi[:40], quote.price_per_gram_usd)
            else:
                misses += 1
            if i % 10 == 0:
                log.info(
                    "[%d/%d] hits=%d misses=%d  ETA=%.1f min",
                    i,
                    len(my_slice),
                    hits,
                    misses,
                    (len(my_slice) - i) / (i / (time.time() - t0)) / 60 if i > 0 else 0,
                )
    finally:
        scraper.close()
        cache.close()
    log.info("DONE hits=%d misses=%d %.1f min", hits, misses, (time.time() - t0) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
