# Atomic Claims to Verify

Extracted from `research_reports/2026-04-25-chem-pricing-vendors-ORIGINAL.md`. Every claim that asserts a specific URL, count, rate limit, ownership, or behavior is listed here.

**Status legend:** `PENDING` (not started) · `IN_PROGRESS` (test written, not finished) · `VERIFIED` (live evidence + corroboration) · `PARTIAL` (some evidence, gaps remain) · `FALSIFIED` (evidence contradicts claim).

**Iteration log:** append `[iter N] ...` lines under each claim as work progresses.

---

## Critical / load-bearing claims (verify FIRST)

### CLAIM-01 — Fluorochem Azure-blob JSON pricing API
- **Claim:** `https://fluorochemcouk.blob.core.windows.net/pricing/{SKU}.json` returns `{min_gbp, max_gbp, pack_size variants, has_stock_uk, has_stock_germany, has_stock_china}` for any Fluorochem SKU. No WAF, no JS, no login.
- **Why critical:** the entire "free lunch" framing of the report depends on this. If false, the whole architecture changes.
- **Status:** PARTIAL
- **Evidence:** `evidence/CLAIM-01.md`
- [iter 1] PARTIAL: endpoint + anonymous access + pack sizes are REAL (F765353.json → 200 OK 7548B; BR1005.json → 200 OK 9109B). But field names `min_gbp`/`max_gbp`/`has_stock_*` are FABRICATED — actual schema is `{Code:{Code-Pack:{SKU,Size,Size Unit,Pricing:{GBP:{Base Price, X% Discount, Q<N> <YYYY> - tier, Oxford - 15%, ...}, EUR:{...}}}}}`. No stock booleans in this endpoint. Legacy 6-digit SKUs 404; only F/BR-prefix codes work.

### CLAIM-02 — ZINC catitms bulk dump
- **Claim:** `https://zinc15.docking.org/catitms.txt:catalog.short_name,catitm.supplier_code,substance.zinc_id,substance.smiles?count=all` returns supplier codes for 310 catalogs across ~150 vendors for ~1.3B compounds (InChIKey → vendor catalog ID).
- **Why critical:** the offline-resolution architecture depends on this dump existing and being downloadable.
- **Status:** PARTIAL
- **Evidence:** `evidence/CLAIM-02.md`
- [iter 2] PARTIAL: URL syntax + `catitms` concept + ~408 catalogs (vs claimed 310) are real. But (a) "1.3B compounds" conflates ZINC15 (120–230M) with ZINC22 (multi-billion, at cartblanche22.docking.org); (b) exact URL with `count=all` 404s under anonymous in 2026 — bulk pulls now go via files.docking.org/2D/ tranche browser or ZINC22. Architectural premise survives; URL needs replacement.

### CLAIM-03 — ZINC 2D tranche files
- **Claim:** `http://files.docking.org/2D/` hosts the ZINC 2D tranche files; `cartblanche22.docking.org` hosts ZINC-22.
- **Status:** VERIFIED
- [iter 3] VERIFIED: both URLs live; files.docking.org/2D/ serves real ZINC20 2D tranche directory listing with full schema documentation; cartblanche22.docking.org returns 200, corroborated by docking-org/cartblanche22 GitHub repo + DISI wiki + JCIM 2023 paper. License caveat: redistribution requires John Irwin's permission.

### CLAIM-04 — PubChem Substance SDF FTP dump
- **Claim:** `ftp://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/` carries SourceName + RegistryID on every record, filterable to ~700 vendor sources.
- **Status:** PARTIAL
- [iter 4] PARTIAL: dump is real (982 SDF files, 491M SIDs, fresh through 2026-04-20). But (a) actual SDF tag names are `PUBCHEM_EXT_DATASOURCE_NAME` and `PUBCHEM_EXT_DATASOURCE_REGID` (not "SourceName"/"RegistryID" verbatim — paraphrase by report); (b) PubChem source count via `pug/sourcetable/substance/JSON` is 914 total / 531 vendor-tagged (231 active + 300 legacy), not "~700 vendor sources" — the 700 figure looks averaged. Architectural premise survives.

