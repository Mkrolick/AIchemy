# Patent Licensing in the AIchemy Pricing MILP — Design Spec

**Date:** 2026-04-25
**Status:** Brainstorm complete; pending user review before plan generation
**Scope:** Add patent-license cost as a factor in the AIchemy profit-maximization MILP. Introduces three new DVC pipeline stages (patent metadata fetch, CPC-code classification, LLM classification) plus a new `solve sweep` CLI subcommand for sensitivity analysis. Modifies the solver objective to include process and composition royalty terms.

## Context

The current AIchemy MILP (`src/aichemy/solver/model.py`) maximizes profit over a chemo-enzymatic reaction hypergraph but treats every reaction and product as freely usable. In reality, both **synthesis routes** (process patents) and **products** (composition-of-matter patents) can be patent-protected, requiring royalty payments to the patent holder. For a course-project deliverable that aims to be defensible rather than precisely accurate, this spec models license cost as a percentage royalty on net sales, with the actual royalty rate treated as a **sensitivity parameter** swept over the industry-typical range \[0%, 8%\] rather than fabricated as a single point estimate.

Reactions in the pipeline come from two sources (`src/aichemy/preprocessing/sources/`):
- **USPTO** — `rxn_id` format `USPTO:<patent_number>:<idx>` carries the source patent.
- **MetaNetX** — biochemistry / enzymatic reactions with no associated USPTO patent.

This spec covers only USPTO-sourced reactions. MetaNetX rows pass through with `patent_active=False, process_covered=False, composition_covered=False`, and the writeup will document this as a known scope limitation.

## Decisions

The following calls were made during brainstorming and are load-bearing for this design:

| Decision | Choice | Rationale |
|---|---|---|
| License cost model | Royalty-only, % of net sales | Industry-typical bound (3–8%); fixed fees have no defensible upper bound and would break sensitivity analysis |
| Royalty sweep range | \[0%, 8%\] | Industry-typical for fine/specialty chemistry; defensible in writeup without primary-source citation |
| License classification | Process and composition tracked as **separate booleans** | Process coverage blocks a synthesis route only; composition coverage blocks the compound by any route — different MILP implications |
| Patent metadata source | USPTO PatentsView REST API | Free, no auth, structured fields, covers 100% of Lowe-dataset patents |
| Classification strategy | CPC-code heuristic for the bulk; LLM classifies CPC-ambiguous patents in **eager mode** with persistent cache | Cheapest defensible option; one-time LLM cost (~$10–300); subsequent runs hit cache |
| LLM model | Claude Haiku 4.5 | Cheap structured-output classification with reasoning-quality sufficient for claim-scope judgment |
| LLM prompt content | Title + abstract + claims + reaction SMILES | Reaction SMILES gives the model "is this *specific* reaction in claim scope" signal beyond generic process/composition judgment |
| CPC rules | Externalized to `config/cpc_rules.yaml` | Tweakable without code changes; load-bearing for the writeup ("here are the rules we used") |
| DVC pipeline structure | Three thin stages + a merge step | Matches existing `augment_*` convention; lets each stage be cached/replayed independently |
| Sensitivity sweep | New `aichemy solve sweep` subcommand | Mirrors DVC stage convention; produces reproducible artifact (summary parquet) for the writeup |
| Sweep grid | 5×5 = 25 cells over (r_process, r_comp) | Smooth enough for a heatmap and "decision invariance map"; finishes in seconds |
| Default royalty rates in `SolverConfig` | 0.0 / 0.0 | Preserves existing solver behavior when license data is absent or rates aren't passed |
| Missing-data default for covered flags | `False` (no royalty applied) | Conservative for the optimizer (does not over-penalize); honest about data gaps in the writeup |

## Architecture

### Pipeline stages (DVC-orchestrated)

