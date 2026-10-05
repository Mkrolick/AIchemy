# Stage 09 — augment yields

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 09 COMPLETE`.

**Goal:** Fill missing `yield_rate` values via the strategy in `config.yields.strategy`.

**Strategies:**
- `global_mean` — simple mean over present values
- `per_ec_class` — for enzymatic reactions only, group by EC number (column added during ingest from MetaNetX), fill with per-class mean; fallback to global mean
- `fixed` — single configured value for all missing rows

## Tasks

### T1: `global_mean_imputer(df)`
- [ ] Failing test: df with 2 present + 3 missing → all missing filled with mean of present
- [ ] Implement via `pl.col("yield_rate").fill_null(pl.col("yield_rate").mean())`
- [ ] Commit

### T2: `per_ec_class_imputer(df)`
- [ ] Failing test: enzymatic rows grouped by EC class, per-class mean fills; chemical rows get global mean
- [ ] Implement: `group_by("ec_class").agg(pl.col("yield_rate").mean().alias("ec_mean"))` then left-join + coalesce
- [ ] Commit

### T3: `fixed_value_imputer(df, value)`
- [ ] Failing test: missing → `value`
- [ ] Implement: `fill_null(value)`
- [ ] Commit

### T4: `augment_yields(df, config)` dispatcher
- [ ] Failing test per strategy
- [ ] Dispatch via config.yields.strategy enum
- [ ] Commit

### T5: Wire CLI + dvc repro verify
- [ ] Commit + push
