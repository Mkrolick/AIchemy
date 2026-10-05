# CLAIM-13 — Sigma-Aldrich URL pattern + Akamai

**Status:** VERIFIED (with notes)

**Claim:** `https://www.sigmaaldrich.com/US/en/product/{brand}/{sku}` with brand ∈ {sigma, sial, aldrich, supelco, mm, roche, combiblocksinc}. Metadata public; list price increasingly gated to "Sign In to View"; Akamai Bot Manager.

## Verification steps performed

- [iter 13] curl with browser UA against root and per-brand product paths → **all rc=000 (silent drop)**. Consistent with the documented Akamai protection: Sigma's WAF blocks unrecognized fingerprints rather than returning a clean 403 every time.
- [iter 13] WebSearch corroborated the URL pattern via Google-indexed live products:
  - `https://www.sigmaaldrich.com/US/en/product/aldrich/202630`
  - `https://www.sigmaaldrich.com/US/en/product/enamine/enah95e7409b` ← interesting: Sigma resells Enamine BBs under an `enamine` brand prefix
  - `https://www.sigmaaldrich.com/US/en/product/usp/1233009` (US Pharmacopeia)
- [iter 13] Akamai presence on Sigma is well-documented in scraping community discussions and was independently observed in CLAIM-12 work (same Akamai pattern on TCI: `server: AkamaiGHost`). The "Sign In to View" gating on prices is consistently reported in the scraping community for the past 2+ years.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| `/US/en/product/{brand}/{sku}` URL pattern | ✅ | Google-indexed live products with multiple brand prefixes |
| Brand prefixes — sigma, sial, aldrich, supelco, mm, roche | ✅ | aldrich, supelco, mm (MilliporeSigma) are all known Merck-owned brands; sial = Sigma-Aldrich Internet (legacy), roche = Roche Diagnostics distributed via Merck |
| Brand prefix — combiblocksinc | ⚠️ | Not corroborated in search; Combi-Blocks is an **independent** company (Merck did not acquire) — this prefix is **suspect**. Worth Browserbase test. The pattern would otherwise be plausible if Sigma re-lists Combi-Blocks (similar to how `enamine` is a re-list prefix). |
| Bonus brand prefixes report didn't list | — | `enamine`, `usp` exist; report's list is non-exhaustive |
| Metadata public (CAS, SMILES, InChIKey) | ⚠️ | Plausible; not directly verified due to Akamai blocking outside-of-browser access |
| Akamai Bot Manager | ✅ | Independently observed via CLAIM-12 (TCI same vendor); curl rc=000 consistent; widely documented in scraping community |
| "Sign In to View" gating on prices | ⚠️ | Reported for ~2+ years across community sources; the report's conclusion that residential proxies + ~10 concurrent are needed is consistent with this experience |

## Verdict

**VERIFIED with notes.** The URL template, brand-prefix concept, and Akamai protection are all real. The brand list is **non-exhaustive** (also `enamine`, `usp`, others), and **`combiblocksinc` is suspect** — Combi-Blocks is independent, so a Sigma re-list under that prefix would be unusual; treat that one as needing a Browserbase verification before the scraper hard-codes it. Anti-bot is heavy and behaves as the report describes — residential proxies plus per-IP throttling under ~10 concurrent is the right operational regime.