```
… → augment_directionality (existing)
        ↓
        data/interim/augmented/reactions_full.parquet
        ↓
[NEW] fetch_patent_metadata
        ↓
        data/interim/patents/patent_metadata.parquet
        ↓
[NEW] classify_licenses_cpc
        ↓
        data/interim/licenses/cpc_classifications.parquet
        ↓
[NEW] classify_licenses_llm
        ↓
        data/interim/licenses/llm_classifications.parquet
        + data/interim/licenses/llm_cache.jsonl   (DVC-tracked)
        ↓
[NEW] augment_licenses                            (merge step)
        ↓
        data/interim/augmented/reactions_licensed.parquet
        ↓
export → data/processed/reactions.parquet         (consumed by solver)
```

### Solver integration

Existing entry point `build_and_solve()` in `src/aichemy/solver/model.py` is extended to:
1. Read three new columns from the reactions DataFrame (`patent_active`, `process_covered`, `composition_covered`).
2. Subtract two new royalty terms from the objective function (both linear in existing decision variables).
3. Accept two new scalars on `SolverConfig`: `r_process` and `r_comp`, both defaulting to `0.0`.

A new CLI subcommand `aichemy solve sweep` (in `src/aichemy/solver/cli.py`) loops `build_and_solve()` over a 2-D grid of (r_process, r_comp) values, writes per-cell solutions and a top-level summary parquet.

## Data shapes

### `patent_metadata.parquet` — produced by `fetch_patent_metadata`

One row per **unique** USPTO patent referenced by any USPTO reaction.

| Column | Type | Notes |
|---|---|---|
| `patent_number` | `str` | PatentsView primary key (e.g., `7456123`) |
| `filing_date` | `date` | Used to compute expiry (filing + 20yr) |
| `grant_date` | `date \| null` | For traceability |
| `abstract` | `str \| null` | LLM input |
| `claims_text` | `str \| null` | Concatenated independent claims; LLM input |
| `cpc_codes` | `list[str]` | E.g., `["C07D 401/12", "A61K 31/505"]` |
| `assignee` | `str \| null` | Surfaced in writeup, not used in MILP |
| `fetch_status` | `str` | `"ok"`, `"not_found"`, `"error"` |

### `cpc_classifications.parquet` — produced by `classify_licenses_cpc`

One row per `(rxn_id, patent_number)` pair. By construction this is always 1:1 within the current data (each USPTO `rxn_id` embeds exactly one patent number; MetaNetX rows do not enter this stage), but the table is keyed on the pair to support potential future composition-of-matter lookup that could attach additional patents to a reaction.

| Column | Type | Notes |
|---|---|---|
| `rxn_id` | `str` | |
| `patent_number` | `str` | |
| `patent_active` | `bool` | `today < filing_date + 20yr` |
| `cpc_process_hit` | `bool` | Any of the process CPC codes present |
| `cpc_composition_hit` | `bool` | Any of the composition CPC codes present |
| `cpc_ambiguous` | `bool` | Both hits, A61K (medicinal — composition vs. method-of-use), or no chemistry codes |
| `process_covered_cpc` | `bool` | `cpc_process_hit and not cpc_ambiguous` |
| `composition_covered_cpc` | `bool` | `cpc_composition_hit and not cpc_ambiguous` |

Inactive patents short-circuit: `patent_active=False` → both covered flags `False`, `cpc_ambiguous=False`. No LLM call follows.

### CPC rule set (`config/cpc_rules.yaml`)

```yaml
process_codes:
  - "C07B"   # general organic process
  - "C07C"   # acyclic / carbocyclic process
  - "B01J"   # catalysts / reactor processes
  - "C12P"   # fermentation / enzymatic processes
composition_codes:
  - "C07D"   # heterocyclic compounds
  - "C07E"
  - "C07F"
  - "C07G"
  - "C07H"
  - "C07J"
  - "C07K"
ambiguous_codes:
  - "A61K"   # medicinal preparations — needs LLM to disambiguate composition vs. method-of-use
```

### `llm_classifications.parquet` — produced by `classify_licenses_llm`

One row per **unique** patent with `cpc_ambiguous=True AND patent_active=True`.

