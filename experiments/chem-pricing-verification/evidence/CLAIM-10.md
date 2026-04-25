# CLAIM-10 — Enamine screening collections

**Status:** VERIFIED

**Claim:** HTS 1.96M, Advanced 752k, Premium 72k at `enamine.net/compound-collections/screening-collection`.

## Verification steps performed

- [iter 10] curl HEAD `https://enamine.net/compound-collections/screening-collection` → 200 OK.
- [iter 10] curl HEAD `https://enamine.net/compound-collections/screening-libraries` → 404 (the report's URL is the canonical one).
- [iter 10] WebFetch on the screening-collection page returned verbatim numbers.

## Evidence

| Collection | Report says | Actual (verbatim) | Match? |
|---|---:|---:|:---:|
| HTS | 1.96M | **1,956,995** | ✅ |
| Advanced | 752k | **751,644** | ✅ |
| Premium | 72k | **71,974** | ✅ |
| Legacy | (not stated) | 1,716,643 | — |
| Functional | (not stated) | 239,713 | — |
| **Total Screening** | (not stated) | **4,736,969** | — |
| Liquid Stock UA | (not stated) | 1,069,144 | — |
| Liquid Stock US | (not stated) | 2,487,082 | — |

## Verdict

**VERIFIED.** All three numbers in the report match the current Enamine page to within typical rounding. URL is the canonical one. Notable contrast with CLAIM-09 (BB total was 4× too low and stale): the screening-collection figures here are current and precise — suggesting the report's quantitative claims are inconsistent in freshness rather than uniformly fabricated. Worth knowing about the additional 1.7M Legacy and 4.7M total collection figures the report didn't mention.
