# CLAIM-21 — Avanti Polar Lipids redirect to avantiresearch.com + Sigma `/product/avanti/{sku}`

**Status:** VERIFIED

**Claim:** Avanti is now at `avantiresearch.com` and prices flow through Sigma's `/product/avanti/{sku}`.

## Verification steps performed

- [iter 21] curl `https://avantilipids.com/` → **HTTP/2 301 → `https://www.avantiresearch.com/`** (Microsoft Azure App Gateway). Old domain redirects cleanly.
- [iter 21] curl `https://avantiresearch.com/` → 301 → `https://www.avantiresearch.com/` → 302 → `/en-gb`. New domain alive.
- [iter 21] WebSearch corroborated:
  - **September 3, 2024:** brand transformation announcement "Avanti Polar Lipids becomes Avanti Research, a Croda brand" (drug-dev.com, official press release on avantiresearch.com).
  - **2020:** Croda acquired Avanti for $185M up-front + up to $75M earnout (Croda investor page).
  - **December 2017:** MilliporeSigma signed distribution agreement with Avanti — explains why Avanti products live under Sigma's `/product/avanti/{sku}` brand prefix.
  - Live Sigma product URLs verifying the brand prefix:
    - `sigmaaldrich.com/US/en/product/avanti/860493p` (1-deoxysphinganine)
    - `sigmaaldrich.com/US/en/product/avanti/790595p` (Upstate Lipid Blend)
  - **Bonus warning:** "Product codes are changing in June 2026 due to implementation of a new SAP system" — pricing scrapers should expect SKU churn around this date.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| Avanti now at avantiresearch.com | ✅ | avantilipids.com 301-redirects to avantiresearch.com; live since 2024-09-03 |
| Croda ownership | ✅ | 2020 acquisition $185M + $75M earnout |
| Sigma `/product/avanti/{sku}` URL | ✅ | Multiple Google-indexed live products |
| Distribution path through Sigma | ✅ | MilliporeSigma distribution agreement Dec 2017 |
| Stable through 2026 | ⚠️ | Avanti SKU codes will change in June 2026 due to SAP migration — scraper should re-resolve mappings after the changeover |

## Verdict

**VERIFIED.** Both URLs (Avanti's own `avantiresearch.com` and Sigma's `/product/avanti/{sku}` brand prefix) are live and behave exactly as the report describes. Note for pipeline planning: the **June 2026 SAP migration** at MilliporeSigma will change Avanti product codes — any cached InChIKey → SKU mappings should be re-resolved after the changeover.