| Column | Type | Notes |
|---|---|---|
| `patent_number` | `str` | |
| `process_covered` | `bool` | LLM judgment |
| `composition_covered` | `bool` | LLM judgment |
| `confidence` | `float` | Self-reported \[0,1\] from the model |
| `rationale` | `str` | One-sentence justification — surfaced for spot-checking |
| `model` | `str` | E.g., `"claude-haiku-4-5"` |
| `cache_hit` | `bool` | `False` for fresh calls, `True` on replay |

### `llm_cache.jsonl` (cache file, DVC-tracked)

```jsonl
{"patent_number":"7456123","process_covered":true,"composition_covered":false,"confidence":0.86,"rationale":"Independent claim 1 covers a method for…","model":"claude-haiku-4-5","ts":"2026-04-25T14:32:01Z"}
```

Append-only. Cache key is `patent_number` alone. PatentsView is canonical: abstract/claims for a given patent number are stable, so prompt content variation isn't a concern.

### `reactions_licensed.parquet` — final shape consumed by the solver

Existing columns (per `solver/model.py:78-114`) plus three new:

| Column | Type | Notes |
|---|---|---|
| `patent_active` | `bool` | `False` for MetaNetX rows (no patent) |
| `process_covered` | `bool` | LLM result if available, else CPC; `False` for MetaNetX |
| `composition_covered` | `bool` | LLM result if available, else CPC; `False` for MetaNetX |

**Resolution rule** (in `augment_licenses`): for each `(rxn_id, patent_number)` pair, if `cpc_ambiguous` and a matching LLM row exists, use LLM; otherwise use CPC. The merge produces one row per `rxn_id`. If a reaction is associated with multiple patents (not produced by current stages but supported by the schema), `process_covered = OR across patents`, same for composition.

## MILP changes

### Current objective (`src/aichemy/solver/model.py:146-151`)

```
maximize:  Σ_m  price_sell[m] · q_sell[m]
        −  Σ_m  price_buy[m]  · q_buy[m]
```

### New objective

```
maximize:  Σ_m  price_sell[m] · q_sell[m]
        −  Σ_m  price_buy[m]  · q_buy[m]
        −  r_process · Σ_{r ∈ process_covered}  ( price_sell[product(r)] · η_r · f_r )
        −  r_comp    · Σ_{m ∈ composition_covered} ( price_sell[m] · q_sell[m] )
```

Both new terms are linear in existing decision variables (`f_r`, `q_sell[m]`). The `process_covered` / `composition_covered` booleans are pre-computed in the data — they only gate which reactions/molecules contribute to the royalty sums at model-build time. No new binary variables required; no change to constraint structure.

**Edge case:** `process_covered=True` reactions whose products do not appear in `q_sell` (i.e., intermediates only) still pay process royalty in proportion to flow `f_r`, but since their product isn't sold the term `price_sell[product(r)] · η_r · f_r` represents *implied revenue if it were sold at market price*. This is a modeling approximation; alternative is to drop process royalty for non-terminal intermediates. The implementation will use the implied-revenue form (consistent with treating the route license as a per-unit-of-route fee tied to the throughput of the patented chemistry) and document this in the writeup.

### `SolverConfig` additions (`src/aichemy/solver/config.py`)

```python
r_process: float = 0.0   # royalty rate on process-covered reaction revenue, [0, 1]
r_comp:    float = 0.0   # royalty rate on composition-covered product revenue, [0, 1]
```

Default `0.0` preserves existing solver output exactly.

## Sensitivity sweep

### CLI

```
aichemy solve sweep \
  --reactions data/processed/reactions.parquet \
  --molecules data/processed/molecules.parquet \
  --r-process 0,0.02,0.04,0.06,0.08 \
  --r-comp    0,0.02,0.04,0.06,0.08 \
  --out       data/processed/sensitivity/
```

Default grid: 5 × 5 = 25 cells. Values are **decimal fractions** (`0.04` = 4%), comma-separated. Configurable.

### Outputs

- `data/processed/sensitivity/runs/r_process_<X>_r_comp_<Y>/solution.json` — full per-cell solution.
- `data/processed/sensitivity/summary.parquet` — one row per grid point:

