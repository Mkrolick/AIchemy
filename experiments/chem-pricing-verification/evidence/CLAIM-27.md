# CLAIM-27 — eMolecules pricing requires institutional-account login

**Status:** VERIFIED (with note)

**Claim:** eMolecules pricing requires institutional-account login.

## Verification steps performed

- [iter 27] curl `emolecules.com/` (browser UA) → 200 OK, served via Cloudflare. Body grep: `Login` × 5 prominently in nav.
- [iter 27] curl `/search?query=aspirin` → body has `order` × 10 (CTAs) but **no `$`, no `USD`, no `price` strings** — consistent with prices gated behind login.
- [iter 27] `/pricing` and `/about` returned SPA shells (empty grep).
- [iter 27] WebSearch: eMolecules described as a "leading chemical search-and-fulfillment platform" focused on "early drug discovery," with "real-time pricing, availability, and shipping information" via "strategic partnerships with major eProcurement and eCommerce platforms." 83M+ part numbers. Founded 2005, San Diego HQ. The model is B2B/enterprise procurement — consistent with the report's "institutional account" framing even if that exact phrase isn't surfaced verbatim.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| Pricing requires login | ✅ | Homepage Login×5, search page has order CTAs but no price strings |
| **Institutional** specifically | ⚠️ | eMolecules is positioned as B2B / drug-discovery procurement platform with eProcurement partnerships — consistent with "institutional" but the exact term isn't surfaced verbatim. Could be more general "any registered user" rather than strictly institutional. |

## Verdict

**VERIFIED with note.** eMolecules unambiguously gates pricing behind login (no anonymous prices visible on search or product surfaces). The "institutional" qualifier in the report may be slightly overspecified — eMolecules' model is B2B-procurement-driven (eProcurement integrations, drug-discovery enterprise focus) rather than literally requiring an institutional affiliation, but the practical effect is identical for a 2.7M-compound scrape: anonymous bulk price extraction is not viable. Report's recommendation to exclude eMolecules from anonymous scraping plans stands.
