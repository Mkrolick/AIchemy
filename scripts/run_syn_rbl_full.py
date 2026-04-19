"""Run SYN-RBL on the full USPTO corpus with checkpointing + resume.

Processes USPTO reactions in chunks, writing each chunk's output to a
separate parquet shard. Safe to interrupt + restart — already-complete
shards are skipped on resume. When the last shard completes, concats
them into the canonical `data/interim/balanced/reactions.parquet`.

Usage:
    uv run python scripts/run_syn_rbl_full.py [--chunk-size 5000] [--workers -1]

All USPTO reactions from `data/interim/uspto/reactions_raw.parquet` are
processed. MetaNetX reactions are not touched (they are passed through
as-is in the final output).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import polars as pl

from aichemy.preprocessing.balance.syn_rbl import balance_reactions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=-1, help="n_jobs for synrbl")
    parser.add_argument("--uspto-limit", type=int, default=None, help="Process only first N")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", stream=sys.stderr)
    log = logging.getLogger("syn_rbl_full")

    root = Path(__file__).resolve().parents[1]
    uspto_path = root / "data" / "interim" / "uspto" / "reactions_raw.parquet"
    mnx_path = root / "data" / "interim" / "metanetx" / "reactions_raw.parquet"
    shard_dir = root / "data" / "interim" / "balanced" / "shards"
    final_out = root / "data" / "interim" / "balanced" / "reactions.parquet"

    if not uspto_path.exists():
        log.error("USPTO interim not found at %s — run `aichemy ingest uspto` first.", uspto_path)
        return 1

    uspto = pl.read_parquet(uspto_path)
    if args.uspto_limit is not None:
        uspto = uspto.head(args.uspto_limit)
    log.info("USPTO rows to process: %d", uspto.height)

    shard_dir.mkdir(parents=True, exist_ok=True)

    total = uspto.height
    n_shards = (total + args.chunk_size - 1) // args.chunk_size
    log.info("Splitting into %d shards of up to %d rows each.", n_shards, args.chunk_size)

    total_recovered = 0
    overall_start = time.time()

    for shard_idx in range(n_shards):
        shard_path = shard_dir / f"shard_{shard_idx:05d}.parquet"
        if shard_path.exists():
            df = pl.read_parquet(shard_path)
            recovered = df.filter(pl.col("balanced")).height
            total_recovered += recovered
            log.info(
                "[%d/%d] %s already exists (%d rows, %d balanced)",
                shard_idx + 1,
                n_shards,
                shard_path.name,
                df.height,
                recovered,
            )
            continue

        chunk = uspto.slice(shard_idx * args.chunk_size, args.chunk_size)
        rxn_smiles_list = chunk["reaction_smiles"].to_list()

        t0 = time.time()
        balanced_smiles = balance_reactions(rxn_smiles_list, n_jobs=args.workers)
        elapsed = time.time() - t0

        # Attach results back to the chunk.
        balanced_bool = [b is not None for b in balanced_smiles]
        new_rxn_smiles = [
            balanced if balanced is not None else orig
            for orig, balanced in zip(rxn_smiles_list, balanced_smiles, strict=True)
        ]
        out_df = chunk.with_columns(
            pl.Series("reaction_smiles", new_rxn_smiles),
            pl.Series("balanced", balanced_bool, dtype=pl.Boolean),
        )
        out_df.write_parquet(shard_path)

        shard_recovered = sum(balanced_bool)
        total_recovered += shard_recovered
        rate = chunk.height / elapsed if elapsed > 0 else 0
        cumulative_elapsed = time.time() - overall_start
        progress_frac = (shard_idx + 1) / n_shards
        eta_sec = (
            cumulative_elapsed * (1 - progress_frac) / progress_frac if progress_frac > 0 else 0
        )
        log.info(
            "[%d/%d] %s: %d rows in %.1fs (%.1f rxn/s), %d recovered. Total: %d. ETA: %.1f min",
            shard_idx + 1,
            n_shards,
            shard_path.name,
            chunk.height,
            elapsed,
            rate,
            shard_recovered,
            total_recovered,
            eta_sec / 60,
        )

    # Concat all shards into the canonical output (+ pass through MetaNetX if present).
    log.info("Concatenating %d shards into %s", n_shards, final_out)
    shard_frames: list[pl.DataFrame] = []
    for shard_idx in range(n_shards):
        shard_path = shard_dir / f"shard_{shard_idx:05d}.parquet"
        if shard_path.exists():
            shard_frames.append(pl.read_parquet(shard_path))
    combined = pl.concat(shard_frames, how="diagonal_relaxed") if shard_frames else uspto.head(0)

    if mnx_path.exists():
        mnx = pl.read_parquet(mnx_path)
        combined = pl.concat([combined, mnx], how="diagonal_relaxed")
        log.info("Merged MetaNetX pass-through: %d rows", mnx.height)

    final_out.parent.mkdir(parents=True, exist_ok=True)
    combined.write_parquet(final_out)

    total_elapsed = time.time() - overall_start
    log.info(
        "DONE. Wrote %d rows to %s in %.1f min.", combined.height, final_out, total_elapsed / 60
    )
    log.info(
        "USPTO balance recovery: %d / %d (%.1f%%)",
        total_recovered,
        total,
        100 * total_recovered / total if total > 0 else 0,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
