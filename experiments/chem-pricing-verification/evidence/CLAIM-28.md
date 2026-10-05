# CLAIM-28 — USPTO yield estimate

**Status:** PLAUSIBLE-OPTIMISTIC (estimate, not VERIFIED/FALSIFIED)

**Claim:** 600,000–800,000 priced compounds out of the 1.2M USPTO set after Enamine resolution (50–70% hit rate).

## Verification anchors

### USPTO compound count

- Lowe USPTO 1976–2016 dataset has ~1.94M reactions (per ORDerly / OpenReactionDatabase / rxn4chemistry citations).
- Unique molecule counts after dedup vary by source but are typically 1.5–2M when reactants + products are combined (and ~600K–1M when restricted to either side).
- The report's "1.2M USPTO compound list" is plausible if reactants + products are deduped together.

### Enamine BB catalog (per CLAIM-09)

- Actual size: **2,292,307 compounds** total / **300,000 in stock** — the report's working-assumption of 573K was off by 4×.
- A 600K–800K match count against a 573K BB catalog would be **mathematically impossible** under the report's own assumption (you can't match more compounds than the catalog contains). The 600K–800K figure only becomes feasible against the *real* 2.29M catalog.

### Empirical hit-rate anchors from the literature

- **ASKCOS**: uses a 107K curated commercial set (Sigma + eMolecules under $100/g) as default starting material; explicitly says "addition of Enamine building blocks could find routes for additional compounds".
- **Retrosynthesis solve rates** (different from direct match):
  - 215 / 300 = 71.7% routes-found rate on one curated benchmark
  - 3,517 / 9,621 = 36.5% routes-found rate on another
- **Direct InChIKey match against Enamine BBs** is typically much lower than retrosynthesis solve rate, because most USPTO molecules are *products* of multi-step synthesis, not BBs themselves. Reactants have higher overlap (~40–70%); products have much lower overlap (~5–20%).

## Assessment

| Aspect | Verdict |
|---|---|
| Internal consistency of report's math | ❌ — 600K–800K matches against the report's assumed 573K BB catalog is impossible |
| Feasibility against the *actual* 2.29M BB catalog | ✅ — 600K–800K is achievable in principle |
| Realism of "50–70% hit rate" on a mixed reactant+product set | ⚠️ Optimistic. More likely 30–50% if 1.2M is mixed; 60–70% would only hold if the 1.2M skews heavily toward reactants. |
| Likely actual yield (revised estimate) | **360K–600K priced compounds** (30–50% hit rate × 1.2M) |

## Verdict

**PLAUSIBLE-OPTIMISTIC.** The 50–70% hit rate is at the upper end of what literature suggests. A more conservative range — **360K–600K priced compounds (30–50% hit rate)** — is the better operational estimate. Critically, the report's *own* internal math was inconsistent (claimed 600K–800K hits against an assumed 573K catalog) and only becomes physically possible because Enamine's actual catalog is ~4× larger than the report assumed (CLAIM-09). The strategic conclusion (Enamine = primary USPTO matcher) survives, but the headline number should be revised down.
