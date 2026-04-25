# CLAIM-25 — Public-price vendors

**Status:** PARTIAL (Apollo FALSIFIED; Sigma & TCI weakened)

**Claim:** Fluorochem, Apollo, TCI, Sigma-Aldrich (US anon), Enamine (JS), Cayman (JS), MedChemExpress (CF), Santa Cruz/ChemCruz, Molbase, Tocris all show public list prices.

## Verification steps performed

This iteration synthesizes evidence from prior claims plus a fresh probe of Tocris.

- [iter 25] curl `tocris.com/products/aspirin_4906` (browser UA) → real product page with `<title>JW 642 | Monoacylglycerol Lipase | Tocris Bioscience</title>` and **multiple visible USD prices** ($9, $5, $1, $2, etc.) in the body. Tocris is confirmed public-anonymous.

## Per-vendor verdict

| Vendor | Public anon prices? | Source claim |
|---|:---:|---|
| Fluorochem | ✅ via undocumented Azure-blob JSON API | CLAIM-01 (PARTIAL — endpoint real, fields hallucinated) |
| **Apollo Scientific** | ❌ **store decommissioned** | CLAIM-11 (FALSIFIED — `store.` 302→www; main is WordPress marketing only) |
| TCI Chemicals | ⚠️ Akamai blocks anonymous probes; can't externally verify | CLAIM-12 (PARTIAL — URL real, anti-bot heavy not light) |
| Sigma-Aldrich (US anon) | ⚠️ "Sign in to View" increasingly common; Akamai | CLAIM-13 (VERIFIED with notes — pricing visibility weakening) |
| Enamine Store | ✅ JS-rendered, anonymous | CLAIM-07 (VERIFIED) |
| Cayman Chemical | ✅ partial-SSR, JS-loaded prices | CLAIM-14 (VERIFIED) |
| MedChemExpress | ✅ behind Cloudflare, visible to fingerprinted clients | CLAIM-15 (VERIFIED) |
| Santa Cruz/ChemCruz | ✅ moderate Cloudflare, browser UA passes | CLAIM-17 (VERIFIED) |
| Molbase | ✅ "price & availability" pages anonymous | CLAIM-18 (PARTIAL — URL form wrong, capability real) |
| Tocris | ✅ real USD prices visible in body without login | This iteration |

## Verdict

**PARTIAL.** 8 of 10 vendors are correctly classified as having public anonymous prices (Fluorochem, Enamine, Cayman, MCE, ChemCruz, Molbase, Tocris, plus Sigma-Aldrich which is *increasingly* gated). The big break:

- **Apollo Scientific is wrongly included** — its e-commerce surface no longer exists (CLAIM-11). It belongs in the "skip" tier, not the "public-price" tier.
- **Sigma-Aldrich's "public US anon" framing is weakening** — anonymous list prices are progressively being replaced with "Sign In to View" per CLAIM-13. Practical scraping can still extract some prices but should not assume universal anonymous visibility.
- **TCI's "public" classification is misleading** because the heavy Akamai protection (CLAIM-12) makes anonymous bulk scraping nontrivial — at scale, residential proxies + per-IP throttling is required, similar to Sigma.

**Operational implication:** the report's "Drug-like quick win" / "public-price scrapes" tier should be re-tiered: Fluorochem (JSON API), Enamine, Cayman, ChemCruz, MCE, Tocris, Molbase are genuinely public. TCI and Sigma require WAF-aware scraping infrastructure. Apollo should be removed entirely.
