# CLAIM-14 — Cayman Chemical URL pattern

**Status:** VERIFIED (with notes)

**Claim:** `https://www.caymanchem.com/product/{itemID}/{slug}` with sequential 5–8 digit item IDs (enumerable). ~25,000 products. Public USD prices, JS-rendered.

## Verification steps performed

- [iter 14] curl HEAD on multiple IDs (100, 1000, 10000, 13649, 70000, 70071, 100000) → all 200 OK (SPA routing serves a 200 even for bogus IDs).
- [iter 14] WebSearch returned multiple Google-indexed live product pages with the exact pattern:
  - `/product/14010/prostaglandin-e2`
  - `/product/16824/17-phenyl-trinor-prostaglandin-f2alpha-isopropyl-ester`
  - `/product/14012/prostaglandin-e2-ethanolamide`
  - `/product/14750/16-16-dimethyl-prostaglandin-e2`
  - `/product/500141/prostaglandin-e2-express-elisa-kit` (6-digit)
  - `/product/514010/prostaglandin-e2-elisa-kit---monoclonal` (6-digit)
  - `/product/10007211/prostaglandin-e2-maxspec-registered-standard` (8-digit)
- [iter 14] curl body of `/product/14010/prostaglandin-e2` (3.9 KB) → has `<title>Prostaglandin E2 (CAS 363-24-6)…` (partial SSR — title and CAS in HTML) but **no `price`/`usd`/`sku`/`inStock` strings** — pricing is JS-rendered (XHR after page load).

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| URL pattern `/product/{itemID}/{slug}` | ✅ | Google-indexed live products |
| Item IDs are 5–8 digits | ✅ | Observed range: 14010 (5), 500141 (6), 10007211 (8) |
| **Sequential / enumerable** | ⚠️ | IDs are NOT strictly contiguous — large gaps + multiple disjoint ranges (5-digit reagents like 14010, 6-digit kits at 500K, 8-digit MaxSpec standards at 10M). Pure sequential enumeration would mostly miss. Better strategy: scrape from a sitemap or category index, then dereference. |
| ~25,000 products | ⚠️ | Not directly verified; broadly consistent with a specialty vendor but no current catalog count cited |
| Public USD prices | ⚠️ | Not directly verified — pricing is JS-loaded; report's claim is consistent with the partial-SSR markup observed. Browserbase or XHR-replay needed. |
| JS-rendered | ✅ | Confirmed — title in HTML but price/sku absent |
| No aggressive anti-bot | ✅ | curl with browser UA returns 200 + readable HTML; no Akamai/Cloudflare gate observed |

## Verdict

**VERIFIED with notes.** URL pattern, ID-width range, JS-rendering, and lack of aggressive anti-bot are all real. The "sequential" enumeration claim is **misleading** — IDs are non-contiguous across multiple ranges, so a scraper should drive from a sitemap or category index rather than `for id in range(1, 25000): ...`. The 25K product count is unverified but plausible.
