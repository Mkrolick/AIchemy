# Paper artifacts

Curated data tables and figures referenced in the AIchemy paper.

## Layout

- `data/` — six CSVs (paper-ready). See [data/README.md](data/README.md) for column-level docs.
- `figures/` — PNGs rendered from those CSVs (paper-clean style; no titles, 300 dpi).

## What each figure shows

### Wall-clock vs reaction-subset size (complexity scaling)

| Figure | Subset | Series | Source data |
|---|---|---|---|
| `figures/complexity_scaling_rdkit.png` | 43K rdkit-balanced | MILP / MILP-cap20 / LP | `data/1_complexity_sweep_43k_rdkit.csv` |
| `figures/complexity_scaling.png` | 100K curated | MILP / MILP-cap20 / LP | (raw JSONL: `data/processed/complexity_sweep.jsonl`) |
| `figures/complexity_scaling_no_cap20.png` | 100K curated | MILP / LP only | same |
| `figures/complexity_scaling_364k.png` | 364K full corpus | MILP / MILP-cap20 / LP | (raw JSONL: `data/processed/complexity_sweep_364k.jsonl`) |
| `figures/complexity_scaling_364k_partial.png` | 364K (partial) | MILP / MILP-cap20 / LP | snapshot during in-progress run |

### Profit vs solve rank (forbid-loop)

| Figure | Subset | Series | Source data |
|---|---|---|---|
| `figures/profit_vs_rank_top20_rdkit.png` | 43K rdkit-balanced | MILP / MILP-cap20 / LP | `data/3_profit_vs_rank_43k_rdkit.csv` |
| `figures/profit_vs_rank_top20.png` | 100K curated | MILP / MILP-cap20 / LP | (JSONL trio in `data/processed/`) |
| `figures/profit_vs_rank_top20_364k_partial.png` | 364K (partial) | MILP / MILP-cap20 / LP | snapshot |

### Wall-clock per solve vs solve rank (forbid-loop)

| Figure | Subset | Series | Source data |
|---|---|---|---|
| `figures/solve_time_vs_rank_top20_rdkit.png` | 43K rdkit-balanced | MILP / MILP-cap20 / LP | `data/4_walltime_vs_rank_43k_rdkit.csv` |
| `figures/solve_time_vs_rank_top20.png` | 100K curated | MILP / MILP-cap20 / LP | `data/2_walltime_vs_rank_100k.csv` |
| `figures/solve_time_vs_rank_top20_364k_partial.png` | 364K (partial) | MILP / MILP-cap20 / LP | snapshot |

### Knuth-Dijkstra greedy baseline vs LP relaxation (43K rdkit subset)

| Figure | Series | Source data |
|---|---|---|
| (planned: profit overlay) | LP / Knuth-Dijkstra profit vs rank | `data/5_profit_lp_vs_knuth_43k_rdkit.csv` |
| (planned: time overlay) | LP / Knuth-Dijkstra wall-clock vs rank | `data/6_walltime_lp_vs_knuth_43k_rdkit.csv` |

## Reproducing

All artifacts here were produced by scripts in `scripts/` against the parquets in `data/processed/`. The relevant entry points:

- `scripts/run_complexity_sweep.py` — wall-clock vs reaction-set size sweep.
- `scripts/profit_curve_loop.py` — iterative forbid-loop profit / time vs rank.
- `scripts/regenerate_clean_plots.py` — paper-clean PNGs from the JSONLs.
- `scripts/plot_complexity_scaling.py` — log-log scaling figure.
- `scripts/plot_complexity_seeds.py` — multi-seed scaling with bootstrap CI.
- `scripts/plot_dijkstra_vs_lp.py` — Knuth vs LP overlays.

The CSVs in `data/` were exported from the same JSONLs via `tmp/export_data.py` (one-off). To regenerate, see the source-JSONL list at the bottom of `data/README.md`.
