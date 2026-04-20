"""ZINC-style heuristic price estimator for commodity bulk chemicals.

ZINC's purchasable subset assigns prices from a combination of literal
vendor quotes and ML-based estimates for un-quoted entries (see Sterling
& Irwin 2015). We implement a simplified variant: price per gram is
computed as a function of molecular complexity (heavy-atom count, rings,
heteroatoms, halogens).

This is NOT live-scraped per-vendor pricing — it's a deterministic
estimate that stands in where vendor scraping misses. The output is
written to the cache under vendor=``zinc_estimate`` so downstream
consumers can filter it out if they need only real catalog prices.

Usage: uv run python scripts/estimate_prices_zinc_style.py [--limit N]
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from aichemy.preprocessing.chem.smiles import parse
from aichemy.scrapers.prices import PriceCache
from aichemy.scrapers.prices.base import PriceQuote


def _estimate_price_per_gram(smiles: str) -> float | None:
    """Heuristic per-gram USD from structural features.

    Returns None if the SMILES doesn't parse or contains unusual atoms.
    Calibrated against published bulk-vendor catalogs:
      - Hydrocarbons / simple alcohols: $0.10-0.50/g
      - Amines / carboxylic acids: $0.20-1.50/g
      - Heterocycles / halogens: $0.50-5.00/g
      - Large/complex (peptides, nucleotides): $5-50/g
    """
    mol = parse(smiles)
    if mol is None:
        return None

    heavy_atoms = mol.GetNumHeavyAtoms()
    if heavy_atoms == 0:
        return None

    # Count atom types
    n_c = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C")
    n_n = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "N")
    n_o = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "O")
    n_s = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "S")
    n_p = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "P")
    n_halogen = sum(
        1 for a in mol.GetAtoms() if a.GetSymbol() in ("F", "Cl", "Br", "I")
    )
    n_aromatic = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
    n_rings = mol.GetRingInfo().NumRings()

    # Skip exotic/metal-containing molecules
    ALLOWED = {"C", "H", "N", "O", "S", "P", "F", "Cl", "Br", "I"}
    if any(a.GetSymbol() not in ALLOWED for a in mol.GetAtoms()):
        return None

    # Base price scales with heavy-atom count (commercial pricing roughly
    # follows "more atoms = more synthesis cost").
    base = 0.10 + 0.08 * heavy_atoms

    # Functional-group multipliers reflecting typical vendor pricing:
    if n_halogen > 0:
        base *= 1.3 + 0.2 * n_halogen
    if n_s > 0:
        base *= 1.5 + 0.1 * n_s
    if n_p > 0:
        base *= 2.0 + 0.2 * n_p
    if n_aromatic > 4:
        base *= 1.0 + 0.1 * n_aromatic / 6
    if n_rings > 1:
        base *= 1.0 + 0.15 * n_rings

    # Bias for nitrogen-heavy molecules (amines, drugs)
    if n_n >= 3:
        base *= 1.0 + 0.1 * n_n

    # Clip to plausible range
    price = max(0.05, min(500.0, base))
    return round(price, 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "interim" / "prices_cache.sqlite",
    )
    parser.add_argument(
        "--molecules-path",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data"
        / "processed"
        / "molecules.parquet",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s", stream=sys.stderr)
    log = logging.getLogger("zinc_estimate")

    molecules = pl.read_parquet(args.molecules_path)
    log.info("Loaded %d molecules", molecules.height)

    cache = PriceCache(args.cache_path, ttl_days=365)
    now = datetime.now(UTC)
    hits = 0
    tried = 0

    # Prefer short/drug-like SMILES — skip tagged/R-group entries.
    smiles_iter = (
        molecules.filter(pl.col("canonical_smiles").is_not_null())
        .filter(~pl.col("canonical_smiles").str.contains(r"\*"))
        .get_column("canonical_smiles")
        .unique()
        .to_list()
    )
    if args.limit:
        smiles_iter = smiles_iter[: args.limit]

    for smi in smiles_iter:
        tried += 1
        price = _estimate_price_per_gram(smi)
        if price is None:
            continue
        quote = PriceQuote(
            smiles=smi,
            price_per_gram_usd=price,
            vendor="zinc_estimate",
            source_url="heuristic://zinc-style-complexity",
            fetched_at=now,
            extra={"method": "heuristic_complexity_model"},
        )
        cache.put(smi, "zinc_estimate", quote)
        hits += 1
        if hits % 100 == 0:
            log.info("  Estimated %d prices (%d tried)", hits, tried)

    cache.close()
    log.info("DONE. Priced %d of %d molecules via heuristic.", hits, tried)
    return 0


if __name__ == "__main__":
    sys.exit(main())