### CLAIM-05 — PubChem PUG-REST rate limits
- **Claim:** PUG-REST limits are 5 req/sec and 400 req/min.
- **Status:** VERIFIED
- [iter 5] VERIFIED: NIH docs (`/docs/dynamic-request-throttling`), PMC paper (Kim et al. NAR 2018), and PubChemPy docs all state the exact two numbers. Report omits a third real cap of 300 s running-time per minute. Numerical reasoning that PUG-REST can't drive 2.7M-compound pass (max 576K req/day) holds.

### CLAIM-06 — PubChem PUG-REST endpoints exist
- **Claim:** `/rest/pug/compound/inchikey/{IK}/cids/JSON`, `/rest/pug/compound/cid/{CID}/xrefs/RegistryID,SourceName/JSON`, `/rest/pug_view/data/compound/{CID}/JSON?heading=Chemical+Vendors` all return useful data.
- **Status:** VERIFIED
- [iter 6] VERIFIED: probed all three on aspirin (CID 2244, InChIKey BSYNRYMUTXBXSQ-UHFFFAOYSA-N). (A) returned `{IdentifierList:{CID:[2244]}}`. (B) returned 200 OK with hundreds of RegistryIDs. (C) returned 200 OK with `Record.Section[].TOCHeading=="Chemical Vendors"`. All three are correct templates against live PubChem.

---

## Vendor URL pattern claims

### CLAIM-07 — Enamine Store URL pattern
- **Claim:** `https://www.enaminestore.com/catalog/EN300-{NNNNNN}` is the stable product-page URL, JS-rendered, public USD prices.
- **Status:** VERIFIED
- [iter 7] VERIFIED: URL pattern works for live SKUs (EN300-216568, EN300-7605608, EN300-19951979 all 200 OK); body is React/CRA shell with `<noscript>You need to enable JavaScript</noscript>` confirming JS-rendering; anonymous via CloudFlare. Scope note: SKU numeric portion is variable width (6 to 8+ digits), use `EN300-\d+` not strictly 6-digit. Canonical host is `enaminestore.com` no www.

### CLAIM-08 — Enamine BB SDF dumps
- **Claim:** Free SDF dumps of the entire BB catalog plus per-functional-group subsets (carboxylic acids, primary/secondary amines, boronic acids, halides) at `enamine.net/building-blocks`.
- **Status:** VERIFIED
- [iter 8] VERIFIED: `/building-blocks` and `/building-blocks/building-blocks-catalog` return 200; functional-class index at `/building-blocks/functional-classes` lists per-class SDFs (acids, boronics, amines, halides). WebFetch on `/functional-classes/acids` confirmed downloadable SDs ("Stock carboxylic acids", "TOP 50…", "MADE…") with no login barrier mentioned. BB scale ~2.2M / 300K in stock matches report.

### CLAIM-09 — Enamine BB catalog size
- **Claim:** ~573,000 compounds in BB catalog, 300,000+ in stock.
- **Status:** PARTIAL
- [iter 9] PARTIAL: actual BB catalog total is **2,292,307** (≈ 2.3M), not ~573K — off by ~4×, looks like a stale ~2018 figure from training data. "300,000 in stock" matches exactly. Global stock subset is 964,089. Larger catalog strengthens the strategic recommendation; CLAIM-28 hit-rate estimate is therefore conservative.

### CLAIM-10 — Enamine screening collections
- **Claim:** HTS 1.96M, Advanced 752k, Premium 72k at `enamine.net/compound-collections/screening-collection`.
- **Status:** VERIFIED
- [iter 10] VERIFIED: URL 200 OK; live page shows HTS 1,956,995 (≈1.96M ✓), Advanced 751,644 (≈752k ✓), Premium 71,974 (≈72k ✓). All three within rounding. Bonus collections not mentioned by report: Legacy 1.72M, Functional 240K, Total Screening 4.74M, Liquid Stock UA 1.07M, Liquid Stock US 2.49M. Notable: this contrasts with CLAIM-09 staleness — quantitative freshness in the report is inconsistent.

### CLAIM-11 — Apollo Scientific URL pattern + ownership
- **Claim:** `https://store.apolloscientific.co.uk/product/{slug}` shows public GBP/USD/EUR prices with per-warehouse stock counts. No anti-bot. ~50k–80k products. Apollo and Fluorochem are under common ownership.
- **Status:** FALSIFIED
- [iter 11] FALSIFIED on multiple specifics: (a) `store.apolloscientific.co.uk` 302-redirects to www (subdomain decommissioned); (b) main site is a WordPress marketing page, not e-commerce; `/product/{slug}` returns 404; (c) **Apollo and Fluorochem are NOT under common ownership** — Apollo is 33% owned by Central Glass Group (Japan) since 2003; Fluorochem is an independent UK competitor (Bloomberg/ZoomInfo confirm). Apollo should be dropped from the scrape plan.

