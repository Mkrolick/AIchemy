"""Batch-scrape chemical prices with a shared Playwright browser.

Reuses a single headless Chromium across many SMILES so we don't pay
startup cost per molecule. Writes every hit into the shared PriceCache
with vendor attribution. Safe to interrupt and resume — cache is
persistent SQLite.

Usage:
    uv run python scripts/scrape_prices_playwright.py [--limit N]
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
    parser.add_argument("--limit", type=int, default=1000)
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
    parser.add_argument("--log-every", type=int, default=5)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger("scrape_playwright")

    mols = pl.read_parquet(args.processed_dir / "molecules.parquet")
    rxns_path = args.processed_dir / "reactions.parquet"

    # Build mol_id -> canonical_smiles lookup.
    id_to_smi: dict[str, str] = {
        row["mol_id"]: row["canonical_smiles"]
        for row in mols.iter_rows(named=True)
        if row.get("canonical_smiles")
    }

    # Prioritize SMILES that appear in balanced reactions.
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

    # Pre-filter: drop SMILES with <5 heavy atoms (single atoms, salts) or
    # no C/N/O (inorganic) — Fisher Sci doesn't catalog those.
    def _is_drug_like(smi: str) -> bool:
        if not smi or len(smi) < 5:
            return False
        if not any(c in smi for c in "CNOPScnops"):
            return False
        # Count atom-like characters as rough proxy for size
        heavy = sum(1 for c in smi if c.isalpha() and c not in "lrnftaugsmdiob")
        return heavy >= 3

    smiles_list = [
        s for s in mols.get_column("canonical_smiles").drop_nulls().to_list() if _is_drug_like(s)
    ]
    prioritized = sorted(set(smiles_list), key=lambda s: (s not in priority_smiles, s))
    if args.limit:
        prioritized = prioritized[: args.limit]
    log.info(
        "Processing %d SMILES (%d in priority set, drug-like pre-filter applied).",
        len(prioritized),
        sum(1 for s in prioritized if s in priority_smiles),
    )

    cache = PriceCache(args.cache_path, ttl_days=30)
    scraper = PlaywrightFisherScraper()
    t0 = time.time()
    hits = 0
    misses = 0
    try:
        for i, smi in enumerate(prioritized, 1):
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
                log.warning("scrape failed on %s: %s", smi[:60], exc)
                cache.put(smi, scraper.vendor_name, None)
                misses += 1
                continue

            cache.put(smi, scraper.vendor_name, quote)
            if quote is not None:
                hits += 1
                if hits % 5 == 0:
                    log.info(
                        "HIT %d/%d: %s = $%.4f/g (%s)",
                        hits,
                        i,
                        smi[:40],
                        quote.price_per_gram_usd,
                        quote.source_url[:80],
                    )
            else:
                misses += 1

            if i % args.log_every == 0:
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(prioritized) - i) / rate if rate > 0 else 0
                log.info(
                    "[%d/%d] hits=%d misses=%d  %.2f SMILES/s  ETA=%.1f min",
                    i,
                    len(prioritized),
                    hits,
                    misses,
                    rate,
                    eta / 60,
                )
    finally:
        scraper.close()
        cache.close()

    log.info(
        "DONE. hits=%d misses=%d elapsed=%.1f min",
        hits,
        misses,
        (time.time() - t0) / 60,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
