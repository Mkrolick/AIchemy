"""Smoke test: do each configured scraper return a plausible price for two
well-known molecules (ethanol, vanillin)?

Prints a per-vendor table with price or skip-reason. Exits 0 iff at least
2 of 3 vendors return non-None, distinct prices for both molecules.
"""

from __future__ import annotations

import logging
import sys

from aichemy.scrapers.prices.base import PriceScraperBase
from aichemy.scrapers.prices.pipeline import DEFAULT_VENDOR_ORDER
from aichemy.scrapers.prices.registry import get_scraper

TEST_CASES: list[tuple[str, str]] = [
    ("ethanol", "CCO"),
    ("vanillin", "COc1cc(C=O)ccc1O"),
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s  %(message)s")

    results: dict[str, dict[str, float | None]] = {name: {} for name, _ in TEST_CASES}
    skipped: dict[str, str] = {}

    for vendor in DEFAULT_VENDOR_ORDER:
        scraper: PriceScraperBase | None = get_scraper(
            vendor,
            user_agent="AIchemy-smoke/0.1 (malcolm.krolick@gmail.com)",
            rate_limit_seconds=1.0,
            respect_robots_txt=False,
        )
        if scraper is None:
            skipped[vendor] = "not registered"
            continue
        try:
            for name, smiles in TEST_CASES:
                quote = scraper.fetch(smiles)
                results[name][vendor] = quote.price_per_gram_usd if quote is not None else None
        except Exception as exc:
            skipped[vendor] = f"exception: {type(exc).__name__}: {exc}"
        finally:
            scraper.close()

    print("\n=== Scraper smoke-test ===")
    header = f"{'molecule':<12} | " + " | ".join(f"{v:<18}" for v in DEFAULT_VENDOR_ORDER)
    print(header)
    print("-" * len(header))
    for name, _ in TEST_CASES:
        row_cells: list[str] = []
        for v in DEFAULT_VENDOR_ORDER:
            if v in skipped:
                cell = "SKIP"
            elif v in results[name] and results[name][v] is not None:
                cell = f"${results[name][v]:.3f}/g"
            else:
                cell = "None"
            row_cells.append(f"{cell:<18}")
        print(f"{name:<12} | " + " | ".join(row_cells))

    if skipped:
        print("\nSkipped vendors:")
        for v, reason in skipped.items():
            print(f"  {v}: {reason}")

    # Success criterion: at least 2 vendors return distinct, non-None prices
    # for BOTH test molecules.
    vendors_with_both = [
        v
        for v in DEFAULT_VENDOR_ORDER
        if all(results[name].get(v) is not None for name, _ in TEST_CASES)
    ]
    print(f"\nVendors with prices for all test molecules: {vendors_with_both}")

    if len(vendors_with_both) < 2:
        print("FAIL: fewer than 2 vendors returned prices for both molecules.")
        return 1

    # Distinctness: different vendors shouldn't all return identical price
    # (that would suggest a bug, not real scraping).
    for name, _ in TEST_CASES:
        vals = {results[name][v] for v in vendors_with_both}
        if len(vals) < 2:
            print(f"FAIL: all vendors returned identical price for {name}: {vals}")
            return 1

    print("PASS: ≥2 vendors returned distinct real prices for both molecules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
