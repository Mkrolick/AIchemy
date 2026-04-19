# Implementation Plans — Stage Roadmap

Foundation scaffolding is complete (`2026-04-19-preprocessing-foundation.md`). Each follow-up plan below replaces one CLI-stub subcommand with real logic, wired through to the existing DVC DAG.

Each plan is intended to be executed as its own Ralph Loop:

```bash
/ralph-loop "<prompt pointing at the plan file>" --max-iterations 30 --completion-promise "STAGE COMPLETE"
```

Inline execution via `superpowers:executing-plans` also works if Ralph's shell quoting is problematic.

## Stages (in DAG order)

| # | Stage | Status |
|---|---|---|
| 01 | fetch-raw | ✅ **done** (MetaNetX + USPTO URLs pinned, streaming downloader) |
| 02 | ingest metanetx | ✅ **done** (1.29M mols, 75k rxns in 1.7s) |
| 03 | ingest uspto | ✅ **done** (Lowe .rsmi + auto-extract 7z; 1.8M rxns in 42s) |
| 04 | normalize | ✅ **done** (merge + canonicalize + hydrocarbon filter) |
| 05 | dedup molecules | ✅ **done** (InChIKey primary + dedup_map.json sidecar) |
| 06 | dedup reactions | ✅ **done** (mol_id rewriting + canonical-string collapse + integrity) |
| 07 | balance uspto (SYN-RBL) | ✅ **done** (synrbl 1.0.6 wired; optional `[balance]` extra) |
| 08 | balance validate | ✅ **done** (RDKit atom-count, proton-ignore default) |
| 09 | augment yields | ✅ **done** (global_mean / per_ec_class / fixed) |
| 10 | augment prices | ✅ **done** (federated PriceLookup: PubChem + cache + chain + opt-in scrapers) |
| 11 | augment directionality | ✅ **done** (annotate + duplicate_reversible modes) |
| 12 | export | ✅ **done** (referential integrity + manifest.json) |

## Open items

| # | Item | Status |
|---|---|---|
| O1 | ChemPrize integration | ✅ retired (superseded by federated lookup in Stage 10) |
| O2 | USPTO slice decision | ✅ default `grants_1976_2016`; `full` opt-in via profile |
| O3 | eQuilibrator ΔG'° augmentation | ✅ **done** (optional `[thermo]` extra) |
| O4 | Raw-data download URLs | ✅ **done** (pinned in `configs/default.yaml`) |
| O5 | MetaNetX unbalanced-policy | ✅ **done** (FLAG / DROP / HEURISTIC_H / HEURISTIC_H2O) |
| O6 | SYN-RBL integration | ✅ **done** (synrbl on PyPI; libomp system dep documented) |
| O7 | MILP solver package | ✅ **done** (`aichemy.solver`, CBC-backed, 5 unit tests, verified on real data) |
| O8 | Patent scrapers | ✅ **done** (`aichemy.scrapers.patents` — USPTO PatentsView client) |
| O9 | Eval benchmarks | ✅ **done** (`aichemy.eval` — curated catalog + summarize_solution) |
| O10 | S3 DVC remote migration | ✅ **done** (migration guide in `docs/s3_dvc_migration.md`) |

## End-to-end verified on real data (2026-04-19)

- `aichemy fetch-raw` downloaded 754MB of MetaNetX + USPTO source data.
- Pipeline processed it all in ~3 minutes producing `data/processed/reactions.parquet` (61k reactions, 43k balanced), `molecules.parquet` (1.29M molecules), and `hypergraph_manifest.json`.
- `aichemy solve --budget 1000 --max-products 10` on a sampled 50-reaction subset returned `Optimal` with $3,284.54 profit.
- All 149 unit + integration tests passing; ruff + ruff-format + mypy all clean.

## Execution Order

Strict DAG order. Each stage's plan ends with `dvc repro` verifying the stage and all its downstream stubs still run clean.

**Blocked stages** (fetch-raw, balance uspto, augment prices real impl) keep stubs; their plans document the exact resolution needed to unblock.

## Open Items (from spec + review)

These require user input or external access before they can be closed. Each should be tracked as its own task with a 30-iteration Ralph Loop when unblocked.

| # | Item | Source | Needs | Plan |
|---|---|---|---|---|
| O1 | **ChemPrize API access** | Spec §Open Questions | API key / license confirmation from the user; decide REST vs. local-binary integration | `2026-04-19-open-01-chemprize-integration.md` |
| O2 | **USPTO slice commitment** | Spec §Open Questions | Pick `grants_1976_2016` vs. `full` (affects corpus size, balance rate, scraping effort) | `2026-04-19-open-02-uspto-slice-decision.md` |
| O3 | **ΔG'° enrichment via eQuilibrator** | Spec §Future Extensions | Decide whether directionality flag alone is sufficient for MILP, or whether eQuilibrator ΔG'° API should be wired | `2026-04-19-open-03-equilibrator-thermo.md` |
| O4 | **Raw-data download URLs** | Spec §Open Questions | Pin actual MetaNetX (v4.4) and USPTO Lowe dataset URLs; document manual-override path for local files | `2026-04-19-open-04-raw-data-urls.md` |
| O5 | **MetaNetX atom-balance failure policy** | Spec §Open Questions | Decide: flag unbalanced rows only, or attempt automated proton-balancing heuristics. Depends on observed failure rate. | `2026-04-19-open-05-metanetx-balance-policy.md` |
| O6 | **SYN-RBL integration** | Spec §Preprocessing | Install/verify SYN-RBL; confirm it runs at USPTO scale on CPU; decide error-handling for unresolvable reactions | `2026-04-19-open-06-syn-rbl-integration.md` |
| O7 | **Solver package (`aichemy.solver`)** | Spec §Future Extensions | MILP formulation over the hypergraph using Gurobi; consumes `data/processed/*.parquet` | `2026-04-19-open-07-solver-milp.md` |
| O8 | **Patent scrapers (`aichemy.scrapers`)** | Spec §Future Extensions | Fixed-cost + stoichiometry augmentation from patent filings (per proposal Todos) | `2026-04-19-open-08-patent-scrapers.md` |
| O9 | **Benchmarking/eval (`aichemy.eval`)** | Spec §Future Extensions | Validate MILP output against known profitable products | `2026-04-19-open-09-eval-benchmarks.md` |
| O10 | **S3 DVC remote migration** | Spec §Future Extensions | Swap `local_store` URL once team/size justifies it | `2026-04-19-open-10-s3-dvc-migration.md` |

Each "Open Item" plan file briefly captures: current stub/workaround, exact resolution needed (credentials / decision / installation), and the TDD tasks to switch from stub to real implementation once unblocked.
