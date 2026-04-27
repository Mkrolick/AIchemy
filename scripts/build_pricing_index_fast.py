#!/usr/bin/env python3
"""Fast PubChem pricing-index builder (one-off helper).

Builds `data/interim/aichemy_pricing_index.parquet` directly via
`SID-Map + parallel Compound scan`, skipping the 90-min Substance pass that
the production `PubChemCompoundResolver.from_files` walks. Output schema is
identical to the production builder, so `make_lookup` picks it up via
`PubChemCompoundResolver.from_cache` with no code changes.

Wall-clock on Lambda 64-core: ~5-10 min vs ~3 hr single-threaded. The wins
come from (1) using SID-Map's 4-column format to get (CID, vendor, SKU)
without scanning Substance SDFs, and (2) ProcessPoolExecutor across cores
for the Compound InChIKey lookup.

Caveat: canonical_url is None for every row — SID-Map carries the
source_reg_id but not the substance/datasource URL. The full 3-pass build
still populates it. For validation runs the URL field is unused.
"""

from __future__ import annotations

import argparse
import gzip
import logging
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import polars as pl

# DSN -> display-name (column 2 of SID-Map). Verified empirically on
# 2026-04-27 by sampling SID-Map.gz; matches column 2 of PubChem
# Source-Names. Covers the curated allowlist in configs/default.yaml.
DSN_TO_DISPLAY = {
    "822": "Enamine",
    "959": "MedChemexpress MCE",
    "10600": "Tocris Bioscience",
    "25659": "Santa Cruz Biotechnology, Inc.",
    "29665": "Fluorochem",
    "843": "Cayman Chemical",
    "Sigma-Aldrich": "Sigma-Aldrich",
}


_NEEDED_CIDS: set[int] | None = None


def _worker_init(needed_cids: set[int], repo_src: str) -> None:
    global _NEEDED_CIDS
    _NEEDED_CIDS = needed_cids
    if repo_src not in sys.path:
        sys.path.insert(0, repo_src)


def _scan_compound_shard(path: Path) -> dict[int, str]:
    assert _NEEDED_CIDS is not None
    from aichemy_pricing.resolvers._sdf import iter_sdf_records

    out: dict[int, str] = {}
    for rec in iter_sdf_records(path):
        cid_v = rec.get("PUBCHEM_COMPOUND_CID")
        if not cid_v:
            continue
        try:
            cid = int(cid_v[0])
        except (ValueError, IndexError):
            continue
        if cid not in _NEEDED_CIDS:
            continue
        ik_v = rec.get("PUBCHEM_IUPAC_INCHIKEY")
        if not ik_v:
            continue
        ik = ik_v[0]
        if len(ik) != 27:
            continue
        out[cid] = ik
    return out


