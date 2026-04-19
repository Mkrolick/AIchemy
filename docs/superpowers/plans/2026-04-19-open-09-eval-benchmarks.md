# Open Item 09 — Eval / benchmarking (`aichemy.eval`)

**Goal:** Benchmark the MILP output against known profitable products. Sanity-check: does the solver pick products that are *actually* profitable in the real world?

**Prerequisites:** Open Item 07 (solver) running end-to-end.

## Tasks (Ralph loop: 30 iterations when activated)

- [ ] Curate a "known good" list of profitable chemicals with published profit margins (e.g., pharma intermediates with known production data)
- [ ] Build `aichemy.eval.BenchmarkSuite` that runs the MILP, extracts its product selections, and compares against the curated list
- [ ] Metrics: top-K precision, top-K recall, predicted-vs-observed profit rank correlation
- [ ] Report in a markdown summary with plots
