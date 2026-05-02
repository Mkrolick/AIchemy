#!/usr/bin/env bash
# Run augment_prices + export directly, bypassing DVC stage validation.
#
# Why: when interim parquets come from a tarball/rsync (not a fresh dvc repro),
# DVC's lockfile hashes won't match the on-disk files, and `dvc repro export`
# would re-run 17 upstream stages just to recompute matching hashes. The CLI
# commands themselves don't care about DVC — they read the input parquets
# directly and write outputs.
#
# Prereqs (script will check):
#   - .env in repo root with USPTO_ODP_API_KEY, ANTHROPIC_API_KEY, BROWSERBASE_API_KEY
#   - data/interim/augmented/reactions_full.parquet      (from tarball)
#   - data/interim/deduped/molecules.parquet             (from tarball)
#   - data/interim/augmented/reactions_licensed.parquet  (from tarball; needed by export)
#   - data/raw/pubchem_{compound,substance,sid_map}/     (from download scripts)
#   - uv on PATH

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a; source .env; set +a
fi
export PATH="$HOME/.local/bin:$PATH"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }

# --- preflight ----------------------------------------------------------------
missing=0
for f in \
  data/interim/augmented/reactions_full.parquet \
  data/interim/deduped/molecules.parquet \
  data/interim/augmented/reactions_licensed.parquet
do
  if [ ! -f "$f" ]; then
    red "MISSING input parquet: $f"
    missing=1
  fi
done

for d in \
  data/raw/pubchem_compound \
  data/raw/pubchem_substance \
  data/raw/pubchem_sid_map
do
  if [ ! -d "$d" ] || [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
    red "MISSING or empty raw dir: $d"
    missing=1
  fi
done

for k in USPTO_ODP_API_KEY ANTHROPIC_API_KEY BROWSERBASE_API_KEY; do
  if [ -z "${!k:-}" ]; then
    red "MISSING env var: $k (set in .env)"
    missing=1
  fi
done

if [ $missing -ne 0 ]; then
  red "preflight failed; fix the above and re-run"
  exit 1
fi
green "preflight ok"

# --- step 1: pricing index ----------------------------------------------------
INDEX=data/interim/aichemy_pricing_index.parquet
if [ -f "$INDEX" ]; then
  blue "[1/3] pricing index already exists at $INDEX — skipping rebuild"
  blue "       (delete the file if you want to rebuild)"
else
  blue "[1/3] building pricing index (~5 min on 64-core)"
  uv run python scripts/build_pricing_index_fast.py --allowed-dsns 29665
fi

# --- step 2: augment prices ---------------------------------------------------
blue "[2/3] running augment_prices"
uv run aichemy augment prices --config configs/default.yaml

# --- step 3: export -----------------------------------------------------------
blue "[3/3] running export"
uv run aichemy export --config configs/default.yaml

green "DONE"
echo
echo "outputs:"
ls -lah data/processed/ 2>/dev/null || true
echo
echo "molecules priced:"
uv run python -c "
import polars as pl
df = pl.read_parquet('data/interim/augmented/molecules_priced.parquet')
priced = df.filter(pl.col('price_per_gram').is_not_null())
print(f'  {priced.height:,} / {df.height:,} ({100*priced.height/max(df.height,1):.1f}%) priced')
" 2>/dev/null || true