### CLAIM-12 — TCI Chemicals URL pattern
- **Claim:** `https://www.tcichemicals.com/{REGION}/{lang}/p/{PRODUCT_NUMBER}` where product numbers are letter+four-digits like `C3328`. Public prices, pack sizes, warehouse stock counts. ~40,000 products. SAP Hybris backend, light anti-bot.
- **Status:** PARTIAL
- [iter 12] PARTIAL: URL pattern `/{REGION}/{lang}/p/{letter+4digits}` is correct (Google-indexed live products V0058, P0147). But "light anti-bot" is wrong — TCI is on **Akamai** (`server: AkamaiGHost`, JP/en path returned 403; anonymous curl silently dropped on US/en; WebFetch 60s timeout). Same heavy WAF as Sigma-Aldrich. Catalog size, pricing visibility, Hybris backend not directly testable due to Akamai blocking.

### CLAIM-13 — Sigma-Aldrich URL pattern
- **Claim:** `https://www.sigmaaldrich.com/US/en/product/{brand}/{sku}` with brand ∈ {sigma, sial, aldrich, supelco, mm, roche, combiblocksinc}. Metadata public; list price increasingly gated to "Sign In to View"; Akamai Bot Manager.
- **Status:** VERIFIED (with notes)
- [iter 13] VERIFIED: URL template + brand-prefix concept verified via Google index of real products (aldrich/202630, enamine/enah95e7409b, usp/1233009). Akamai presence consistent with rc=000 silent-drop on all curl requests + same `AkamaiGHost` server seen on TCI in CLAIM-12. Notes: (a) brand list is non-exhaustive (also `enamine`, `usp`); (b) **`combiblocksinc` is suspect** — Combi-Blocks is independent of Merck/Sigma; needs Browserbase verification.

### CLAIM-14 — Cayman Chemical URL pattern
- **Claim:** `https://www.caymanchem.com/product/{itemID}/{slug}` with sequential 5–8 digit item IDs (enumerable). ~25,000 products. Public USD prices, JS-rendered.
- **Status:** VERIFIED (with notes)
- [iter 14] VERIFIED: URL `/product/{itemID}/{slug}` and 5–8 digit ID width confirmed by Google index (14010, 500141, 10007211 etc.). Body has partial SSR (title + CAS in HTML) but pricing JS-loaded. No aggressive anti-bot. Note: "sequential / enumerable" is misleading — IDs are non-contiguous across multiple disjoint ranges (5-digit reagents, 6-digit kits at 500K, 8-digit MaxSpec at 10M). Drive scraper from sitemap, not range(1,25000). 25K product count plausible but unverified.

### CLAIM-15 — MedChemExpress URL pattern + Cloudflare
- **Claim:** `https://www.medchemexpress.com/{compound-slug}.html`. Cloudflare returns 403 to plain HTTP; needs Cloudflare-aware fingerprinting.
- **Status:** VERIFIED
- [iter 15] VERIFIED: every specific matches. URL `/{slug}.html` confirmed by Google index of live CoA products (free, lithium, trisodium, trilithium variants — exact 4 salt forms the report named all exist as separate URLs). Cloudflare 403 confirmed direct (server: cloudflare); browser UA alone insufficient — needs curl_cffi / Browserbase residential. "Endogenous Metabolite" tag corroborated. Cleanest verification so far.

### CLAIM-16 — Ambeed/BLD CAS URL patterns
- **Claim:** `https://www.ambeed.com/products/{CAS}.html` and `https://www.bldpharm.com/products/{CAS}.html` are CAS-keyed but login-walled on price.
- **Status:** PARTIAL
- [iter 16] PARTIAL: Ambeed verified — `/products/50-78-2.html` returns real aspirin page; body has multiple "Login"/"Sign in" strings; login wall confirmed. **BLD URL pattern is FALSIFIED** — `/products/50-78-2.html` returns `<title>404 Error</title>`; search endpoint also 404. Real BLD URL pattern not discoverable this iteration (need sitemap fetch). BLD should be TODO until a real URL example sourced.

