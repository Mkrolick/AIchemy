# CLAIM-22 — Larodan ~3,000 lipids, EUR-priced, structured product code

**Status:** VERIFIED

**Claim:** ~3,000 lipids, EUR-priced, structured product code.

## Verification steps performed

- [iter 22] WebFetch `larodan.com` homepage:
  - Currency selector defaults to **"Euro (€)"** with optional Swedish krona (kr) and USD ($) — matches "EUR-priced".
  - Prices not visible on the homepage without sign-in (page has a "Sign in" link but no inline pricing) — the report only claimed "EUR-priced", not "public anonymous prices", so no contradiction.
  - Sample product codes from the popular-products section: **`31-2260`** (Monodocosahexaenoin), **`33-2260`** (Tridocosahexaenoin) — two-block hyphenated format consistent with a structured code.
- [iter 22] WebSearch corroboration:
  - "Larodan's catalog consists of **around 3,000** different lipids, lipid analogs and lipid-like compounds" — exact verbatim match.
  - Documented numbering scheme: "first two numbers indicate the lipid class, the third and fourth number indicate the number of carbons, the fifth and sixth number indicate the number of double bonds, and seventh and eighth numbers the size (weight)" — confirms the "structured product code" is real and informative (not just an opaque ID).

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| ~3,000 lipids | ✅ | Verbatim "around 3,000" in vendor copy |
| EUR-priced | ✅ | Site default currency is Euro (€) |
| Structured product code | ✅ | Documented 8-digit scheme: class.carbons.dbonds.weight; live examples `31-2260`, `33-2260` |

## Verdict

**VERIFIED.** All three claim components match. Larodan is a small but well-organized lipid specialist with a semantically meaningful product-code system — that's actually useful for an offline join because the code structure encodes molecular class without needing to resolve through CAS/InChIKey. Note: prices appear gated behind sign-in on the public homepage, so a price scrape would still need a registered/automated session even though the catalog metadata and code system are open. The report's positioning of Larodan as a niche lipid-coverage filler is sound.
