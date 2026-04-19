# Implementation Plans — Stage Roadmap

Foundation scaffolding is complete (`2026-04-19-preprocessing-foundation.md`). Each follow-up plan below replaces one CLI-stub subcommand with real logic, wired through to the existing DVC DAG.

Each plan is intended to be executed as its own Ralph Loop:

```bash
/ralph-loop "<prompt pointing at the plan file>" --max-iterations 30 --completion-promise "STAGE COMPLETE"
```

Inline execution via `superpowers:executing-plans` also works if Ralph's shell quoting is problematic.

## Stages (in DAG order)

| # | Stage | Plan | Status | Blockers |
|---|---|---|---|---|
| 01 | fetch-raw | `2026-04-19-stage-01-fetch-raw.md` | 🔴 blocked (stub) | Needs pinned MetaNetX + USPTO URLs (Open Item 04) |
| 02 | ingest metanetx | `2026-04-19-stage-02-ingest-metanetx.md` | ✅ **done** | — |
| 03 | ingest uspto | `2026-04-19-stage-03-ingest-uspto.md` | 🟡 stub | fixture-driven; follow-up plan ready |
| 04 | normalize | `2026-04-19-stage-04-normalize.md` | ✅ **done** | — |
| 05 | dedup molecules | `2026-04-19-stage-05-dedup-molecules.md` | ✅ **done** | — |
| 06 | dedup reactions | `2026-04-19-stage-06-dedup-reactions.md` | ✅ **done** | — |
| 07 | balance uspto (SYN-RBL) | `2026-04-19-stage-07-balance-uspto.md` | 🔴 blocked (stub) | SYN-RBL package availability (Open Item 06) |
| 08 | balance validate | `2026-04-19-stage-08-balance-validate.md` | ✅ **done** | — |
| 09 | augment yields | `2026-04-19-stage-09-augment-yields.md` | ✅ **done** | — |
| 10 | augment prices | `2026-04-19-stage-10-augment-prices.md` | ✅ **done (MVP)** | Web-scraping + ZINC layers pending; PubChem + cache + chain live |
| 11 | augment directionality | `2026-04-19-stage-11-augment-directionality.md` | ✅ **done** | — |
| 12 | export | `2026-04-19-stage-12-export.md` | ✅ **done** | — |

**Completed overnight 2026-04-19:** Stages 02, 04, 05, 06, 08, 09, 10 (MVP), 11, 12. All with TDD unit tests, CLI wiring, and DVC-stage integration. 121 tests passing, all lint/typecheck green, `dvc repro` clean end-to-end.

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
