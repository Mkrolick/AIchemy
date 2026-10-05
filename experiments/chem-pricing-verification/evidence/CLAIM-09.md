# CLAIM-09 — Enamine BB catalog size

**Status:** PARTIAL

**Claim:** ~573,000 compounds in BB catalog, 300,000+ in stock.

## Verification steps performed

- [iter 9] WebFetch `enamine.net/building-blocks/building-blocks-catalog` quoted the page verbatim:
  > "2 292 307" building blocks in the comprehensive catalog
  > "300 000" compounds available in stock with 1–7 days delivery
  > "Global Stock" subset of "964 089" compounds across distribution network
- [iter 9] WebSearch corroboration: "Enamine's catalogue currently contains 2,292,307 building blocks including 300,000 compounds in stock". Confirmed by multiple Enamine sub-pages (`/building-blocks`, `/`, `/tangible-building-blocks`).

## Evidence

| Metric | Report says | Actual (2026) |
|---|---:|---:|
| Total BB catalog | ~573,000 | **2,292,307** |
| In stock (1–7 day) | 300,000+ | **300,000** ✓ |
| Global stock | (not stated) | 964,089 |

## Verdict

**PARTIAL.** The "300,000 in stock" number is exactly correct. The total catalog claim of "~573,000" is **off by ~4×** — the real figure is **2.29 million**. The discrepancy is large enough to be material:

- Strategically: a larger BB catalog *strengthens* the report's recommendation to use Enamine as primary for USPTO (more candidate matches), not weakens it. The 600K–800K downstream price-resolution estimate (CLAIM-28) was anchored on the smaller catalog and is therefore likely conservative.
- Tactically: the "573,000" number looks like a stale figure from ~2018 (Enamine was at roughly that size then per news archives) — typical hallucination pattern of pulling an outdated number from training data.
