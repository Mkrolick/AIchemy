# AIchemy paper data — exported 2026-05-01 20:24

## Conventions

- All timestamps from the ISO8601 fields in the source JSONLs are dropped here; rerun the source script if you need them.
- "rdkit subset" = 40,874 reactions with `rdkit_balanced=True` (atom-balanced, RDKit-verified).
- "100K subset" = 100,000 reactions from the IDF-anchored `select_reactions` curated subset (filter `balanced=True`).
- Solver: CBC (system binary) via PuLP. LP mode drops binary y_r and w_c; MILP-cap20 imposes sum(y_r) <= 20.
- Solve rank n in the profit-curve files = nth iteration of the forbid-loop (each iter blocks the prior iter's top-revenue product).
- Per-solve wall-clock is the elapsed seconds from `subprocess.run` start to end (full solver invocation incl. CBC startup).
- Profit is the MILP/LP objective in USD; cost is bounded at $10,000 budget; revenue includes the empirical-floor sell price for unpriced byproducts.

## Files

| # | File | Description |
|---|---|---|
| 1 | 1_complexity_sweep_43k_rdkit.csv | Wall-clock per solve vs nested random subsample size of the 43K rdkit_balanced corpus, three modes (MILP, MILP-cap20, LP). 7 sample sizes (500 to 40000). Single seed (42); subsamples are nested. |
| 2 | 2_walltime_vs_rank_100k.csv | Wall-clock per solve vs forbid-loop rank on the 100K curated subset, three modes. 20 ranks. |
| 3 | 3_profit_vs_rank_43k_rdkit.csv | Solver profit (USD) vs forbid-loop rank on the 43K rdkit subset, three modes. 20 ranks. |
| 4 | 4_walltime_vs_rank_43k_rdkit.csv | Wall-clock per solve vs forbid-loop rank on the 43K rdkit subset, three modes. 20 ranks. |
| 5 | 5_profit_lp_vs_knuth_43k_rdkit.csv | Solver profit (USD) vs rank on the 43K rdkit subset: LP vs greedy Knuth-Dijkstra baseline. 20 ranks. |
| 6 | 6_walltime_lp_vs_knuth_43k_rdkit.csv | Wall-clock per solve vs rank on the 43K rdkit subset: LP vs greedy Knuth-Dijkstra baseline. 20 ranks. |

## Source JSONLs

For provenance, all six CSVs are derived from these JSON-Lines files in `data/processed/`:

| File | Source |
|---|---|
| 1 | complexity_sweep_rdkit_v2.jsonl |
| 2 | profit_curve.jsonl + profit_curve_cap20.jsonl + profit_curve_lp.jsonl |
| 3,4 | profit_curve_milp_rdkit.jsonl + profit_curve_cap20_rdkit.jsonl + profit_curve_lp_rdkit.jsonl |
| 5,6 | profit_curve_lp_rdkit.jsonl + profit_curve_knuth_rdkit.jsonl |
