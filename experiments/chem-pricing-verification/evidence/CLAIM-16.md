# CLAIM-16 — Ambeed/BLD CAS URL patterns

**Status:** PARTIAL (Ambeed verified, BLD URL falsified)

**Claim:** `https://www.ambeed.com/products/{CAS}.html` and `https://www.bldpharm.com/products/{CAS}.html` are CAS-keyed but login-walled on price.

## Verification steps performed

### Ambeed (aspirin, CAS 50-78-2)

- [iter 16] curl `ambeed.com/products/50-78-2.html` GET → real product body returned, `<title>Aspirin (Acetylsalicylic Acid) | COX Inhibitor | AmBeed.com`. (HEAD returned 405 — nginx denies HEAD specifically; GET works.)
- [iter 16] Body grep: many "login" / "Sign in" / "Login" / "inquiry" strings — consistent with prices behind login.
- [iter 16] Search corroboration: official Ambeed login page exists at `/user/login.html`. Catalog: 65K US-stock / 110K global-stock per LinkedIn / Metoree.

### BLDpharm (aspirin, CAS 50-78-2)

- [iter 16] curl `bldpharm.com/products/50-78-2.html` GET → body title `<title>404 Error</title>`. **URL pattern is wrong.**
- [iter 16] curl `bldpharm.com/search.html?key=50-78-2` → `<title>404 | BLDpharm</title>`. Search endpoint also wrong.
- [iter 16] Probed alternates: `/product/50-78-2`, `/p/50-78-2.html`, `/cas/50-78-2`, `/products/aspirin`, `/products/BD0001` — all 405 (nginx denies HEAD on every URL; need GET to truly diagnose, but pattern is clearly not the report's `/products/{CAS}.html`).
- [iter 16] WebSearch did not surface a canonical BLD product URL pattern in 2026 results.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| Ambeed URL `/products/{CAS}.html` | ✅ | Live aspirin page returned with correct title |
| Ambeed login-walled on price | ✅ | Multiple "Login"/"Sign in" tokens in body; Ambeed `/user/login.html` exists |
| BLD URL `/products/{CAS}.html` | ❌ | Returns `404 Error` body |
| BLD login-walled on price | ⚠️ | Plausible per industry norm + their CDMO/API focus, but couldn't verify because URL pattern itself is wrong |

## Verdict

**PARTIAL.** Ambeed's CAS-keyed URL is correct and login-walled prices are confirmed. **BLDpharm's URL pattern in the report is wrong** — `/products/{CAS}.html` returns a 404 body. BLD's actual URL pattern was not discoverable in this iteration (HEAD requests blanket-405 on this site; would need a sitemap fetch or rendered search). For pipeline planning: Ambeed remains correctly classified as login-walled (skip for anonymous price scraping); BLD should be marked TODO until a real URL example is sourced (e.g., from Google scholar / ChemSpider supplier link), and not relied on without that.