| Column | Type |
|---|---|
| `r_process` | `float` |
| `r_comp` | `float` |
| `objective_value` | `float \| null` (null if infeasible) |
| `n_active_reactions` | `int` |
| `n_sold_products` | `int` |
| `set_hash` | `str` (hash of the multiset of sold mol_ids — used to detect "did the optimal set change") |
| `infeasible` | `bool` |

### Writeup artifacts derived from the summary

- **Decision invariance map** — heatmap on the (r_process, r_comp) plane colored by `set_hash` region. Shows where the optimal product/reaction set is invariant to royalty assumptions.
- **Objective heatmap** — same plane, colored by `objective_value`.

## Error handling

- **PatentsView fetch failure** — `fetch_status="error"` written; downstream stages treat the patent as `patent_active=False` (conservative default: assume expired / no license needed). Pipeline continues.
- **LLM API failure (after 3 retries)** — fall back to the patent's CPC classification. If CPC was ambiguous, default to `process_covered=False, composition_covered=False`. Stage emits a one-line summary at the end (`"LLM resolved 4,871 / 5,012 ambiguous patents; 141 fell back to CPC default"`).
- **MILP infeasibility at high royalty rates** — sweep records `objective_value=null, infeasible=True` for that cell and continues. Surfaced in the summary parquet so the writeup can identify the boundary.
- **No internet during pipeline run** — only `fetch_patent_metadata` requires network. The DVC cache means subsequent runs work fully offline.

## Testing

### Unit tests (`tests/unit/`)

- `test_cpc.py` — fixture patents with hand-labeled CPC codes; verify each rule branch (process-only, composition-only, ambiguous).
- `test_llm_classify.py` — stubbed LLM client (no real API calls in CI); verify cache write, cache read, retry behavior, fallback on failure.
- `test_augment_licenses.py` — small synthetic reactions + classifications DataFrames; verify merge resolution rule (LLM takes precedence; CPC fallback; multi-patent OR aggregation).
- `test_solver_royalty.py` — extends `test_solver.py`. Two-reaction fixture; one `process_covered=True`. Assert: at `r_process=0` objective matches current; at `r_process=0.5` objective is reduced by exactly the expected amount.
- `test_sweep.py` — 2×2 grid over a tiny fixture; assert summary parquet shape and that `set_hash` differs across cells where the optimal set actually changes.

### Integration test

Full `dvc repro` on the existing tiny fixture (`tests/fixtures/`), with PatentsView calls stubbed via the `responses` library. Verifies the new stages slot into the existing DAG without breaking `augment_directionality → export → solve run`.

## Known limitations (documented in writeup)

1. **MetaNetX has no patent coverage modeled.** Enzymatic synthesis can still produce a patented compound; we don't check this. Future work: composition-of-matter search by InChIKey against PatentsView would close the gap.
2. **Patent extension and terminal disclaimer effects** are ignored. Expiry is computed as `filing_date + 20 years`; real-world patent life can be extended (Hatch-Waxman for pharma) or shortened (terminal disclaimer). Most matter for pharmaceutical APIs and would shift expiry by months to a few years.
3. **The patent associated with a reaction is the patent it was *extracted from*** (Lowe dataset provenance), not necessarily the patent that *legally protects* the route. A reaction might be prior art the patent merely cites. The LLM classifier mitigates this when the patent's claims clearly cover something else, but doesn't eliminate the issue.
4. **Process royalty on intermediate-only reactions** uses implied market-price revenue rather than a per-unit-of-chemistry fee — a modeling choice rather than a fact about how license deals work.
5. **Royalty rate range \[0%, 8%\] is industry-typical for fine/specialty chemistry** but actual deals vary widely. The sweep is intended to demonstrate decision robustness within this range, not predict the rate of any specific deal.

## Out of scope

- Fixed annual access fees / lump-sum license fees (no defensible bound).
- Per-deal license terms (running royalty steps, exclusivity premiums, sublicense rights, etc.).
- International patents (Lowe data is USPTO-only; coverage outside the US not modeled).
- Patent maintenance-fee status check (`patent_active` is an *eligibility* check based on filing date — does not verify the holder still pays maintenance fees).
- Patent litigation status, opposition proceedings, or post-grant review outcomes.
