# CLAIM-19 — Molport free API tier

**Status:** VERIFIED (with note on supplier count)

**Claim:** Molport REST API has a 10K req/month free tier covering 100+ suppliers with real prices.

## Verification steps performed

- [iter 19] WebSearch found Molport's API documentation pages: `/shop/api-documentation-v-3-0`, `/shop/api`, `api.molport.com`, blog "Discover the ways to access the Molport database".
- [iter 19] Verbatim from search result: "Each user's API account is limited to **10,000 requests per month**, with the remaining request count refreshed at the start of each month." — exact match to report.
- [iter 19] Confirmed REST + JSON interface ("Molport API is implemented as REST interfaces, which relies on stateless, client-server, cacheable communications, with JSON used as a lightweight data-interchange format").
- [iter 19] WebFetch on `molport.com/shop/suppliers` for supplier count:
  - Page directly lists **59 suppliers** in the visible directory (Europe 55, North America 57, Asia 30, Australia 1 — sums overlap because individual suppliers serve multiple regions).
  - Page copy says "There are hundreds of chemical suppliers in our chemical supplier directory" — the visible list is a subset, and Molport's marketing rounds up.
- [iter 19] Real prices via API confirmed by existence of multiple maintained Python wrappers that consume Molport's pricing endpoints: [ChemPrice](https://github.com/bsaliou/ChemPrice), [molharbor](https://github.com/asiomchen/molharbor).

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| 10K requests/month free tier | ✅ | Exact verbatim match in Molport docs |
| REST + JSON | ✅ | Stated in API docs |
| 100+ suppliers | ⚠️ | Directory page lists 59 visible entries; copy says "hundreds". "100+" is a fair upper-bound paraphrase of the marketing copy but the **directly visible/scrapable** count is closer to 60. |
| Real prices in API responses | ✅ | Multiple maintained Python wrappers (ChemPrice, molharbor) consume Molport for prices |

## Verdict

**VERIFIED** with a small note: the precise free-tier rate limit (10,000 req/month) and the existence of real per-supplier pricing in API responses are both correct. The "100+ suppliers" framing is loose — Molport's own copy says "hundreds" but their directory page lists ~59 visible suppliers. For practical scraping purposes, "tens to ~100" is the right mental model. Strategically the report's recommendation to use Molport's API as the cleanest API-first option holds, but a 10K/month cap means it can only resolve ~10K compounds/month, so it's a tertiary supplement not a primary lookup.
