#!/usr/bin/env bash
# Download PubChem Compound SDF dump (~30 GB) into data/raw/pubchem_compound/.
#
# Required by the aichemy_pricing backend's PubChemCompoundResolver — the
# Compound shards carry PUBCHEM_IUPAC_INCHIKEY, which the Substance shards
# do NOT carry on vendor-deposited records. See
# docs/superpowers/plans/2026-04-26-pricing-scalability.md for the JOIN design.
#
# One-shot helper. Do NOT invoke from DVC. Re-running is idempotent (curl -O
# skips files that already exist with -C - resume).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="$REPO_ROOT/data/raw/pubchem_compound"
mkdir -p "$DST"
cd "$DST"

# Lower parallelism than the Substance download to avoid the partial-content
# / HTML-error-page issue we hit at -P 12.
PARALLEL="${PARALLEL:-4}"

echo "Listing Compound SDF shards..."
curl -sS "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/CURRENT-Full/SDF/" \
  | grep -oE 'Compound_[0-9_]+\.sdf\.gz' | sort -u > shards.txt
SHARD_COUNT=$(wc -l < shards.txt)
echo "Found $SHARD_COUNT shards. Starting download with -P $PARALLEL ..."

cat shards.txt | xargs -n1 -P "$PARALLEL" -I {} \
  curl -sS -C - --retry 5 --retry-delay 5 -O \
  "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/CURRENT-Full/SDF/{}"

echo "Verifying integrity (gzip -t on each file)..."
ls *.sdf.gz | xargs -n1 -P 8 -I {} bash -c 'gzip -t {} 2>/dev/null || echo "BAD: {}"' \
  | tee bad-shards.txt

if [ -s bad-shards.txt ]; then
  echo "Found $(wc -l < bad-shards.txt) corrupt shards. Re-run this script to retry."
  exit 1
fi

echo "Done: $(ls *.sdf.gz | wc -l) shards, $(du -sh . | cut -f1)"
