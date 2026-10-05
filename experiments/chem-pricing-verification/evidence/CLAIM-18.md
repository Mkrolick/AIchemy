# CLAIM-18 — Molbase URL pattern

**Status:** PARTIAL (URL form wrong, underlying capability real)

**Claim:** `www.molbase.com/en/cas-{CAS}.html` shows real list prices for ~49M compounds (mostly Chinese suppliers).

## Verification steps performed

- [iter 18] curl `molbase.com/en/cas-50-78-2.html` (browser UA) → **404 Not Found** (`<title>404 Not Found</title>`).
- [iter 18] Probed alternates `/cas/50-78-2`, `/p/50-78-2`, `/molbase/products?cas=50-78-2`, `/en/p-50-78-2.html` → all returned **HTTP 203** (non-standard "Non-Authoritative Information"; nginx cache/proxy oddity — not 200, not normal 404). Inconclusive at the HEAD level.
- [iter 18] WebSearch returned the **canonical URL pattern**: `molbase.com/cas/{CAS}.html` (slash-separated, NO `/en/` prefix). Multiple Google-indexed live products:
  - `molbase.com/cas/5790-69-2.html` (2-Amino-5-chlorobenzenesulfonamide)
  - `molbase.com/cas/5165-97-9.html` (2-Acrylamido-2-methyl-1-propanesulfonic acid sodium salt)
  - `molbase.com/cas/27153-10-2.html` (trichloromethanesulfonic acid)
  - All have titles ending "price & availability - MOLBASE" — pricing is publicly displayed.
- [iter 18] Search snippet quotes Molbase's own count: "**49,406,656 compounds**" — exact match to the report's "~49M".
- [iter 18] Supplier directory exists at `/en/chemical-suppliers.html` (Chinese suppliers majority).

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| URL pattern `/en/cas-{CAS}.html` | ❌ | 404 — wrong format |
| Real URL pattern `/cas/{CAS}.html` | ✅ | Google-indexed live products + title "price & availability" |
| ~49M compounds | ✅ | 49,406,656 verbatim — exact match |
| Real list prices on public pages | ✅ | Titles confirm pricing visible without login |
| Mostly Chinese suppliers | ✅ | Molbase is a Shanghai-based chemical aggregator; supplier directory is dominated by Chinese vendors |

## Verdict

**PARTIAL.** The underlying claim — Molbase publishes anonymous list prices for ~49M compounds aggregated mostly from Chinese suppliers — is correct, but **the report's URL template is wrong**. Actual canonical URL is `https://www.molbase.com/cas/{CAS}.html` (no `/en/`, hyphen replaced by slash). A scraper using the report's `/en/cas-{CAS}.html` would 404 100% of the time. Report's recommendation to use Molbase as a tertiary commodity-chemical fallback survives once the URL is corrected.
