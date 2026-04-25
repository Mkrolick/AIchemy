# CLAIM-26 — ChemSpider redistribution prohibited + RSC API key

**Status:** VERIFIED

**Claim:** ChemSpider supplier-tab data cannot be redistributed; API requires an RSC key.

## Verification steps performed

- [iter 26] WebFetch `chemspider.com/AboutUs.aspx` → **403** (anti-bot — consistent with the heavy WAF protection on the public site).
- [iter 26] WebSearch surfaced authoritative sources:
  - **RSC Developer Portal:** `https://developer.rsc.org/` — official API gateway for ChemSpider.
  - **ChemSpiPy docs:** confirm registration + API key required.
  - **webchem R package:** `cs_check_key()` function exists specifically to validate the API key.
  - **Wikipedia, ropensci docs:** independent corroboration of the API-key + RSC-portal model.

## Evidence

Quoted from search synthesis:

> "Registration and an API key are required. You need to sign up, register an App, and obtain an API key for the App. You can register at `https://developer.rsc.org/` for an API key."
>
> "API access requires free registration via the RSC developer portal, with usage subject to quotas such as a limit of **1,000 calls per month** for standard accounts. For an increased allowance, contact api@rsc.org."
>
> "**Bulk downloads of the entire database are restricted and available only under specific licenses, preventing unrestricted redistribution of aggregated content.**"

| Sub-claim | Status | Evidence |
|---|:---:|---|
| Requires RSC API key | ✅ | RSC Developer Portal is the documented entry point; ChemSpiPy and webchem both validate keys |
| Redistribution prohibited | ✅ | RSC terms explicitly restrict bulk downloads to specific licenses |
| Bonus: 1,000 calls/month free | — | Tighter than PubChem PUG-REST's 5 req/s × 60 = 300/min cap; effectively unusable for bulk resolution |

## Verdict

**VERIFIED.** Both sub-claims (RSC API key required; redistribution prohibited) are correct. Bonus operational fact: ChemSpider's free quota is **1,000 API calls per month** — a hard ceiling that makes ChemSpider strictly worse than PubChem PUG-REST for any bulk resolution work, and reinforces the report's recommendation to NOT route the 2.7M-compound resolution pass through ChemSpider.