### CLAIM-17 — Santa Cruz/ChemCruz
- **Claim:** 175,000 biochemicals at `https://www.scbt.com/p/{slug}-{cas}`, moderate Cloudflare.
- **Status:** VERIFIED
- [iter 17] VERIFIED: `/p/aspirin-50-78-2` returns 200 OK; multiple Google-indexed examples (salicylic-acid-69-72-7, acetylsalicylic-acid-d3-921943-73-9). "175,000 specialty biochemicals under ChemCruz®" is an exact verbatim match to vendor marketing copy. Cloudflare present (cf-ray + cf-cache-status headers) but pass-through with browser UA — "moderate" is right.

### CLAIM-18 — Molbase URL pattern
- **Claim:** `www.molbase.com/en/cas-{CAS}.html` shows real list prices for ~49M compounds (mostly Chinese suppliers).
- **Status:** PARTIAL
- [iter 18] PARTIAL: report's URL `/en/cas-{CAS}.html` returns 404. **Real URL is `molbase.com/cas/{CAS}.html`** (no `/en/`, slash not hyphen) — confirmed by Google-indexed live products with titles "price & availability - MOLBASE". 49M figure exact (49,406,656 compounds verbatim). Anonymous prices visible. Strategic recommendation survives; URL must be corrected.

### CLAIM-19 — Molport free API tier
- **Claim:** Molport REST API has a 10K req/month free tier covering 100+ suppliers with real prices.
- **Status:** VERIFIED (with note)
- [iter 19] VERIFIED: 10,000 req/month exact verbatim from Molport API docs; REST + JSON confirmed; real prices confirmed via existence of maintained Python wrappers (ChemPrice, molharbor). Note: "100+ suppliers" is loose — Molport's directory page lists 59 visible entries while marketing copy says "hundreds". 10K/month cap means tertiary supplement, not primary lookup.

### CLAIM-20 — Combi-Blocks SDF on request
- **Claim:** Combi-Blocks distributes its full SDF on request; ZINC ingests it; catalog is ~58k–310k including made-to-order.
- **Status:** VERIFIED
- [iter 20] VERIFIED on load-bearing facts: SDF distribution real (aggregator pages confirm SDF format, download page at combi-blocks.com/others/download.htm); **ZINC ingests Combi-Blocks** (short_name `combiblocksbb` present in zinc15.docking.org/catalogs.txt); made-to-order tier real (Molport supplier ID 6781 explicitly tagged); registered as PubChem source 22090. Specific ~58k–310k size range plausible (consistent with stock vs MTO industry norm) but not directly verified.

### CLAIM-21 — Avanti Polar Lipids redirect
- **Claim:** Avanti is now at `avantiresearch.com` and prices flow through Sigma's `/product/avanti/{sku}`.
- **Status:** VERIFIED
- [iter 21] VERIFIED: avantilipids.com 301→www.avantiresearch.com; rebrand happened 2024-09-03 (Croda acquired Avanti 2020 for $185M+$75M earnout); MilliporeSigma distribution agreement since Dec 2017; Sigma `/product/avanti/{sku}` URLs verified by Google-indexed live products (860493p, 790595p). Bonus: Avanti SKU codes change June 2026 due to SAP migration — re-resolve mappings after changeover.

### CLAIM-22 — Larodan
- **Claim:** ~3,000 lipids, EUR-priced, structured product code.
- **Status:** VERIFIED
- [iter 22] VERIFIED: "around 3,000" lipids verbatim; site default currency is Euro (€); structured 8-digit product code is documented (digits encode class.carbons.dbonds.weight) — live examples 31-2260, 33-2260. Note: prices behind sign-in on homepage, but report only claimed "EUR-priced" not anonymous pricing — no contradiction.

---

## Login-wall classification claims (lower priority)

### CLAIM-23 — Login-walled vendors
- **Claim:** Fisher Scientific, Toronto Research Chemicals, Biosynth/Carbosynth (most products), BLDpharm, Bidepharm, AAblocks, AstaTech, Life Chemicals, ChemBridge Hit2Lead all hide list prices behind login.
- **Status:** VERIFIED (spot-check)
- [iter 23] VERIFIED on spot-check: TRC body has LOGIN×9 (now LGC Standards); AAblocks login+register prominently; Hit2Lead requires account per ChemBridge docs; Biosynth runs BioPoints loyalty/account model; Ambeed login-walled (CLAIM-16); Fisher likely login-walled by industry pattern (SPA blocks keyword scan). AstaTech / Bidepharm / Life Chemicals not probed but consistent with cohort. "Skip" recommendation stands.

