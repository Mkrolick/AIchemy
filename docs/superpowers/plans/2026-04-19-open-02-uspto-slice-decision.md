# Open Item 02 — USPTO slice decision

**Needs user decision.** Choose `grants_1976_2016` (Lowe's ~1.8M reactions) vs. the full-patent superset (~3M+ including applications).

**Tradeoff:**
- Grants-only: cleaner data (granted ≠ just proposed), smaller corpus, better balance rate
- Full: broader coverage, but many duplicates of near-identical reactions, lower balance quality

**Recommendation:** start with `grants_1976_2016` (current default). Can revisit after Stage 03 ingests and we see coverage.

**Action:** confirm default via `configs/default.yaml` (already set to `grants_1976_2016`). No code changes needed unless slice changes.
