# CLAIM-12 — TCI Chemicals URL pattern + anti-bot

**Status:** PARTIAL

**Claim:** `https://www.tcichemicals.com/{REGION}/{lang}/p/{PRODUCT_NUMBER}` where product numbers are letter+four-digits like `C3328`. Public prices, pack sizes, warehouse stock counts. ~40,000 products. SAP Hybris backend, **light anti-bot**.

## Verification steps performed

- [iter 12] curl `https://www.tcichemicals.com/US/en/p/C3328` (default UA) → empty response (silently dropped at TLS / WAF layer; rc=000).
- [iter 12] curl with browser UA (Chrome 124 macOS) → still no response from US/en path.
- [iter 12] curl JP/en path with browser UA → **HTTP/2 403** with `server: AkamaiGHost` (Akamai Bot Manager).
- [iter 12] WebFetch on `/US/en/p/C3328` → **timed out at 60s** (Akamai blocks).
- [iter 12] WebSearch corroborated URL pattern via Google-indexed live product pages:
  - `https://www.tcichemicals.com/US/en/p/V0058` (L-Valinol)
  - `https://www.tcichemicals.com/US/en/p/P0147` (D-Penicillamine)
  - The `letter+4digits` SKU shape is real.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| URL pattern `/{REGION}/{lang}/p/{SKU}` | ✅ | Google-indexed live products (V0058, P0147); shape matches |
| SKU is letter+4digits | ✅ | Confirmed via index |
| Public prices visible without login | ⚠️ | Not testable from anonymous CLI/WebFetch (Akamai blocks) — plausible but unverified at this level |
| Pack sizes / warehouse stock counts | ⚠️ | Not testable from CLI |
| ~40,000 products | ⚠️ | Not directly verified; search results say "full catalog requires approved TCI account" |
| SAP Hybris backend | ⚠️ | Not directly verified (can't read body); plausible per industry chatter |
| **"Light anti-bot"** | ❌ | TCI is fronted by **AkamaiGHost** — same Akamai Bot Manager as Sigma-Aldrich. Anonymous curl is dropped silently or 403'd. This is **not "light"**. |

## Verdict

**PARTIAL.** The URL template `tcichemicals.com/{REGION}/{lang}/p/{letter+4digits}` is correct and stable (corroborated by Google-indexed products). But the "light anti-bot" classification is **wrong** — TCI sits behind Akamai, the same heavy WAF that gates Sigma-Aldrich. A scraping pipeline must budget for residential-proxy rotation and per-IP throttling on TCI just like it does for Sigma. The report's tier-3 framing of TCI as a "clean public-price scrape" is too optimistic.