def parse_sid_map(
    sid_map_path: Path, allowed_display_names: set[str]
) -> dict[int, list[tuple[str, str]]]:
    cid_to_vendors: dict[int, list[tuple[str, str]]] = defaultdict(list)
    n_lines = 0
    n_kept = 0
    t0 = time.time()
    log = logging.getLogger("sidmap")
    with gzip.open(sid_map_path, "rt", errors="replace") as f:
        for line in f:
            n_lines += 1
            if n_lines % 50_000_000 == 0:
                log.info(
                    "%d lines / %d matches / %.0fs",
                    n_lines,
                    n_kept,
                    time.time() - t0,
                )
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            display_name = parts[1]
            if display_name not in allowed_display_names:
                continue
            cid_str = parts[3].strip()
            if not cid_str:
                continue
            try:
                cid = int(cid_str)
            except ValueError:
                continue
            cid_to_vendors[cid].append((display_name, parts[2]))
            n_kept += 1
    log.info(
        "done: %d lines / %d matches / %d unique CIDs / %.0fs",
        n_lines,
        n_kept,
        len(cid_to_vendors),
        time.time() - t0,
    )
    return cid_to_vendors


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--workers", type=int, default=os.cpu_count() or 8)
    p.add_argument(
        "--allowed-dsns",
        default=",".join(DSN_TO_DISPLAY.keys()),
        help="Comma-separated DSN values matching configs/default.yaml allowed_sources",
    )
    p.add_argument(
        "--limit-shards",
        type=int,
        default=0,
        help="Process only the first N Compound shards (0 = all). Smoke-test aid.",
    )
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("build_fast")

    repo_root = args.repo_root.resolve()
    sid_map_path = repo_root / "data/raw/pubchem_sid_map/SID-Map.gz"
    compound_dir = repo_root / "data/raw/pubchem_compound"
    out_path = repo_root / "data/interim/aichemy_pricing_index.parquet"

    if not sid_map_path.exists():
        raise SystemExit(f"missing: {sid_map_path}")
    if not compound_dir.is_dir():
        raise SystemExit(f"missing: {compound_dir}")

    allowed_dsns = {s.strip() for s in args.allowed_dsns.split(",") if s.strip()}
    unknown = allowed_dsns - DSN_TO_DISPLAY.keys()
    if unknown:
        raise SystemExit(
            f"DSN(s) without display-name mapping: {sorted(unknown)}. "
            "Update DSN_TO_DISPLAY in this script (verify against PubChem Source-Names)."
        )
    display_to_dsn = {DSN_TO_DISPLAY[d]: d for d in allowed_dsns}
    allowed_display_names = set(display_to_dsn.keys())
    log.info("DSNs: %s", sorted(allowed_dsns))
    log.info("display names: %s", sorted(allowed_display_names))

    log.info("== pass 1: SID-Map walk ==")
    cid_to_vendors = parse_sid_map(sid_map_path, allowed_display_names)
    if not cid_to_vendors:
        raise SystemExit("0 CID matches; check DSN -> display-name mapping vs SID-Map column 2.")

    needed_cids = set(cid_to_vendors.keys())
    log.info(
        "pass 1 result: %d unique CIDs across %d vendor matches",
        len(needed_cids),
        sum(len(v) for v in cid_to_vendors.values()),
    )

    shard_paths = sorted(list(compound_dir.glob("*.sdf")) + list(compound_dir.glob("*.sdf.gz")))
    if args.limit_shards:
        shard_paths = shard_paths[: args.limit_shards]
        log.info("--limit-shards=%d -> %d shards", args.limit_shards, len(shard_paths))

    log.info(
        "== pass 2: Compound scan, %d shards x %d workers ==",
        len(shard_paths),
        args.workers,
    )

    cid_to_inchikey: dict[int, str] = {}
    repo_src = str(repo_root / "src")
    t0 = time.time()
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_worker_init,
        initargs=(needed_cids, repo_src),
    ) as ex:
        futures = {ex.submit(_scan_compound_shard, p): p for p in shard_paths}
        for done, fut in enumerate(as_completed(futures), start=1):
            chunk = fut.result()
            cid_to_inchikey.update(chunk)
            if done % 25 == 0 or done == len(shard_paths):
                log.info(
                    "compound: %d/%d shards / %d total InChIKeys / %.0fs",
                    done,
                    len(shard_paths),
                    len(cid_to_inchikey),
                    time.time() - t0,
                )

    log.info("== pass 3: JOIN + persist ==")
    rows: list[dict[str, str | None]] = []
    for cid, vendors in cid_to_vendors.items():
        ik = cid_to_inchikey.get(cid)
        if ik is None:
            continue
        for display_name, sku in vendors:
            rows.append(
                {
                    "inchikey": ik,
                    "vendor": display_to_dsn[display_name],
                    "sku": sku,
                    "canonical_url": None,
                }
            )

    df = pl.DataFrame(
        rows,
        schema={
            "inchikey": pl.Utf8,
            "vendor": pl.Utf8,
            "sku": pl.Utf8,
            "canonical_url": pl.Utf8,
        },
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    log.info(
        "wrote %d hits / %d unique InChIKeys to %s",
        df.height,
        df.select("inchikey").n_unique(),
        out_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
