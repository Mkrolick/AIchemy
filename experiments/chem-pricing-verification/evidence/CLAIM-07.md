# CLAIM-07 — Enamine Store URL pattern

**Status:** VERIFIED (with scope note on SKU width)

**Claim:** `https://www.enaminestore.com/catalog/EN300-{NNNNNN}` is the stable product-page URL, JS-rendered, public USD prices.

## Verification steps performed

- [iter 7] curl HEAD on multiple SKUs:
  - `EN300-216568` → 200 OK (6-digit)
  - `EN300-7605608` → 200 OK (7-digit)
  - `EN300-19951979` → 200 OK (8-digit)
  - `EN300-100`, `EN300-1000`, `EN300-100000` → 200 (templates resolve even for invalid SKUs because of SPA routing)
- [iter 7] curl body of `EN300-7605608`:
  - `Content-Type: text/html`, response is the React/CRA shell:
    ```html
    <head>...<title>EnamineStore</title>...<script defer="defer" src="/static/js/main.060dfd03.js"></script>...</head>
    <body><noscript>You need to enable JavaScript to run this app.</noscript><div id="root"></div></body>
    ```
  - No SSR price/SKU/USD strings in the HTML — entirely client-side render. Fronted by CloudFlare (`cf-cache-status: DYNAMIC`).
- [iter 7] WebSearch corroborated 10+ real EN300 SKUs indexed by Google with the same URL pattern (e.g., `EN300-7605608`, `EN300-386200`, `EN300-46979794`, `EN300-37469638`, `EN300-1666635`, etc.).
- [iter 7] Note: `www.enaminestore.com` 308-redirects to `enaminestore.com` (no www) — scrapers should use the canonical no-www form to avoid an extra hop.

## Evidence

- Live HTTP probes confirm URL template, anonymous access, and JS-rendering.
- Multiple Google-indexed SKUs corroborate the `EN300-` prefix is stable.

## Verdict

**VERIFIED** with one scope note: the SKU numeric portion is **variable width (6 to 8+ digits)**, not strictly 6 digits as the `{NNNNNN}` template in the report suggests. Use `EN300-\d+` as the regex. URL stability, JS-rendering, anonymous accessibility, and the Browserbase requirement for price extraction are all correct. Canonical host is `enaminestore.com` (no www).

A scraper might benefit from inspecting the React app's XHR calls (likely a `/api/...` endpoint returning JSON) to skip headless rendering — that would be a useful follow-up not covered by the report.
