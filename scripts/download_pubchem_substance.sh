#!/usr/bin/env bash
# Download PubChem Substance SDF dump (~54 GB) into data/raw/pubchem_substance/.
#
# Required by PubChemCompoundResolver pass 1 — collects the SID -> (vendor DSN,
# vendor SKU, vendor URL) mapping that the JOIN with SID-Map and Compound
# turns into the InChIKey -> ResolverHit index.
#
# One-shot helper. Do NOT invoke from DVC. Re-running is idempotent
# (curl -C - resumes partial files; broken/HTML-error shards are flagged
# at the end so a second invocation can re-pull them).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="$REPO_ROOT/data/raw/pubchem_substance"
mkdir -p "$DST"
cd "$DST"

# Lower parallelism than naive `-P 12` — the FTP server starts serving HTML
# error pages instead of gzip data when hammered, leading to a ~30% corrupt
# rate that has to be cleaned up afterward. -P 4 has been empirically fine.
PARALLEL="${PARALLEL:-4}"

echo "Listing Substance SDF shards..."
curl -sS "https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/" \
  | grep -oE 'Substance_[0-9_]+\.sdf\.gz' | sort -u > shards.txt
SHARD_COUNT=$(wc -l < shards.txt)
echo "Found $SHARD_COUNT shards. Starting download with -P $PARALLEL ..."

cat shards.txt | xargs -n1 -P "$PARALLEL" -I {} \
  curl -sS -C - --retry 5 --retry-delay 5 -O \
  "https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/{}"

echo "Verifying integrity (gzip -t on each file)..."
ls *.sdf.gz | xargs -n1 -P 8 -I {} bash -c 'gzip -t {} 2>/dev/null || echo "BAD: {}"' \
  | tee bad-shards.txt

if [ -s bad-shards.txt ]; then
  echo "Found $(wc -l < bad-shards.txt) corrupt shards. Re-run this script to retry."
  exit 1
fi

echo "Done: $(ls *.sdf.gz | wc -l) shards, $(du -sh . | cut -f1)"
