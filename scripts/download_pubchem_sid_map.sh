#!/usr/bin/env bash
# Download PubChem SID-Map.gz (~3 GB) — the SID -> CID cross-reference table
# required by PubChemCompoundResolver to JOIN Substance (vendor + SKU) and
# Compound (InChIKey) records.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="$REPO_ROOT/data/raw/pubchem_sid_map"
mkdir -p "$DST"
cd "$DST"

curl -sS -C - --retry 5 --retry-delay 5 -O \
  "https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/Extras/SID-Map.gz"

echo "Verifying integrity..."
gzip -t SID-Map.gz

echo "Done: $(du -sh SID-Map.gz | cut -f1)"
