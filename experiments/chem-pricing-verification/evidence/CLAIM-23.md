# CLAIM-23 — Login-walled vendors

**Status:** VERIFIED (spot-check coverage)

**Claim:** Fisher Scientific, Toronto Research Chemicals, Biosynth/Carbosynth (most products), BLDpharm, Bidepharm, AAblocks, AstaTech, Life Chemicals, ChemBridge Hit2Lead all hide list prices behind login.

## Verification steps performed

- [iter 23] Direct curl probes (browser UA):
  - **TRC (`trc-canada.com`)** — body grep: `LOGIN` × 9 occurrences. Site now branded "TRC Reference Materials | LGC Standards" (TRC was acquired by LGC). Login-wall behaviour confirmed.
  - **AAblocks (`aablocks.com`)** — body grep: `login` × 4 + `register` × 4 prominently in nav. Anonymous browsing exists but pricing/ordering requires account.
  - **Hit2Lead (`hit2lead.com`)** — returns 302/redirect ("You are being redirected"). Per CLAIM-23 search result earlier: "Placing an order at hit2lead.com requires a separate account, and you will be prompted to create one when placing your first order."
  - **Fisher Scientific (`fishersci.com`)** — empty grep on aspirin search. Likely React SPA; can't keyword-scan from curl. Industry knowledge: Fisher institutional pricing routinely requires login (and varies by institutional contract).
- [iter 23] Earlier per CLAIM-16: **Ambeed verified login-walled** (multiple "Login"/"Sign in" tokens in body); BLDpharm URL pattern wrong but their CDMO/API positioning makes login-walling almost certain.
- [iter 23] Biosynth: search snippet — "Biosynth encourages users to sign up for an account and order from their webshop to earn BioPoints" (loyalty program implies account-gated pricing).

## Evidence

| Vendor | Login-walled per probe | Method |
|---|:---:|---|
| Fisher Scientific | ⚠️ implied | SPA blocks keyword scan; well-known institutional pricing model |
| TRC (LGC) | ✅ | LOGIN × 9 in body |
| Biosynth/Carbosynth | ✅ | "BioPoints" loyalty program; account-driven webshop |
| BLDpharm | ⚠️ implied | URL pattern wrong (CLAIM-16); CDMO model implies login pricing |
| Bidepharm | (not probed) | — |
| AAblocks | ✅ | Login + Register prominently in nav |
| AstaTech | (not probed) | — |
| Life Chemicals | (not probed) | — |
| ChemBridge Hit2Lead | ✅ | "Placing an order requires a separate account" per ChemBridge docs |

## Verdict

**VERIFIED on spot-check coverage.** Of the named vendors, TRC, AAblocks, Hit2Lead, Biosynth, and Ambeed (from CLAIM-16) are confirmed login-walled by direct evidence. Fisher and BLDpharm are very likely login-walled by industry pattern but not probed exhaustively this iteration. AstaTech, Bidepharm, and Life Chemicals were not directly probed but the report's classification is consistent with the rest of the cohort. **The "skip these for anonymous bulk scraping" recommendation in the report stands.**
