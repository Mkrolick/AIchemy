"""One-time download of the ChEBI OBO ontology (~200 MB).

Used by the class-metabolite resolver (Layer B) to walk ``is_a`` from
class-level metabolites down to concrete leaves with real SMILES.

Not part of the DVC pipeline — invoke manually::

    uv run python scripts/fetch_chebi.py

Skips the download if ``data/raw/chebi/chebi.obo`` already exists. Override
the destination with the ``--out`` flag.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

CHEBI_OBO_URL = "https://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi.obo.gz"
DEFAULT_OUT = Path("data/raw/chebi/chebi.obo")


def fetch(out_path: Path, *, force: bool = False) -> Path:
    """Download chebi.obo (gzipped on the wire, decompressed on disk)."""
    if out_path.exists() and not force:
        print(f"[fetch_chebi] {out_path} already exists; skipping (use --force to redownload).")
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[fetch_chebi] downloading {CHEBI_OBO_URL}")
    with httpx.stream("GET", CHEBI_OBO_URL, follow_redirects=True, timeout=120.0) as r:
        r.raise_for_status()
        # Write the gzipped body, then decompress (httpx handles gzip transparently
        # on streamed bytes only if Accept-Encoding is set — easier to gunzip here).
        gz_path = out_path.with_suffix(out_path.suffix + ".gz")
        with gz_path.open("wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)

    import gzip

    with gzip.open(gz_path, "rb") as src, out_path.open("wb") as dst:
        while True:
            buf = src.read(1 << 20)
            if not buf:
                break
            dst.write(buf)
    gz_path.unlink()
    print(f"[fetch_chebi] wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output OBO path")
    ap.add_argument("--force", action="store_true", help="re-download even if file exists")
    args = ap.parse_args()
    fetch(args.out, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
