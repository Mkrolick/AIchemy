#!/usr/bin/env bash
# Build a small reproducible subset of MetaNetX + USPTO raw data into
# data_subset/raw/ for end-to-end pipeline validation runs.
#
# Use with: --override configs/subset.yaml on any aichemy command.
#
# Sizes (configurable via env vars):
#   MNX_REACTIONS=200    (≈0.27% of full ~75k)
#   MNX_MOLECULES=5000   (≈0.39% of full 1.29M; biased toward earlier IDs)
#   MNX_XREFS=5000       (chem + reac xref, no semantic guarantee but ingest-safe)
#   USPTO_REACTIONS=200  (≈0.011% of full 1.8M; balance_uspto sees these)
#
# Idempotent: rebuilds data_subset/raw/ from scratch each run.

set -euo pipefail

MNX_REACTIONS="${MNX_REACTIONS:-200}"
MNX_MOLECULES="${MNX_MOLECULES:-5000}"
MNX_XREFS="${MNX_XREFS:-5000}"
USPTO_REACTIONS="${USPTO_REACTIONS:-200}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/data/raw"
DST="$REPO_ROOT/data_subset/raw"

if [[ ! -d "$SRC/metanetx" ]]; then
  echo "ERROR: $SRC/metanetx not found. Run 'aichemy fetch-raw' first." >&2
  exit 1
fi
if [[ ! -f "$SRC/uspto/1976_Sep2016_USPTOgrants_smiles.rsmi" ]]; then
  echo "ERROR: USPTO .rsmi not found. Run 'aichemy fetch-raw' first." >&2
  exit 1
fi

rm -rf "$DST"
mkdir -p "$DST/metanetx" "$DST/uspto"

# MetaNetX TSVs: 352 comment-header lines + N data rows.
sample_mnx() {
  local file="$1"
  local n="$2"
  local total=$((352 + n))
  head -n "$total" "$SRC/metanetx/$file" > "$DST/metanetx/$file"
  echo "  $file: 352 header + $n data rows"
}

echo "Sampling MetaNetX:"
sample_mnx chem_prop.tsv "$MNX_MOLECULES"
sample_mnx reac_prop.tsv "$MNX_REACTIONS"
sample_mnx chem_xref.tsv "$MNX_XREFS"
sample_mnx reac_xref.tsv "$MNX_XREFS"

echo "Sampling USPTO:"
# USPTO .rsmi: 1 header line + N data rows.
head -n $((1 + USPTO_REACTIONS)) "$SRC/uspto/1976_Sep2016_USPTOgrants_smiles.rsmi" \
  > "$DST/uspto/1976_Sep2016_USPTOgrants_smiles.rsmi"
echo "  1976_Sep2016_USPTOgrants_smiles.rsmi: 1 header + $USPTO_REACTIONS data rows"

echo ""
echo "Subset built at: $DST"
echo "Use with: aichemy <stage> --config configs/default.yaml --override configs/subset.yaml"
