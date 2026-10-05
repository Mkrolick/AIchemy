# CLAIM-11 — Apollo Scientific URL pattern + Apollo/Fluorochem common ownership

**Status:** FALSIFIED

**Claim:** `https://store.apolloscientific.co.uk/product/{slug}` shows public GBP/USD/EUR prices with per-warehouse stock counts. No anti-bot. ~50k–80k products. **Apollo and Fluorochem are under common ownership.**

## Verification steps performed

### URL probes

- [iter 11] curl `https://store.apolloscientific.co.uk/` (default UA) → **HTTP/2 403** from `awselb/2.0` (AWS WAF / blocking).
- [iter 11] curl with browser UA → **HTTP/2 302 → `https://www.apolloscientific.co.uk`** (the `store.` subdomain has been **decommissioned** and now redirects to the main marketing site).
- [iter 11] curl `https://www.apolloscientific.co.uk/product/acetophenone` → **404 Not Found**. The `/product/{slug}` URL pattern in the report does not exist on the main site.
- [iter 11] Main `www.apolloscientific.co.uk` returns 200 — but it's a WordPress marketing site (Yoast SEO plugin v27.3, `og:site_name = "Apollo Scientific"`, modified 2026-02-25). Page text: "Apollo Scientific is a reliable UK supplier of high-purity research chemicals for academic, biotech and industrial R&D." No e-commerce on this domain.

### Ownership

- [iter 11] WebSearch on Apollo + ownership: **Central Glass Co., Ltd of Japan acquired a 33% holding in Apollo Scientific in 2003**. Apollo "operates as part of the Central Glass Group". Confirmed by RD Chemicals, Bloomberg, Lookchem profiles, and Apollo's own "About" page.
- [iter 11] WebSearch on Fluorochem + ownership: Fluorochem Ltd founded 1999, separate company; **Apollo Scientific is listed as one of Fluorochem's top competitors**. **No evidence** of common ownership, sister-company relationship, or shared parent in Bloomberg, ZoomInfo, RocketReach, or PitchBook profiles.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| `store.apolloscientific.co.uk` URL works | ❌ | 302-redirects to www; subdomain decommissioned |
| `/product/{slug}` URL pattern works | ❌ | 404 on main site |
| Public GBP/USD/EUR prices | ❌ untestable | site is now a marketing-only WordPress page; no e-commerce |
| No anti-bot | ❌ | AWS WAF returned 403 to default-UA curl on the (now-defunct) store subdomain |
| ~50k–80k products | ❌ untestable | no live store to count |
| Apollo & Fluorochem common ownership | ❌ | Apollo owned 33% by Central Glass (Japan) since 2003; Fluorochem is an independent UK company and a competitor |

## Verdict

**FALSIFIED.** The most-load-bearing facts are wrong:
1. The `store.apolloscientific.co.uk` subdomain has been retired and redirects to a static WordPress marketing site. The `/product/{slug}` URL pattern doesn't exist anywhere on the current Apollo web presence.
2. **Apollo and Fluorochem are not under common ownership** — they are independent competitors. Apollo is part of the Central Glass Group (Japan, 33% acquisition 2003); Fluorochem is an independent UK company founded 1999. The "common ownership" framing in the report appears to be hallucinated.

**Implication for the pipeline:** Apollo Scientific should be **dropped from the scrape plan** until/unless a current e-commerce surface is identified. Fluorochem (CLAIM-01, PARTIAL) stands alone and should not be paired with Apollo on the assumption of shared infrastructure.
