# Lambda snapshots

Compressed tarballs of intermediate / final pipeline state captured from the Lambda Cloud machine that ran the full DVC pipeline (priced molecules, thermo-augmented reactions, and the master handoff).

**These files are too large to track in-repo and are published as GitHub Release assets.** Download them from:

> **https://github.com/Mkrolick/AIchemy/releases/tag/v0.1-paper-snapshots**

Or via the `gh` CLI:

```bash
gh release download v0.1-paper-snapshots --dir paper/snapshots/
```

## Files

| Asset | Size | Contents |
|---|---:|---|
| `dominance_test_results.tar.gz` | 8 KB | Output of the 30-partition dominance hypothesis test — per-partition profit + binomial-test summary CSV. |
| `lambda-thermo-results_2026-04-29_035426.tar.zst` | 77 MB | Output of `augment_metanetx_yields_thermo`: post-export ΔG-derived yields for MetaNetX rows, plus the regenerated `data/processed/reactions_thermo_yields.parquet`. |
| `lambda-pricing-results_2026-04-28_235750.tar.zst` | 379 MB | Full pricing run on Lambda — Fluorochem-only DSN (PubChem source 29665), 73,109 priced molecules of 1.3M; includes `aichemy_pricing_index.parquet`, `aichemy_pricing_cache.sqlite`, the priced `molecules_priced.parquet`, and the resulting `data/processed/molecules_with_mw.parquet`. |
| `lambda-handoff.tar.zst` | 286 MB | Composite snapshot at the end of the Lambda run cycle — config + interim parquets + processed parquets + DVC lockfile state, sufficient to skip rerunning all 17 upstream stages and resume at `augment_prices`/`export`. Use with `scripts/run_pricing_on_tarball_data.sh`. |

## Provenance

Captured from `ubuntu@192.222.59.156:/home/ubuntu/` between 2026-04-28 and 2026-04-30 during the Fluorochem-purity integration cycle.

## Decompression

The `.tar.zst` files require zstandard:

```bash
brew install zstd                                  # macOS
sudo apt install zstd                              # Debian/Ubuntu
tar -I zstd -xf lambda-handoff.tar.zst             # extracts in place
```

The `.tar.gz` is plain gzip:

```bash
tar xzf dominance_test_results.tar.gz
```

## Note on Git LFS

A previous attempt tracked these tarballs via Git LFS (`*.tar.zst` and `*.tar.gz` patterns in `.gitattributes`). LFS push failed because LFS is not enabled for this repository on GitHub. The `.gitattributes` LFS rules are retained so that future tarball commits will route through LFS if it gets enabled later; for now, please use the Release link above.
