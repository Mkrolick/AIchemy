# CLAIM-17 — Santa Cruz / ChemCruz

**Status:** VERIFIED

**Claim:** 175,000 biochemicals at `https://www.scbt.com/p/{slug}-{cas}`, moderate Cloudflare.

## Verification steps performed

- [iter 17] curl `scbt.com/p/aspirin-50-78-2` (browser UA) → **200 OK**, served via Cloudflare (`cf-ray: 9f2022776b90f45a-IAD`, `cf-cache-status: DYNAMIC`).
- [iter 17] WebSearch corroborated multiple Google-indexed live products with the exact pattern:
  - `/p/aspirin-50-78-2` (Aspirin)
  - `/p/salicylic-acid-69-72-7` (Salicylic acid)
  - `/p/acetylsalicylic-acid-d3-921943-73-9` (deuterated standard, 9-digit CAS)
- [iter 17] Search snippet states verbatim: "Santa Cruz Biotechnology is the #1 supplier of biochemicals for research and offers over **175,000 specialty biochemicals under the ChemCruz® brand**" — exact match to report.
- [iter 17] Cloudflare classification: returns 200 OK with browser UA, no JS challenge or 403 — "moderate" is the right tier (lighter than MedChemExpress, much lighter than Akamai-gated Sigma/TCI).

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| URL pattern `/p/{slug}-{CAS}` | ✅ | `aspirin-50-78-2` returns 200 OK; multiple Google-indexed examples |
| 175,000 ChemCruz biochemicals | ✅ | Exact match to vendor's own marketing copy ("over 175,000 specialty biochemicals under ChemCruz®") |
| Moderate Cloudflare | ✅ | cf-ray + cf-cache-status headers present; 200 OK on browser UA — passes through, but CF is in front |

## Verdict

**VERIFIED.** URL pattern, biochemical count, and Cloudflare characterization all match. ChemCruz is a reasonable Tier-2 metabolite supplement as the report recommends; expect a CF challenge if scaled aggressively, but at modest concurrency a clean residential session should pass.