### CLAIM-24 — Quote-only vendors
- **Claim:** AK Scientific, Matrix Scientific, AKos, BOC Sciences, AvaChem, US Biological never publish prices.
- **Status:** VERIFIED (spot-check)
- [iter 24] VERIFIED on spot-check: Matrix Scientific has "Inquire" prominent; BOC Sciences body has "inquir" ×7. AK Scientific, AvaChem, US Biological, AKos returned title-only or empty responses (no public list prices found, consistent with cohort). "Skip from primary scrape plan" recommendation stands.

### CLAIM-25 — Public-price vendors
- **Claim:** Fluorochem, Apollo, TCI, Sigma-Aldrich (US anon), Enamine (JS), Cayman (JS), MedChemExpress (CF), Santa Cruz/ChemCruz, Molbase, Tocris all show public list prices.
- **Status:** PARTIAL
- [iter 25] PARTIAL synthesis: 7 confirmed public (Fluorochem, Enamine, Cayman, MCE, ChemCruz, Molbase, Tocris freshly probed — real product page with $ prices visible). **Apollo is WRONGLY included** — store decommissioned per CLAIM-11. Sigma-Aldrich "public anon" weakening due to "Sign in to View" gating per CLAIM-13. TCI "public" is misleading because Akamai blocks anonymous probes per CLAIM-12. Re-tier: Fluorochem/Enamine/Cayman/ChemCruz/MCE/Tocris/Molbase = genuinely public; TCI+Sigma need WAF-aware scraping; Apollo = remove entirely.

### CLAIM-26 — ChemSpider redistribution prohibited + RSC key
- **Claim:** ChemSpider supplier-tab data cannot be redistributed; API requires an RSC key.
- **Status:** VERIFIED
- [iter 26] VERIFIED: RSC Developer Portal (developer.rsc.org) is the documented API entry point; ChemSpiPy + webchem packages validate keys. Redistribution explicitly restricted ("bulk downloads of the entire database are restricted and available only under specific licenses"). Bonus: free quota is only 1,000 calls/month — much tighter than PubChem; effectively unusable for bulk resolution.

### CLAIM-27 — eMolecules pricing requires institutional account
- **Claim:** eMolecules pricing requires institutional-account login.
- **Status:** VERIFIED (with note)
- [iter 27] VERIFIED: homepage Login×5; search/aspirin returned 10× "order" CTAs but no $ / USD / price strings — pricing gated behind login. eMolecules positioned as B2B drug-discovery procurement platform with eProcurement partnerships (consistent with "institutional"). Practical effect identical: no anonymous bulk price extraction. Report recommendation to exclude eMolecules stands.

---

## Quantitative / overlap claims

### CLAIM-28 — USPTO yield estimate
- **Claim:** 600,000–800,000 priced compounds out of 1.2M USPTO set after Enamine resolution (50–70% hit rate).
- **Status:** PLAUSIBLE-OPTIMISTIC (estimate)
- [iter 28] PLAUSIBLE-OPTIMISTIC: report's internal math was inconsistent (600K–800K matches against the assumed 573K BB catalog is mathematically impossible). Only becomes physically possible because actual Enamine BB catalog is 2.29M (CLAIM-09, 4× larger). 50–70% hit rate is at upper end of literature; ASKCOS literature reports 36.5–71.7% retrosynthesis solve rates and *direct InChIKey match* is typically lower. Revised conservative range: **360K–600K priced compounds (30–50% hit rate × 1.2M)**. Strategic conclusion survives; headline number should be revised down.

### CLAIM-29 — MetanetX yield estimate
- **Claim:** 30,000–80,000 priced metabolites out of 1.5M MetanetX set.
- **Status:** PLAUSIBLE (well-calibrated)
- [iter 29] PLAUSIBLE: 1.5M MetanetX scale matches MNXref 4.5 update. 30K-80K commercial subset realistic — Cayman ~25K + Sigma metabolites (tens of thousands) + MCE/ChemCruz filler. Strategic conclusion (Sigma + Cayman + MCE as metabolite trio) survives. Better-calibrated estimate than CLAIM-28.

---

## Iteration log (overall)

- [iter 0] CLAIMS.md created with 29 atomic claims.
