# CLAIM-20 — Combi-Blocks SDF on request + ZINC ingestion

**Status:** VERIFIED (catalog size range unverified)

**Claim:** Combi-Blocks distributes its full SDF on request; ZINC ingests it; catalog is ~58k–310k including made-to-order.

## Verification steps performed

- [iter 20] WebSearch corroborated SDF distribution: "catalogs in PDF, ISIS-Base or SD file format are available". Download page lives at `combi-blocks.com/others/download.htm`.
- [iter 20] PubChem registers Combi-Blocks as data source ID 22090 (`pubchem.ncbi.nlm.nih.gov/source/22090`).
- [iter 20] Molport lists Combi-Blocks as a supplier with explicit "made-to-order" SKU at `/shop/supplier/Combi-Blocks-Inc-made-to-order/6781` — confirms the report's distinction between in-stock and made-to-order tiers.
- [iter 20] curl ZINC15 `catalogs.txt:short_name?count=all` → grep finds `combiblocksbb` in the catalog list. **ZINC15 ingests Combi-Blocks.** ✅
- [iter 20] No direct verification of the ~58k–310k catalog-size range; not contradicted but not corroborated either.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| SDF distribution available | ✅ | Multiple aggregator pages confirm SDF format |
| ZINC ingests Combi-Blocks | ✅ | `combiblocksbb` short_name present in ZINC15 catalogs.txt |
| Made-to-order tier exists | ✅ | Molport supplier `Combi-Blocks-Inc-made-to-order/6781` |
| ~58k–310k catalog size | ⚠️ | Plausible (58k = in-stock, 310k = total including MTO is in line with industry) but not directly verified |

## Verdict

**VERIFIED** on the load-bearing facts. Combi-Blocks is a real, well-integrated supplier that distributes its catalog as SDF, is ingested by ZINC (under short_name `combiblocksbb`), and offers a made-to-order tier on top of in-stock inventory. The specific 58k–310k size range is not directly verifiable from public pages but is consistent with how aggregators like Molport split the supplier into stock vs MTO. Strategic recommendation in the report — use Combi-Blocks for coverage gap-filling via offline resolution rather than live price scraping — survives.
